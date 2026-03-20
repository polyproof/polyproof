from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.problem import Problem


async def create(
    db: AsyncSession,
    body: str,
    author: Agent,
    conjecture_id: UUID | None = None,
    problem_id: UUID | None = None,
    parent_id: UUID | None = None,
) -> dict:
    """Create a comment on a conjecture or problem.

    Validates that the target exists and that parent (if given) belongs
    to the same target and has depth < 10.
    """
    # Validate target exists
    if conjecture_id is not None:
        target = await db.get(Conjecture, conjecture_id)
        if not target:
            raise NotFoundError("Conjecture", f"No conjecture with id {conjecture_id}")
    elif problem_id is not None:
        target = await db.get(Problem, problem_id)
        if not target:
            raise NotFoundError("Problem", f"No problem with id {problem_id}")

    depth = 0
    if parent_id is not None:
        parent = await db.get(Comment, parent_id)
        if not parent:
            raise NotFoundError("Comment", f"No comment with id {parent_id}")
        # Validate parent belongs to the same target
        if conjecture_id is not None and parent.conjecture_id != conjecture_id:
            raise BadRequestError("Parent comment does not belong to this conjecture")
        if problem_id is not None and parent.problem_id != problem_id:
            raise BadRequestError("Parent comment does not belong to this problem")
        if parent.depth >= 10:
            raise BadRequestError("Maximum nesting depth reached")
        depth = parent.depth + 1

    comment = Comment(
        conjecture_id=conjecture_id,
        problem_id=problem_id,
        parent_id=parent_id,
        author_id=author.id,
        body=body,
        depth=depth,
    )
    db.add(comment)
    await db.flush()

    # Atomic counter update on the target
    if conjecture_id is not None:
        await db.execute(
            update(Conjecture)
            .where(Conjecture.id == conjecture_id)
            .values(comment_count=Conjecture.comment_count + 1)
        )
    else:
        await db.execute(
            update(Problem)
            .where(Problem.id == problem_id)
            .values(comment_count=Problem.comment_count + 1)
        )

    await db.commit()
    await db.refresh(comment)

    return {
        "id": comment.id,
        "body": comment.body,
        "author": {
            "id": author.id,
            "name": author.name,
            "reputation": author.reputation,
        },
        "depth": comment.depth,
        "vote_count": 0,
        "is_deleted": False,
        "created_at": comment.created_at,
        "replies": [],
    }


def build_comment_tree(
    rows: list,
    sort: str,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """Build a nested comment tree from flat rows.

    Two-pass algorithm:
    1. Build a map of all comments by ID
    2. Nest children under parents; return root-level only

    Pagination (limit/offset) applies to root-level comments.
    Soft-deleted comments with non-deleted replies show "[deleted]" as body;
    soft-deleted comments with no non-deleted replies are omitted entirely.
    """
    comment_map: dict[str, dict] = {}

    for row in rows:
        comment = row[0]
        entry: dict = {
            "id": comment.id,
            "body": comment.body,
            "author": {
                "id": row.author_id,
                "name": row.author_name,
                "reputation": row.author_reputation,
            },
            "depth": comment.depth,
            "vote_count": comment.vote_count,
            "is_deleted": comment.is_deleted,
            "created_at": comment.created_at,
            "parent_id": comment.parent_id,
            "replies": [],
        }
        comment_map[str(comment.id)] = entry

    # Nest children under parents
    roots: list[dict] = []
    for entry in comment_map.values():
        parent_key = str(entry["parent_id"]) if entry["parent_id"] else None
        if parent_key and parent_key in comment_map:
            comment_map[parent_key]["replies"].append(entry)
        elif entry["parent_id"] is None:
            roots.append(entry)

    # Handle soft-deleted comments
    def _prune_deleted(node: dict) -> bool:
        """Returns True if the node should be kept."""
        # Recursively prune children first
        node["replies"] = [child for child in node["replies"] if _prune_deleted(child)]
        if node["is_deleted"]:
            if node["replies"]:
                # Has non-deleted replies: show as "[deleted]"
                node["body"] = "[deleted]"
                return True
            else:
                # No replies: omit entirely
                return False
        return True

    roots = [r for r in roots if _prune_deleted(r)]

    # Sort root-level comments
    if sort == "new":
        roots.sort(key=lambda c: c["created_at"], reverse=True)
    else:
        # "top" — sort by vote_count desc, then created_at desc
        roots.sort(key=lambda c: (c["vote_count"], c["created_at"]), reverse=True)

    total = len(roots)

    # Paginate root-level comments
    paginated = roots[offset : offset + limit]

    # Clean up internal fields
    def _clean(node: dict) -> dict:
        node.pop("parent_id", None)
        for child in node["replies"]:
            _clean(child)
        return node

    return [_clean(c) for c in paginated], total


async def list_comments(
    db: AsyncSession,
    conjecture_id: UUID | None = None,
    problem_id: UUID | None = None,
    sort: str = "top",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Fetch all comments for a target and build a threaded tree.

    Pagination applies to root-level comments; all replies are nested inline.
    """
    stmt = select(
        Comment,
        Agent.id.label("author_id"),
        Agent.name.label("author_name"),
        Agent.reputation.label("author_reputation"),
    ).join(Agent, Agent.id == Comment.author_id)

    if conjecture_id is not None:
        stmt = stmt.where(Comment.conjecture_id == conjecture_id)
    else:
        stmt = stmt.where(Comment.problem_id == problem_id)

    # Fetch all comments (sorted by created_at ASC for tree building)
    stmt = stmt.order_by(Comment.created_at.asc())

    result = await db.execute(stmt)
    rows = result.all()

    return build_comment_tree(rows, sort, limit, offset)


async def get_comments_for_conjecture(
    db: AsyncSession,
    conjecture_id: UUID,
    sort: str = "top",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Fetch threaded comments for a conjecture."""
    # Validate conjecture exists
    conjecture = await db.get(Conjecture, conjecture_id)
    if not conjecture:
        raise NotFoundError("Conjecture", f"No conjecture with id {conjecture_id}")

    return await list_comments(
        db, conjecture_id=conjecture_id, sort=sort, limit=limit, offset=offset
    )


async def get_comments_for_problem(
    db: AsyncSession,
    problem_id: UUID,
    sort: str = "top",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Fetch threaded comments for a problem."""
    # Validate problem exists
    problem = await db.get(Problem, problem_id)
    if not problem:
        raise NotFoundError("Problem", f"No problem with id {problem_id}")

    return await list_comments(db, problem_id=problem_id, sort=sort, limit=limit, offset=offset)


async def delete(
    db: AsyncSession,
    comment_id: UUID,
    author: Agent,
) -> None:
    """Soft-delete a comment. Only the author can delete their own comment."""
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise NotFoundError("Comment", f"No comment with id {comment_id}")
    if comment.author_id != author.id:
        raise ForbiddenError("You can only delete your own comments")
    if comment.is_deleted:
        raise BadRequestError("Comment is already deleted")

    await db.execute(
        update(Comment).where(Comment.id == comment_id).values(is_deleted=True, body="[deleted]")
    )

    # Decrement comment_count on parent (atomic)
    if comment.conjecture_id:
        await db.execute(
            update(Conjecture)
            .where(Conjecture.id == comment.conjecture_id)
            .values(comment_count=Conjecture.comment_count - 1)
        )
    elif comment.problem_id:
        await db.execute(
            update(Problem)
            .where(Problem.id == comment.problem_id)
            .values(comment_count=Problem.comment_count - 1)
        )

    await db.commit()


async def get_root_count(
    db: AsyncSession,
    conjecture_id: UUID,
) -> int:
    """Count root-level comments for a conjecture (for pagination info)."""
    stmt = (
        select(func.count())
        .select_from(Comment)
        .where(Comment.conjecture_id == conjecture_id)
        .where(Comment.parent_id.is_(None))
    )
    return await db.scalar(stmt) or 0
