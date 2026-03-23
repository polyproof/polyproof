"""Problem CRUD with computed progress."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.problem import Problem


async def create(
    db: AsyncSession,
    title: str,
    description: str,
    root_lean_statement: str,
    root_description: str,
    lean_header: str | None = None,
) -> tuple[Problem, Conjecture]:
    """Create a problem with its root conjecture.

    Lean typechecking must be done before calling this.
    Returns (problem, root_conjecture).
    """
    problem = Problem(title=title, description=description, lean_header=lean_header)
    db.add(problem)
    await db.flush()

    root = Conjecture(
        project_id=problem.id,
        parent_id=None,
        lean_statement=root_lean_statement,
        description=root_description,
        status="open",
        priority="critical",
    )
    db.add(root)
    await db.flush()

    problem.root_conjecture_id = root.id
    await db.flush()

    return problem, root


async def list_problems(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """List problems with computed progress.

    Returns (problem_dicts, total_count).
    """
    total = await db.scalar(select(func.count()).select_from(Problem))
    total = total or 0

    problems = (
        await db.scalars(
            select(Problem).order_by(Problem.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    problem_ids = [p.id for p in problems]
    comment_counts = await _batch_comment_counts(db, problem_ids)
    active_agent_counts = await _batch_active_agent_counts(db, problem_ids)

    result = []
    for p in problems:
        stats = await _compute_progress(db, p.root_conjecture_id)
        root_status = await _get_root_status(db, p.root_conjecture_id)
        last_activity = await _get_last_activity(db, p.id)
        result.append(
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "root_conjecture_id": p.root_conjecture_id,
                "progress": stats["progress"],
                "root_status": root_status,
                "total_leaves": stats["total_leaves"],
                "proved_leaves": stats["proved_leaves"],
                "last_activity_at": last_activity,
                "comment_count": comment_counts.get(p.id, 0),
                "active_agent_count": active_agent_counts.get(p.id, 0),
                "created_at": p.created_at,
            }
        )

    return result, total


async def get_by_id(db: AsyncSession, problem_id: UUID) -> Problem | None:
    """Get a problem by ID."""
    return await db.get(Problem, problem_id)


async def get_detail(db: AsyncSession, problem: Problem) -> dict:
    """Get problem detail with full stats."""
    stats = await _compute_progress(db, problem.root_conjecture_id)
    status_counts = await _count_by_status(db, problem.id)
    root_status = await _get_root_status(db, problem.root_conjecture_id)
    last_activity = await _get_last_activity(db, problem.id)

    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "root_conjecture_id": problem.root_conjecture_id,
        "progress": stats["progress"],
        "root_status": root_status,
        "total_conjectures": sum(status_counts.values()),
        "proved_conjectures": status_counts.get("proved", 0),
        "open_conjectures": status_counts.get("open", 0),
        "decomposed_conjectures": status_counts.get("decomposed", 0),
        "disproved_conjectures": status_counts.get("disproved", 0),
        "invalid_conjectures": status_counts.get("invalid", 0),
        "total_leaves": stats["total_leaves"],
        "proved_leaves": stats["proved_leaves"],
        "last_activity_at": last_activity,
        "created_at": problem.created_at,
    }


async def _compute_progress(db: AsyncSession, root_conjecture_id: UUID | None) -> dict:
    """Compute progress using recursive CTE to count leaves."""
    if root_conjecture_id is None:
        return {"total_leaves": 0, "proved_leaves": 0, "progress": 0.0}

    query = text("""
        WITH RECURSIVE tree AS (
            SELECT id, status
            FROM conjectures WHERE id = :root_id
            UNION ALL
            SELECT c.id, c.status
            FROM conjectures c JOIN tree t ON c.parent_id = t.id
            WHERE c.status != 'invalid'
        ),
        leaves AS (
            SELECT t.id, t.status
            FROM tree t
            WHERE NOT EXISTS (
                SELECT 1 FROM conjectures ch
                WHERE ch.parent_id = t.id AND ch.status != 'invalid'
            )
        )
        SELECT
            COUNT(*) AS total_leaves,
            COUNT(*) FILTER (WHERE status = 'proved') AS proved_leaves
        FROM leaves
    """)
    result = await db.execute(query, {"root_id": str(root_conjecture_id)})
    row = result.one()
    total = row.total_leaves or 0
    proved = row.proved_leaves or 0
    progress = proved / total if total > 0 else 0.0
    return {"total_leaves": total, "proved_leaves": proved, "progress": progress}


async def _count_by_status(db: AsyncSession, problem_id: UUID) -> dict[str, int]:
    """Count conjectures by status for a problem."""
    result = await db.execute(
        select(Conjecture.status, func.count())
        .where(Conjecture.project_id == problem_id)
        .group_by(Conjecture.status)
    )
    return dict(result.all())


async def _get_root_status(db: AsyncSession, root_id: UUID | None) -> str | None:
    """Get the status of the root conjecture."""
    if root_id is None:
        return None
    root = await db.get(Conjecture, root_id)
    return root.status if root else None


async def _get_last_activity(db: AsyncSession, problem_id: UUID) -> datetime | None:
    """Get the timestamp of the latest activity for a problem.

    Checks both comments and activity_log.
    """
    # Check latest comment on conjectures in this problem or directly on the problem
    conj_comment_q = (
        select(func.max(Comment.created_at))
        .join(Conjecture, Comment.conjecture_id == Conjecture.id)
        .where(Conjecture.project_id == problem_id)
    )
    prob_comment_q = select(func.max(Comment.created_at)).where(Comment.project_id == problem_id)
    activity_q = select(func.max(ActivityLog.created_at)).where(
        ActivityLog.project_id == problem_id
    )

    conj_ts = await db.scalar(conj_comment_q)
    proj_ts = await db.scalar(prob_comment_q)
    act_ts = await db.scalar(activity_q)

    timestamps = [ts for ts in [conj_ts, proj_ts, act_ts] if ts is not None]
    return max(timestamps) if timestamps else None


async def _batch_comment_counts(db: AsyncSession, problem_ids: list[UUID]) -> dict[UUID, int]:
    """Total comments for multiple problems in two queries instead of 2*N."""
    if not problem_ids:
        return {}

    # Problem-level comments
    prob_rows = await db.execute(
        select(Comment.project_id, func.count())
        .where(Comment.project_id.in_(problem_ids))
        .group_by(Comment.project_id)
    )
    counts: dict[UUID, int] = dict(prob_rows.all())

    # Conjecture-level comments
    conj_rows = await db.execute(
        select(Conjecture.project_id, func.count())
        .select_from(Comment)
        .join(Conjecture, Comment.conjecture_id == Conjecture.id)
        .where(Conjecture.project_id.in_(problem_ids))
        .group_by(Conjecture.project_id)
    )
    for pid, cnt in conj_rows.all():
        counts[pid] = counts.get(pid, 0) + cnt

    return counts


async def _batch_active_agent_counts(db: AsyncSession, problem_ids: list[UUID]) -> dict[UUID, int]:
    """Distinct active agents for multiple problems in one query."""
    if not problem_ids:
        return {}

    rows = await db.execute(
        select(
            ActivityLog.project_id,
            func.count(func.distinct(ActivityLog.agent_id)),
        )
        .where(
            ActivityLog.project_id.in_(problem_ids),
            ActivityLog.agent_id.is_not(None),
        )
        .group_by(ActivityLog.project_id)
    )
    return dict(rows.all())


async def get_overview(db: AsyncSession, problem: Problem) -> dict:
    """Build the problem overview: problem summary + flat tree with per-node metrics.

    Each node includes: description, status, priority, comment_count,
    last_activity_at, proved_by (agent handle), parent_id, summary (latest is_summary comment body).
    """
    stats = await _compute_progress(db, problem.root_conjecture_id)
    root_status = await _get_root_status(db, problem.root_conjecture_id)

    problem_data = {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "status": root_status or "open",
        "progress": stats["progress"],
    }

    if not problem.root_conjecture_id:
        return {"problem": problem_data, "tree": []}

    # Fetch all conjectures in the tree (including invalid, for visibility)
    tree_query = text("""
        WITH RECURSIVE tree AS (
            SELECT id, parent_id, description, status, priority, proved_by, created_at
            FROM conjectures WHERE id = :root_id
            UNION ALL
            SELECT c.id, c.parent_id, c.description, c.status, c.priority, c.proved_by, c.created_at
            FROM conjectures c JOIN tree t ON c.parent_id = t.id
        )
        SELECT * FROM tree
    """)
    result = await db.execute(tree_query, {"root_id": str(problem.root_conjecture_id)})
    rows = result.all()

    conjecture_ids = [row.id for row in rows]

    # Batch: comment counts
    comment_counts: dict[UUID, int] = {}
    if conjecture_ids:
        cc_result = await db.execute(
            select(Comment.conjecture_id, func.count())
            .where(Comment.conjecture_id.in_(conjecture_ids))
            .group_by(Comment.conjecture_id)
        )
        comment_counts = dict(cc_result.all())

    # Batch: last activity per conjecture (from activity_log)
    last_activities: dict[UUID, datetime] = {}
    if conjecture_ids:
        la_result = await db.execute(
            select(ActivityLog.conjecture_id, func.max(ActivityLog.created_at))
            .where(ActivityLog.conjecture_id.in_(conjecture_ids))
            .group_by(ActivityLog.conjecture_id)
        )
        last_activities = dict(la_result.all())

    # Batch: latest is_summary comment body per conjecture
    summaries: dict[UUID, str] = {}
    if conjecture_ids:
        # Use a lateral join / window function to get latest summary per conjecture
        summary_query = text("""
            SELECT DISTINCT ON (conjecture_id)
                conjecture_id, body
            FROM comments
            WHERE conjecture_id = ANY(:ids) AND is_summary = true
            ORDER BY conjecture_id, created_at DESC
        """)
        s_result = await db.execute(summary_query, {"ids": conjecture_ids})
        for s_row in s_result.all():
            summaries[s_row.conjecture_id] = s_row.body

    # Batch: proved_by agent handles
    proved_by_ids = {row.proved_by for row in rows if row.proved_by is not None}
    agent_handles: dict[UUID, str] = {}
    if proved_by_ids:
        agents_result = await db.execute(
            select(Agent.id, Agent.handle).where(Agent.id.in_(proved_by_ids))
        )
        agent_handles = dict(agents_result.all())

    # Build flat tree
    tree_nodes = []
    for row in rows:
        tree_nodes.append(
            {
                "id": row.id,
                "description": row.description,
                "status": row.status,
                "priority": row.priority,
                "comment_count": comment_counts.get(row.id, 0),
                "last_activity_at": last_activities.get(row.id),
                "proved_by": agent_handles.get(row.proved_by) if row.proved_by else None,
                "parent_id": row.parent_id,
                "summary": summaries.get(row.id),
            }
        )

    return {"problem": problem_data, "tree": tree_nodes}
