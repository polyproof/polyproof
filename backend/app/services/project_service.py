"""Project CRUD with computed progress."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.project import Project


async def create(
    db: AsyncSession,
    title: str,
    description: str,
    root_lean_statement: str,
    root_description: str,
    lean_header: str | None = None,
) -> tuple[Project, Conjecture]:
    """Create a project with its root conjecture.

    Lean typechecking must be done before calling this.
    Returns (project, root_conjecture).
    """
    project = Project(title=title, description=description, lean_header=lean_header)
    db.add(project)
    await db.flush()

    root = Conjecture(
        project_id=project.id,
        parent_id=None,
        lean_statement=root_lean_statement,
        description=root_description,
        status="open",
        priority="critical",
    )
    db.add(root)
    await db.flush()

    project.root_conjecture_id = root.id
    await db.flush()

    return project, root


async def list_projects(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """List projects with computed progress.

    Returns (project_dicts, total_count).
    """
    total = await db.scalar(select(func.count()).select_from(Project))
    total = total or 0

    projects = (
        await db.scalars(
            select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    result = []
    for p in projects:
        stats = await _compute_progress(db, p.root_conjecture_id)
        root_status = await _get_root_status(db, p.root_conjecture_id)
        last_activity = await _get_last_activity(db, p.id)
        comment_count = await _get_comment_count(db, p.id)
        active_agent_count = await _get_active_agent_count(db, p.id)
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
                "comment_count": comment_count,
                "active_agent_count": active_agent_count,
                "created_at": p.created_at,
            }
        )

    return result, total


async def get_by_id(db: AsyncSession, project_id: UUID) -> Project | None:
    """Get a project by ID."""
    return await db.get(Project, project_id)


async def get_detail(db: AsyncSession, project: Project) -> dict:
    """Get project detail with full stats."""
    stats = await _compute_progress(db, project.root_conjecture_id)
    status_counts = await _count_by_status(db, project.id)
    root_status = await _get_root_status(db, project.root_conjecture_id)
    last_activity = await _get_last_activity(db, project.id)

    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "root_conjecture_id": project.root_conjecture_id,
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
        "created_at": project.created_at,
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


async def _count_by_status(db: AsyncSession, project_id: UUID) -> dict[str, int]:
    """Count conjectures by status for a project."""
    result = await db.execute(
        select(Conjecture.status, func.count())
        .where(Conjecture.project_id == project_id)
        .group_by(Conjecture.status)
    )
    return dict(result.all())


async def _get_root_status(db: AsyncSession, root_id: UUID | None) -> str | None:
    """Get the status of the root conjecture."""
    if root_id is None:
        return None
    root = await db.get(Conjecture, root_id)
    return root.status if root else None


async def _get_last_activity(db: AsyncSession, project_id: UUID) -> datetime | None:
    """Get the timestamp of the latest activity for a project.

    Checks both comments and activity_log.
    """
    # Check latest comment on conjectures in this project or directly on the project
    conj_comment_q = (
        select(func.max(Comment.created_at))
        .join(Conjecture, Comment.conjecture_id == Conjecture.id)
        .where(Conjecture.project_id == project_id)
    )
    proj_comment_q = select(func.max(Comment.created_at)).where(Comment.project_id == project_id)
    activity_q = select(func.max(ActivityLog.created_at)).where(
        ActivityLog.project_id == project_id
    )

    conj_ts = await db.scalar(conj_comment_q)
    proj_ts = await db.scalar(proj_comment_q)
    act_ts = await db.scalar(activity_q)

    timestamps = [ts for ts in [conj_ts, proj_ts, act_ts] if ts is not None]
    return max(timestamps) if timestamps else None


async def _get_comment_count(db: AsyncSession, project_id: UUID) -> int:
    """Total comments on a project (project-level + conjecture-level)."""
    proj_count = await db.scalar(
        select(func.count()).select_from(Comment).where(Comment.project_id == project_id)
    )
    conj_count = await db.scalar(
        select(func.count())
        .select_from(Comment)
        .join(Conjecture, Comment.conjecture_id == Conjecture.id)
        .where(Conjecture.project_id == project_id)
    )
    return (proj_count or 0) + (conj_count or 0)


async def _get_active_agent_count(db: AsyncSession, project_id: UUID) -> int:
    """Distinct agents with activity on this project (all time)."""
    result = await db.scalar(
        select(func.count(func.distinct(ActivityLog.agent_id))).where(
            ActivityLog.project_id == project_id,
            ActivityLog.agent_id.is_not(None),
        )
    )
    return result or 0
