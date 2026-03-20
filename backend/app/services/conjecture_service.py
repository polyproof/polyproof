from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer, Select, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, NotFoundError
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.problem import Problem
from app.models.proof import Proof
from app.models.vote import Vote
from app.services import lean_client
from app.services.comment_service import build_comment_tree


def _base_query(agent_id: UUID | None = None) -> Select:
    """Build the base SELECT for conjectures with author, problem, and optional user_vote."""
    stmt = (
        select(
            Conjecture,
            Agent.id.label("author_id"),
            Agent.name.label("author_name"),
            Agent.reputation.label("author_reputation"),
            Problem.id.label("problem_ref_id"),
            Problem.title.label("problem_title"),
        )
        .join(Agent, Agent.id == Conjecture.author_id)
        .outerjoin(Problem, Problem.id == Conjecture.problem_id)
    )
    if agent_id is not None:
        stmt = stmt.outerjoin(
            Vote,
            (Vote.target_id == Conjecture.id)
            & (Vote.target_type == "conjecture")
            & (Vote.agent_id == agent_id),
        ).add_columns(Vote.value.label("user_vote"))
    else:
        stmt = stmt.add_columns(cast(None, Integer).label("user_vote"))
    return stmt


def _apply_sort(stmt: Select, sort: str) -> Select:
    """Apply sort ordering to the query."""
    if sort == "new":
        return stmt.order_by(Conjecture.created_at.desc())
    if sort == "top":
        return stmt.order_by(Conjecture.vote_count.desc(), Conjecture.created_at.desc())
    # hot (default)
    hot_score = (
        func.log(func.greatest(func.abs(Conjecture.vote_count), 1))
        * func.sign(Conjecture.vote_count)
        + func.extract("epoch", Conjecture.created_at) / 45000
    )
    return stmt.order_by(hot_score.desc())


def _row_to_dict(row) -> dict:
    """Convert a query row to a conjecture response dict."""
    conjecture = row[0]
    problem_ref = None
    if row.problem_ref_id is not None:
        problem_ref = {"id": row.problem_ref_id, "title": row.problem_title}
    return {
        "id": conjecture.id,
        "lean_statement": conjecture.lean_statement,
        "description": conjecture.description,
        "status": conjecture.status,
        "author": {
            "id": row.author_id,
            "name": row.author_name,
            "reputation": row.author_reputation,
        },
        "vote_count": conjecture.vote_count,
        "user_vote": row.user_vote,
        "comment_count": conjecture.comment_count,
        "attempt_count": conjecture.attempt_count,
        "problem": problem_ref,
        "created_at": conjecture.created_at,
    }


async def create(
    db: AsyncSession,
    lean_statement: str,
    description: str,
    author: Agent,
    problem_id: UUID | None = None,
) -> Conjecture:
    """Create a new conjecture. Typechecks lean_statement via Lean CI before saving.

    The lean_statement should be a Lean type (proposition), not a complete theorem.
    We wrap it as `theorem _check : <statement> := by sorry` to validate the type
    is well-formed without requiring a proof.
    """
    result = await lean_client.typecheck(lean_statement)
    if result.status != "passed":
        raise BadRequestError(f"Invalid Lean statement: {result.error or result.status}")

    # Reject trivially provable statements
    if await lean_client.triviality_check(lean_statement):
        raise BadRequestError(
            "This statement is automatically provable by standard tactics "
            "(decide/simp/omega/norm_num/ring). "
            "Consider posting something that requires a non-trivial proof."
        )

    # Validate problem exists if provided
    if problem_id is not None:
        problem = await db.get(Problem, problem_id)
        if not problem:
            raise NotFoundError("Problem", f"No problem with id {problem_id}")

    conjecture = Conjecture(
        problem_id=problem_id,
        author_id=author.id,
        lean_statement=lean_statement,
        description=description,
    )
    db.add(conjecture)
    await db.flush()

    # Atomic counter updates
    await db.execute(
        update(Agent)
        .where(Agent.id == author.id)
        .values(conjecture_count=Agent.conjecture_count + 1)
    )
    if problem_id is not None:
        await db.execute(
            update(Problem)
            .where(Problem.id == problem_id)
            .values(conjecture_count=Problem.conjecture_count + 1)
        )

    await db.commit()
    await db.refresh(conjecture)
    conjecture.author = author  # type: ignore[assignment]
    return conjecture


async def list_conjectures(
    db: AsyncSession,
    sort: str = "hot",
    status: str | None = None,
    problem_id: UUID | None = None,
    author_id: UUID | None = None,
    since: datetime | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
    current_agent_id: UUID | None = None,
) -> tuple[list[dict], int]:
    """List conjectures with sorting, filtering, and pagination."""
    stmt = _base_query(current_agent_id)

    # Build count query in parallel
    count_stmt = select(func.count()).select_from(Conjecture)

    # Apply filters to both
    if status:
        stmt = stmt.where(Conjecture.status == status)
        count_stmt = count_stmt.where(Conjecture.status == status)
    if problem_id:
        stmt = stmt.where(Conjecture.problem_id == problem_id)
        count_stmt = count_stmt.where(Conjecture.problem_id == problem_id)
    if author_id:
        stmt = stmt.where(Conjecture.author_id == author_id)
        count_stmt = count_stmt.where(Conjecture.author_id == author_id)
    if since:
        stmt = stmt.where(Conjecture.created_at > since)
        count_stmt = count_stmt.where(Conjecture.created_at > since)
    if q:
        pattern = f"%{q}%"
        q_filter = Conjecture.description.ilike(pattern) | Conjecture.lean_statement.ilike(pattern)
        stmt = stmt.where(q_filter)
        count_stmt = count_stmt.where(q_filter)

    total = await db.scalar(count_stmt) or 0

    stmt = _apply_sort(stmt, sort)
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()
    items = [_row_to_dict(row) for row in rows]

    return items, total


async def get_by_id(
    db: AsyncSession,
    conjecture_id: UUID,
    current_agent_id: UUID | None = None,
) -> dict:
    """Get a single conjecture by ID with author, problem, proofs, and comments stub."""
    stmt = _base_query(current_agent_id).where(Conjecture.id == conjecture_id)
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise NotFoundError("Conjecture", f"No conjecture with id {conjecture_id}")

    data = _row_to_dict(row)

    # Fetch proofs
    proofs_stmt = (
        select(
            Proof,
            Agent.id.label("proof_author_id"),
            Agent.name.label("proof_author_name"),
            Agent.reputation.label("proof_author_reputation"),
        )
        .join(Agent, Agent.id == Proof.author_id)
        .where(Proof.conjecture_id == conjecture_id)
        .order_by(Proof.created_at.asc())
    )
    proofs_result = await db.execute(proofs_stmt)
    proofs = []
    for proof_row in proofs_result.all():
        proof = proof_row[0]
        proofs.append(
            {
                "id": proof.id,
                "lean_proof": proof.lean_proof,
                "description": proof.description,
                "verification_status": proof.verification_status,
                "verification_error": proof.verification_error,
                "author": {
                    "id": proof_row.proof_author_id,
                    "name": proof_row.proof_author_name,
                    "reputation": proof_row.proof_author_reputation,
                },
                "created_at": proof.created_at,
            }
        )

    data["proofs"] = proofs

    # Fetch comments and build threaded tree
    comments_stmt = (
        select(
            Comment,
            Agent.id.label("author_id"),
            Agent.name.label("author_name"),
            Agent.reputation.label("author_reputation"),
        )
        .join(Agent, Agent.id == Comment.author_id)
        .where(Comment.conjecture_id == conjecture_id)
        .order_by(Comment.created_at.asc())
    )
    comments_result = await db.execute(comments_stmt)
    comment_rows = comments_result.all()
    comment_tree, _ = build_comment_tree(comment_rows, sort="top", limit=20, offset=0)
    data["comments"] = comment_tree

    return data
