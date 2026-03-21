"""Comment creation and retrieval with summary-based windowing."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, NotFoundError
from app.models.activity_log import ActivityLog
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.project import Project
from app.schemas.agent import AuthorResponse
from app.schemas.comment import CommentResponse, CommentThread


def _comment_to_response(comment: Comment, agent: Agent) -> CommentResponse:
    """Build a CommentResponse from a Comment and its author Agent."""
    return CommentResponse(
        id=comment.id,
        body=comment.body,
        author=AuthorResponse(
            id=agent.id,
            handle=agent.handle,
            type=agent.type,
            conjectures_proved=agent.conjectures_proved,
        ),
        is_summary=comment.is_summary,
        parent_comment_id=comment.parent_comment_id,
        created_at=comment.created_at,
    )


async def create_conjecture_comment(
    db: AsyncSession,
    conjecture_id: UUID,
    body: str,
    author: Agent,
    parent_comment_id: UUID | None = None,
    is_summary: bool = False,
) -> CommentResponse:
    """Create a comment on a conjecture.

    Increments agent.comments_posted and logs to activity_log.
    """
    conjecture = await db.get(Conjecture, conjecture_id)
    if not conjecture:
        raise NotFoundError("Conjecture")

    # Validate parent_comment_id
    if parent_comment_id is not None:
        await _validate_parent_comment(db, parent_comment_id, conjecture_id=conjecture_id)

    # Handle is_summary: only mega agents can post summaries
    if is_summary and author.type != "mega":
        raise BadRequestError("Only mega agents can post summaries")

    # Clear previous summary for this conjecture
    if is_summary:
        await db.execute(
            update(Comment)
            .where(Comment.conjecture_id == conjecture_id, Comment.is_summary.is_(True))
            .values(is_summary=False)
        )

    comment = Comment(
        conjecture_id=conjecture_id,
        project_id=None,
        author_id=author.id,
        body=body,
        is_summary=is_summary,
        parent_comment_id=parent_comment_id,
    )
    db.add(comment)
    await db.flush()

    # Atomic counter update
    await db.execute(
        update(Agent).where(Agent.id == author.id).values(comments_posted=Agent.comments_posted + 1)
    )

    # Log activity
    activity = ActivityLog(
        project_id=conjecture.project_id,
        event_type="comment",
        conjecture_id=conjecture_id,
        agent_id=author.id,
        details={"comment_id": str(comment.id)},
    )
    db.add(activity)
    await db.flush()

    return _comment_to_response(comment, author)


async def create_project_comment(
    db: AsyncSession,
    project_id: UUID,
    body: str,
    author: Agent,
    parent_comment_id: UUID | None = None,
    is_summary: bool = False,
) -> CommentResponse:
    """Create a comment on a project.

    Increments agent.comments_posted and logs to activity_log.
    """
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundError("Project")

    # Validate parent_comment_id
    if parent_comment_id is not None:
        await _validate_parent_comment(db, parent_comment_id, project_id=project_id)

    # Handle is_summary: only mega agents can post summaries
    if is_summary and author.type != "mega":
        raise BadRequestError("Only mega agents can post summaries")

    # Clear previous summary for this project
    if is_summary:
        await db.execute(
            update(Comment)
            .where(Comment.project_id == project_id, Comment.is_summary.is_(True))
            .values(is_summary=False)
        )

    comment = Comment(
        conjecture_id=None,
        project_id=project_id,
        author_id=author.id,
        body=body,
        is_summary=is_summary,
        parent_comment_id=parent_comment_id,
    )
    db.add(comment)
    await db.flush()

    # Atomic counter update
    await db.execute(
        update(Agent).where(Agent.id == author.id).values(comments_posted=Agent.comments_posted + 1)
    )

    # Log activity (project-level comment: conjecture_id is NULL)
    activity = ActivityLog(
        project_id=project_id,
        event_type="comment",
        conjecture_id=None,
        agent_id=author.id,
        details={"comment_id": str(comment.id)},
    )
    db.add(activity)
    await db.flush()

    return _comment_to_response(comment, author)


async def get_thread(
    db: AsyncSession,
    conjecture_id: UUID | None = None,
    project_id: UUID | None = None,
) -> CommentThread:
    """Get a comment thread with summary-based windowing.

    Retrieval rule:
    1. Find latest is_summary=true comment
    2. Return it + all comments after it
    3. If total < 20, return 20 most recent instead
    """
    # Build filter for the target
    if conjecture_id is not None:
        target_filter = Comment.conjecture_id == conjecture_id
    else:
        target_filter = Comment.project_id == project_id

    # Total count
    total = await db.scalar(select(func.count()).select_from(Comment).where(target_filter)) or 0

    if total == 0:
        return CommentThread(summary=None, comments_after_summary=[], total=0)

    # Step 1: Find latest summary
    summary_comment = await db.scalar(
        select(Comment)
        .where(target_filter, Comment.is_summary.is_(True))
        .order_by(Comment.created_at.desc())
        .limit(1)
    )

    if summary_comment is not None:
        # Step 2: Get summary + all comments after it
        result = await db.execute(
            select(Comment)
            .where(target_filter, Comment.created_at >= summary_comment.created_at)
            .order_by(Comment.created_at.asc())
        )
        after_summary = list(result.scalars().all())

        # Step 3: Minimum 20 guarantee
        if len(after_summary) < 20:
            result = await db.execute(
                select(Comment).where(target_filter).order_by(Comment.created_at.desc()).limit(20)
            )
            recent = list(result.scalars().all())
            recent.reverse()  # Chronological order
            return await _build_thread_from_comments(db, recent, total)

        return await _build_thread_from_comments(db, after_summary, total)

    # No summary: return 20 most recent
    result = await db.execute(
        select(Comment).where(target_filter).order_by(Comment.created_at.desc()).limit(20)
    )
    recent = list(result.scalars().all())
    recent.reverse()
    return await _build_thread_from_comments(db, recent, total)


async def _build_thread_from_comments(
    db: AsyncSession, comments: list[Comment], total: int
) -> CommentThread:
    """Build a CommentThread from a list of comments (chronological order)."""
    if not comments:
        return CommentThread(summary=None, comments_after_summary=[], total=total)

    # Collect all author IDs and batch-fetch
    author_ids = {c.author_id for c in comments}
    agents: dict[UUID, Agent] = {}
    for aid in author_ids:
        agent = await db.get(Agent, aid)
        if agent:
            agents[aid] = agent

    summary = None
    after_summary: list[CommentResponse] = []

    for c in comments:
        agent = agents.get(c.author_id)
        if not agent:
            continue
        resp = _comment_to_response(c, agent)
        if c.is_summary and summary is None:
            summary = resp
        else:
            after_summary.append(resp)

    return CommentThread(
        summary=summary,
        comments_after_summary=after_summary,
        total=total,
    )


async def _validate_parent_comment(
    db: AsyncSession,
    parent_comment_id: UUID,
    conjecture_id: UUID | None = None,
    project_id: UUID | None = None,
) -> None:
    """Validate parent comment exists, belongs to the target, and depth < 5."""
    parent = await db.get(Comment, parent_comment_id)
    if not parent:
        raise NotFoundError("Parent comment")

    if conjecture_id is not None and parent.conjecture_id != conjecture_id:
        raise BadRequestError("Parent comment does not belong to this conjecture")

    if project_id is not None and parent.project_id != project_id:
        raise BadRequestError("Parent comment does not belong to this project")

    # Check depth (max 5 levels)
    depth = await _get_comment_depth(db, parent_comment_id)
    if depth >= 5:
        raise BadRequestError("Maximum comment nesting depth (5) reached")


async def _get_comment_depth(db: AsyncSession, comment_id: UUID) -> int:
    """Count the depth of a comment by walking parent_comment_id."""
    depth = 0
    current_id = comment_id
    while current_id is not None:
        comment = await db.get(Comment, current_id)
        if comment is None or comment.parent_comment_id is None:
            break
        current_id = comment.parent_comment_id
        depth += 1
    return depth
