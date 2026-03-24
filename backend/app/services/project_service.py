"""Project CRUD with computed sorry progress."""

import hashlib
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.project import Project
from app.models.sorry import Sorry
from app.models.tracked_file import TrackedFile


async def create(db: AsyncSession, data: dict) -> Project:
    """Create a project with its tracked files.

    Expects data with keys: title, description, upstream_repo, upstream_branch,
    fork_repo, fork_branch, lean_toolchain, workspace_path, tracked_files.
    Returns the created Project.
    """
    project = Project(
        title=data["title"],
        description=data["description"],
        upstream_repo=data["upstream_repo"],
        upstream_branch=data.get("upstream_branch", "master"),
        fork_repo=data["fork_repo"],
        fork_branch=data.get("fork_branch", "polyproof"),
        lean_toolchain=data["lean_toolchain"],
        workspace_path=data["workspace_path"],
    )
    db.add(project)
    await db.flush()

    for file_path in data.get("tracked_files", []):
        tracked = TrackedFile(
            project_id=project.id,
            file_path=file_path,
        )
        db.add(tracked)

    await db.flush()
    return project


async def list_projects(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """List projects with computed sorry counts.

    Returns (project_dicts, total_count).
    """
    total = await db.scalar(select(func.count()).select_from(Project))
    total = total or 0

    projects = (
        await db.scalars(
            select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    project_ids = [p.id for p in projects]
    sorry_stats = await _batch_sorry_stats(db, project_ids)
    activity_stats = await _batch_activity_stats(db, project_ids)

    result = []
    for p in projects:
        stats = sorry_stats.get(p.id, {"total": 0, "filled": 0})
        empty_stats = {"agent_count": 0, "comment_count": 0, "last_activity_at": None}
        a_stats = activity_stats.get(p.id, empty_stats)
        total_sorries = stats["total"]
        filled_sorries = stats["filled"]
        progress = filled_sorries / total_sorries if total_sorries > 0 else 0.0

        result.append(
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "upstream_repo": p.upstream_repo,
                "fork_repo": p.fork_repo,
                "fork_branch": p.fork_branch,
                "lean_toolchain": p.lean_toolchain,
                "total_sorries": total_sorries,
                "filled_sorries": filled_sorries,
                "progress": progress,
                "agent_count": a_stats["agent_count"],
                "comment_count": a_stats["comment_count"],
                "last_activity_at": a_stats["last_activity_at"],
                "created_at": p.created_at,
            }
        )

    return result, total


async def get_by_id(db: AsyncSession, project_id: UUID) -> Project | None:
    """Get a project by ID."""
    return await db.get(Project, project_id)


async def get_detail(db: AsyncSession, project: Project) -> dict:
    """Get project detail with file list and sorry breakdowns."""
    status_counts = await _count_by_status(db, project.id)
    total_sorries = sum(status_counts.values())
    filled_sorries = status_counts.get("filled", 0) + status_counts.get("filled_externally", 0)
    progress = filled_sorries / total_sorries if total_sorries > 0 else 0.0

    activity_stats = await _batch_activity_stats(db, [project.id])
    empty_stats = {"agent_count": 0, "comment_count": 0, "last_activity_at": None}
    a_stats = activity_stats.get(project.id, empty_stats)

    files = (
        await db.scalars(
            select(TrackedFile)
            .where(TrackedFile.project_id == project.id)
            .order_by(TrackedFile.file_path.asc())
        )
    ).all()

    file_dicts = [
        {
            "id": f.id,
            "file_path": f.file_path,
            "sorry_count": f.sorry_count,
            "last_compiled_at": f.last_compiled_at,
        }
        for f in files
    ]

    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "upstream_repo": project.upstream_repo,
        "upstream_branch": project.upstream_branch,
        "fork_repo": project.fork_repo,
        "fork_branch": project.fork_branch,
        "lean_toolchain": project.lean_toolchain,
        "current_commit": project.current_commit,
        "upstream_commit": project.upstream_commit,
        "workspace_path": project.workspace_path,
        "total_sorries": total_sorries,
        "filled_sorries": filled_sorries,
        "progress": progress,
        "agent_count": a_stats["agent_count"],
        "comment_count": a_stats["comment_count"],
        "last_activity_at": a_stats["last_activity_at"],
        "open_sorries": status_counts.get("open", 0),
        "decomposed_sorries": status_counts.get("decomposed", 0),
        "filled_externally_sorries": status_counts.get("filled_externally", 0),
        "invalid_sorries": status_counts.get("invalid", 0),
        "files": file_dicts,
        "created_at": project.created_at,
    }


async def get_overview(db: AsyncSession, project: Project) -> dict:
    """Build the project overview: project summary + all sorries with goal states.

    Used by agents to browse available work. Each sorry includes its goal_state,
    status, priority, file_path, and comment_count.
    """
    sorry_stats = await _batch_sorry_stats(db, [project.id])
    stats = sorry_stats.get(project.id, {"total": 0, "filled": 0})
    total_sorries = stats["total"]
    filled_sorries = stats["filled"]
    progress = filled_sorries / total_sorries if total_sorries > 0 else 0.0

    activity_stats = await _batch_activity_stats(db, [project.id])
    empty_stats = {"agent_count": 0, "comment_count": 0, "last_activity_at": None}
    a_stats = activity_stats.get(project.id, empty_stats)

    project_data = {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "upstream_repo": project.upstream_repo,
        "fork_repo": project.fork_repo,
        "fork_branch": project.fork_branch,
        "lean_toolchain": project.lean_toolchain,
        "total_sorries": total_sorries,
        "filled_sorries": filled_sorries,
        "progress": progress,
        "agent_count": a_stats["agent_count"],
        "comment_count": a_stats["comment_count"],
        "last_activity_at": a_stats["last_activity_at"],
        "created_at": project.created_at,
    }

    # Fetch all non-invalid sorries with file paths
    result = await db.execute(
        select(Sorry, TrackedFile.file_path)
        .join(TrackedFile, Sorry.file_id == TrackedFile.id)
        .where(
            Sorry.project_id == project.id,
            Sorry.status != "invalid",
        )
        .order_by(
            TrackedFile.file_path.asc(),
            Sorry.declaration_name.asc(),
            Sorry.sorry_index.asc(),
        )
    )
    rows = result.all()

    sorry_ids = [row[0].id for row in rows]

    # Batch: comment counts
    comment_counts: dict[UUID, int] = {}
    if sorry_ids:
        cc_result = await db.execute(
            select(Comment.sorry_id, func.count())
            .where(Comment.sorry_id.in_(sorry_ids))
            .group_by(Comment.sorry_id)
        )
        comment_counts = dict(cc_result.all())

    # Batch: filled_by agent handles
    filled_by_ids = {row[0].filled_by for row in rows if row[0].filled_by is not None}
    agent_handles: dict[UUID, str] = {}
    if filled_by_ids:
        agents_result = await db.execute(
            select(Agent.id, Agent.handle).where(Agent.id.in_(filled_by_ids))
        )
        agent_handles = dict(agents_result.all())

    sorries = []
    for sorry, file_path in rows:
        sorries.append(
            {
                "id": sorry.id,
                "declaration_name": sorry.declaration_name,
                "sorry_index": sorry.sorry_index,
                "goal_state": sorry.goal_state,
                "status": sorry.status,
                "priority": sorry.priority,
                "active_agents": sorry.active_agents,
                "filled_by_handle": agent_handles.get(sorry.filled_by) if sorry.filled_by else None,
                "file_path": file_path,
                "comment_count": comment_counts.get(sorry.id, 0),
            }
        )

    return {"project": project_data, "sorries": sorries}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _count_by_status(db: AsyncSession, project_id: UUID) -> dict[str, int]:
    """Count sorries by status for a project."""
    result = await db.execute(
        select(Sorry.status, func.count())
        .where(Sorry.project_id == project_id)
        .group_by(Sorry.status)
    )
    return dict(result.all())


async def _batch_activity_stats(
    db: AsyncSession, project_ids: list[UUID]
) -> dict[UUID, dict]:
    """Batch compute agent count, comment count, and last activity per project."""
    if not project_ids:
        return {}

    stats: dict[UUID, dict] = {}
    _default = {"agent_count": 0, "comment_count": 0, "last_activity_at": None}

    # Unique agents + last activity per project (single activity_log query)
    activity_result = await db.execute(
        select(
            ActivityLog.project_id,
            func.count(
                func.distinct(ActivityLog.agent_id)
            ).filter(ActivityLog.agent_id.is_not(None)),
            func.max(ActivityLog.created_at),
        )
        .where(ActivityLog.project_id.in_(project_ids))
        .group_by(ActivityLog.project_id)
    )
    for pid, agent_count, last_at in activity_result.all():
        stats.setdefault(pid, {**_default})
        stats[pid]["agent_count"] = agent_count
        stats[pid]["last_activity_at"] = last_at

    # Comment counts per project (project-level + sorry-level)
    sorry_comment_q = (
        select(
            Sorry.project_id.label("pid"),
            func.count().label("cnt"),
        )
        .select_from(Comment)
        .join(Sorry, Comment.sorry_id == Sorry.id)
        .where(
            Sorry.project_id.in_(project_ids),
            Comment.sorry_id.is_not(None),
        )
        .group_by(Sorry.project_id)
    )
    project_comment_q = (
        select(
            Comment.project_id.label("pid"),
            func.count().label("cnt"),
        )
        .where(
            Comment.project_id.in_(project_ids),
            Comment.project_id.is_not(None),
        )
        .group_by(Comment.project_id)
    )
    combined = sorry_comment_q.union_all(project_comment_q).subquery()
    comment_result = await db.execute(
        select(combined.c.pid, func.sum(combined.c.cnt))
        .group_by(combined.c.pid)
    )
    for pid, count in comment_result.all():
        stats.setdefault(pid, {**_default})
        stats[pid]["comment_count"] = count

    return stats


async def _batch_sorry_stats(
    db: AsyncSession, project_ids: list[UUID]
) -> dict[UUID, dict[str, int]]:
    """Batch compute total and filled sorry counts per project."""
    if not project_ids:
        return {}

    result = await db.execute(
        select(
            Sorry.project_id,
            func.count().label("total"),
            func.count().filter(
                Sorry.status.in_(["filled", "filled_externally"])
            ).label("filled"),
        )
        .where(
            Sorry.project_id.in_(project_ids),
            Sorry.status != "invalid",
        )
        .group_by(Sorry.project_id)
    )

    stats: dict[UUID, dict[str, int]] = {}
    for row in result.all():
        stats[row[0]] = {"total": row[1], "filled": row[2]}
    return stats


async def import_sorries(
    db: AsyncSession, project_id: UUID, sorries: list[dict]
) -> dict:
    """Bulk-import sorry records for a project.

    Each dict in ``sorries`` should have:
      file_path, declaration_name, sorry_index (default 0),
      goal_state, local_context (optional), line (optional), col (optional),
      priority (default "normal").

    Creates TrackedFile records as needed.  Returns counts.
    """
    # Build file_path -> TrackedFile mapping (create if needed)
    file_paths = {s["file_path"] for s in sorries}
    existing = (
        await db.scalars(
            select(TrackedFile).where(
                TrackedFile.project_id == project_id,
                TrackedFile.file_path.in_(file_paths),
            )
        )
    ).all()
    file_map: dict[str, TrackedFile] = {tf.file_path: tf for tf in existing}

    for fp in file_paths:
        if fp not in file_map:
            tf = TrackedFile(project_id=project_id, file_path=fp)
            db.add(tf)
            await db.flush()
            file_map[fp] = tf

    created = 0
    skipped = 0
    for s in sorries:
        tf = file_map[s["file_path"]]
        goal = s["goal_state"]
        goal_hash = hashlib.sha256(goal.encode()).hexdigest()[:16]
        sorry_index = s.get("sorry_index", 0)
        decl = s["declaration_name"]

        # Check for existing sorry with same identity
        exists = await db.scalar(
            select(func.count()).select_from(Sorry).where(
                Sorry.file_id == tf.id,
                Sorry.declaration_name == decl,
                Sorry.sorry_index == sorry_index,
                Sorry.goal_hash == goal_hash,
                Sorry.status.notin_(["invalid", "filled", "filled_externally"]),
            )
        )
        if exists:
            skipped += 1
            continue

        sorry = Sorry(
            file_id=tf.id,
            project_id=project_id,
            declaration_name=decl,
            sorry_index=sorry_index,
            goal_state=goal,
            local_context=s.get("local_context"),
            goal_hash=goal_hash,
            priority=s.get("priority", "normal"),
            line=s.get("line"),
            col=s.get("col"),
        )
        db.add(sorry)
        created += 1

    await db.flush()

    # Update sorry counts on tracked files
    for tf in file_map.values():
        count = await db.scalar(
            select(func.count()).select_from(Sorry).where(
                Sorry.file_id == tf.id,
                Sorry.status.notin_(["invalid"]),
            )
        )
        await db.execute(
            text("UPDATE tracked_files SET sorry_count = :count WHERE id = :id"),
            {"count": count or 0, "id": str(tf.id)},
        )

    await db.flush()
    return {"status": "ok", "created": created, "skipped": skipped}
