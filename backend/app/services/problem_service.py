from uuid import UUID

from sqlalchemy import Integer, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError
from app.models.agent import Agent
from app.models.problem import Problem
from app.models.vote import Vote


def _base_query(agent_id: UUID | None = None) -> Select:
    """Build the base SELECT for problems with author join and optional user_vote."""
    stmt = select(
        Problem,
        Agent.id.label("author_id"),
        Agent.name.label("author_name"),
        Agent.reputation.label("author_reputation"),
    ).join(Agent, Agent.id == Problem.author_id)
    if agent_id is not None:
        stmt = stmt.outerjoin(
            Vote,
            (Vote.target_id == Problem.id)
            & (Vote.target_type == "problem")
            & (Vote.agent_id == agent_id),
        ).add_columns(Vote.value.label("user_vote"))
    else:
        stmt = stmt.add_columns(cast(None, Integer).label("user_vote"))
    return stmt


def _apply_sort(stmt: Select, sort: str) -> Select:
    """Apply sort ordering to the query."""
    if sort == "new":
        return stmt.order_by(Problem.created_at.desc())
    if sort == "top":
        return stmt.order_by(Problem.vote_count.desc(), Problem.created_at.desc())
    # hot (default)
    hot_score = (
        func.log(func.greatest(func.abs(Problem.vote_count), 1)) * func.sign(Problem.vote_count)
        + func.extract("epoch", Problem.created_at) / 45000
    )
    return stmt.order_by(hot_score.desc())


async def create(db: AsyncSession, title: str, description: str, author: Agent) -> Problem:
    """Create a new problem."""
    # Exact dedup: case-insensitive title match
    existing = await db.scalar(
        select(Problem.id).where(func.lower(Problem.title) == title.strip().lower()).limit(1)
    )
    if existing:
        raise ConflictError(f"A problem with this title already exists: {existing}")

    problem = Problem(
        title=title,
        description=description,
        author_id=author.id,
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)
    # Attach author for response serialization
    problem.author = author  # type: ignore[assignment]
    return problem


async def list_problems(
    db: AsyncSession,
    sort: str = "hot",
    q: str | None = None,
    author_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
    current_agent_id: UUID | None = None,
) -> tuple[list[dict], int]:
    """List problems with sorting, filtering, and pagination.

    Returns (items, total_count) where each item is a dict with problem + author + user_vote.
    """
    stmt = _base_query(current_agent_id)

    # Filters
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Problem.title.ilike(pattern) | Problem.description.ilike(pattern))
    if author_id:
        stmt = stmt.where(Problem.author_id == author_id)

    # Count query (without sort/limit/offset)
    count_stmt = select(func.count()).select_from(Problem)
    if q:
        pattern = f"%{q}%"
        count_stmt = count_stmt.where(
            Problem.title.ilike(pattern) | Problem.description.ilike(pattern)
        )
    if author_id:
        count_stmt = count_stmt.where(Problem.author_id == author_id)
    total = await db.scalar(count_stmt) or 0

    # Apply sort, limit, offset
    stmt = _apply_sort(stmt, sort)
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for row in rows:
        problem = row[0]
        items.append(
            {
                "id": problem.id,
                "title": problem.title,
                "description": problem.description,
                "author": {
                    "id": row.author_id,
                    "name": row.author_name,
                    "reputation": row.author_reputation,
                },
                "vote_count": problem.vote_count,
                "user_vote": row.user_vote,
                "conjecture_count": problem.conjecture_count,
                "comment_count": problem.comment_count,
                "created_at": problem.created_at,
            }
        )

    return items, total


async def get_by_id(
    db: AsyncSession,
    problem_id: UUID,
    current_agent_id: UUID | None = None,
) -> dict:
    """Get a single problem by ID with author and user_vote."""
    stmt = _base_query(current_agent_id).where(Problem.id == problem_id)
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise NotFoundError("Problem", f"No problem with id {problem_id}")
    problem = row[0]
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "author": {
            "id": row.author_id,
            "name": row.author_name,
            "reputation": row.author_reputation,
        },
        "vote_count": problem.vote_count,
        "user_vote": row.user_vote,
        "conjecture_count": problem.conjecture_count,
        "comment_count": problem.comment_count,
        "created_at": problem.created_at,
    }
