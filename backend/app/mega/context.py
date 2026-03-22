"""Build the context packet for a mega agent invocation.

The context packet is a structured text document passed as the `input`
parameter to the OpenAI Responses API. It contains the full proof tree,
recent activity, summaries, and stuck nodes.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.project import Project

logger = logging.getLogger(__name__)


async def build_context_packet(
    project_id: UUID,
    trigger: dict,
    db: AsyncSession,
) -> str:
    """Build the full context packet for a mega agent invocation.

    Sections:
    - PROJECT: title, description, root statement, progress
    - TRIGGER: type and details
    - PROOF TREE: all non-invalid conjectures with stats
    - RECENT ACTIVITY: comments, proofs, disproofs, assemblies since last invocation
    - PROJECT SUMMARY: latest is_summary comment on the project
    - CONJECTURE SUMMARIES: per-conjecture summaries for active nodes
    - STUCK NODES: open conjectures with no activity in 48+ hours
    """
    project = await db.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    root = await db.get(Conjecture, project.root_conjecture_id)
    if not root:
        raise ValueError(f"Root conjecture not found for project {project_id}")

    sections = []

    # --- PROJECT section ---
    progress = await _compute_progress(project_id, db)
    sections.append(
        f"PROJECT\n\n"
        f"Title: {project.title}\n"
        f"Description: {project.description}\n"
        f"Root: {root.lean_statement}\n"
        f"Root status: {root.status}\n"
        f"Progress: {progress['proved']}/{progress['total']} leaves proved "
        f"({progress['percentage']:.0f}%)"
    )

    # --- TRIGGER section ---
    trigger_type = trigger.get("trigger", "unknown")
    trigger_details = _format_trigger(trigger_type, trigger)
    sections.append(f"TRIGGER\n\n{trigger_type}: {trigger_details}")

    # --- PROOF TREE section ---
    tree_text = await _build_proof_tree(project_id, project.root_conjecture_id, db)
    sections.append(f"PROOF TREE\n\n{tree_text}")

    # --- RECENT ACTIVITY section ---
    last_invocation = project.last_mega_invocation
    activity_text = await _build_recent_activity(project_id, last_invocation, db)
    sections.append(f"RECENT ACTIVITY (since start of your last invocation)\n\n{activity_text}")

    # --- PROJECT SUMMARY section ---
    project_summary = await _get_project_summary(project_id, db)
    sections.append(f"PROJECT SUMMARY\n\n{project_summary}")

    # --- CONJECTURE SUMMARIES section ---
    conj_summaries = await _build_conjecture_summaries(project_id, last_invocation, db)
    sections.append(f"CONJECTURE SUMMARIES (active nodes only)\n\n{conj_summaries}")

    # --- STUCK NODES section ---
    stuck_text = await _build_stuck_nodes(project_id, db)
    sections.append(f"STUCK NODES (open, no progress in 48+ hours)\n\n{stuck_text}")

    return "\n\n".join(sections)


async def _compute_progress(project_id: UUID, db: AsyncSession) -> dict:
    """Count total leaves and proved leaves for progress display."""
    # Leaves are conjectures with no non-invalid children
    all_conjectures = await db.execute(
        select(Conjecture.id, Conjecture.status).where(
            Conjecture.project_id == project_id,
            Conjecture.status != "invalid",
        )
    )
    rows = all_conjectures.all()

    # Get parent_ids of non-invalid conjectures
    parent_ids_result = await db.execute(
        select(Conjecture.parent_id)
        .where(
            Conjecture.project_id == project_id,
            Conjecture.status != "invalid",
            Conjecture.parent_id.isnot(None),
        )
        .distinct()
    )
    parent_ids = {r[0] for r in parent_ids_result.all()}

    # Leaves are conjectures that are not parents of any non-invalid child
    leaves = [r for r in rows if r.id not in parent_ids]
    total = len(leaves)
    proved = sum(1 for r in leaves if r.status == "proved")
    percentage = (proved / total * 100) if total > 0 else 0

    return {"total": total, "proved": proved, "percentage": percentage}


def _format_trigger(trigger_type: str, trigger: dict) -> str:
    """Format trigger details for the context packet."""
    if trigger_type == "project_created":
        return "New project. Study the root and bootstrap."
    elif trigger_type == "activity_threshold":
        count = trigger.get("activity_count", "N")
        return f"{count} interactions since your last invocation."
    elif trigger_type == "periodic_heartbeat":
        return "24 hours since last invocation. No activity threshold fired."
    elif trigger_type == "project_completed":
        return (
            "The root conjecture has been PROVED. The project is complete. "
            "Write a final retrospective summary."
        )
    return f"Unknown trigger: {trigger_type}"


async def _build_proof_tree(
    project_id: UUID,
    root_conjecture_id: UUID,
    db: AsyncSession,
) -> str:
    """Build a text representation of the proof tree using recursive CTE."""
    # Fetch all non-invalid conjectures for the project, ordered by depth
    tree_query = text("""
        WITH RECURSIVE tree AS (
            SELECT id, parent_id, lean_statement, description, status, priority,
                   sorry_proof, proof_lean, proved_by, disproved_by,
                   0 as depth, created_at
            FROM conjectures WHERE id = :root_id
            UNION ALL
            SELECT c.id, c.parent_id, c.lean_statement, c.description, c.status, c.priority,
                   c.sorry_proof, c.proof_lean, c.proved_by, c.disproved_by,
                   t.depth + 1, c.created_at
            FROM conjectures c JOIN tree t ON c.parent_id = t.id
            WHERE c.status != 'invalid'
        )
        SELECT * FROM tree ORDER BY depth, created_at
    """)
    result = await db.execute(tree_query, {"root_id": str(root_conjecture_id)})
    nodes = result.mappings().all()

    if not nodes:
        return "(empty tree)"

    # Gather stats for each node
    lines = []
    for node in nodes:
        node_id = node["id"]
        depth = node["depth"]
        indent = "  " * depth
        is_root = depth == 0

        # Count children
        child_counts = await db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Conjecture.status == "proved").label("proved"),
                func.count().filter(Conjecture.status == "open").label("open_count"),
            ).where(
                Conjecture.parent_id == node_id,
                Conjecture.status != "invalid",
            )
        )
        cc = child_counts.mappings().first()
        child_count = cc["total"] if cc else 0
        proved_count = cc["proved"] if cc else 0
        open_count = cc["open_count"] if cc else 0

        # Count comments
        comment_count_result = await db.scalar(
            select(func.count()).where(Comment.conjecture_id == node_id)
        )
        comment_count = comment_count_result or 0

        # Last activity
        last_activity = await db.scalar(
            select(func.max(ActivityLog.created_at)).where(ActivityLog.conjecture_id == node_id)
        )
        if last_activity:
            days_ago = (datetime.now(UTC) - last_activity).total_seconds() / 86400
            activity_str = f"{days_ago:.1f}d ago"
        else:
            activity_str = "never"

        # Truncate lean_statement
        lean_stmt = node["lean_statement"][:120]
        desc = (node["description"] or "")[:200]
        status = node["status"]
        priority = node["priority"]

        prefix = "ROOT " if is_root else ""
        line = f'{indent}{prefix}{node_id} | {status} | priority:{priority} | "{lean_stmt}"'
        lines.append(line)
        lines.append(f"{indent}  Description: {desc}")

        if child_count > 0:
            lines.append(
                f"{indent}  Children: {child_count} ({proved_count} proved, {open_count} open)"
            )

        lines.append(f"{indent}  Comments: {comment_count} | Last activity: {activity_str}")

        if status == "proved" and node["proof_lean"]:
            proof_preview = node["proof_lean"][:200]
            proved_by = node["proved_by"]
            if proved_by:
                agent = await db.get(Agent, proved_by)
                handle = agent.handle if agent else "unknown"
                lines.append(f"{indent}  Proved by: {handle} | Proof: {proof_preview}")
            else:
                lines.append(f"{indent}  Proved by: (assembly) | Proof: {proof_preview}")

        if status == "disproved" and node["disproved_by"]:
            agent = await db.get(Agent, node["disproved_by"])
            handle = agent.handle if agent else "unknown"
            lines.append(f"{indent}  Disproved by: {handle}")

        if status == "decomposed" and node["sorry_proof"]:
            sorry_preview = node["sorry_proof"][:200]
            lines.append(f"{indent}  Sorry-proof: {sorry_preview}")

        if status == "invalid":
            lines.append(f"{indent}  Invalidated -- excluded from active work")

        lines.append("")  # blank line between nodes

    return "\n".join(lines)


async def _build_recent_activity(
    project_id: UUID,
    last_invocation: datetime | None,
    db: AsyncSession,
) -> str:
    """Build the RECENT ACTIVITY section from activity_log."""
    if last_invocation is None:
        # First invocation -- no prior activity
        return "(no prior invocation)"

    stmt = (
        select(ActivityLog, Agent.handle.label("agent_handle"))
        .outerjoin(Agent, ActivityLog.agent_id == Agent.id)
        .where(
            ActivityLog.project_id == project_id,
            ActivityLog.created_at > last_invocation,
        )
        .order_by(ActivityLog.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return "(no activity since last invocation)"

    sections: dict[str, list[str]] = {
        "Comments": [],
        "Proofs": [],
        "Disproofs": [],
        "Assembly results": [],
        "Decompositions": [],
        "Priority changes": [],
    }

    for row in rows:
        event = row[0]
        handle = row.agent_handle or "system"
        details = event.details or {}
        time_str = event.created_at.strftime("%Y-%m-%d %H:%M UTC")
        conj_id = str(event.conjecture_id) if event.conjecture_id else "project"

        if event.event_type == "comment":
            body_preview = details.get("body_preview", "")[:500]
            sections["Comments"].append(f"  {time_str} | {handle} on {conj_id}:\n  {body_preview}")
        elif event.event_type == "proof":
            tactics = details.get("proof_lean_preview", "")[:300]
            sections["Proofs"].append(
                f"  {time_str} | {handle} proved {conj_id}\n  Tactics: {tactics}"
            )
        elif event.event_type == "disproof":
            tactics = details.get("proof_lean_preview", "")[:300]
            sections["Disproofs"].append(
                f"  {time_str} | {handle} disproved {conj_id}\n  Tactics: {tactics}"
            )
        elif event.event_type in ("assembly_success", "assembly_failure"):
            result_str = "success" if event.event_type == "assembly_success" else "FAILED"
            error = details.get("error", "")[:300]
            entry = f"  {time_str} | Assembly of {conj_id}: {result_str}"
            if error:
                entry += f"\n  Error: {error}"
            sections["Assembly results"].append(entry)
        elif event.event_type in (
            "decomposition_created",
            "decomposition_updated",
            "decomposition_reverted",
        ):
            sections["Decompositions"].append(
                f"  {time_str} | {event.event_type} on {conj_id} by {handle}"
            )
        elif event.event_type == "priority_changed":
            old_p = details.get("old_priority", "?")
            new_p = details.get("new_priority", "?")
            sections["Priority changes"].append(
                f"  {time_str} | {conj_id} priority: {old_p} -> {new_p}"
            )

    parts = []
    for section_name, entries in sections.items():
        if entries:
            parts.append(f"{section_name}:\n" + "\n".join(entries))

    return "\n\n".join(parts) if parts else "(no activity since last invocation)"


async def _get_project_summary(project_id: UUID, db: AsyncSession) -> str:
    """Get the latest is_summary comment on the project."""
    stmt = (
        select(Comment.body)
        .where(
            Comment.project_id == project_id,
            Comment.is_summary.is_(True),
        )
        .order_by(Comment.created_at.desc())
        .limit(1)
    )
    summary = await db.scalar(stmt)
    return summary if summary else "(no summary yet)"


async def _build_conjecture_summaries(
    project_id: UUID,
    last_invocation: datetime | None,
    db: AsyncSession,
) -> str:
    """Build per-conjecture summaries for active nodes."""
    # Get active conjectures (open or decomposed)
    active_conjectures = await db.execute(
        select(Conjecture.id, Conjecture.lean_statement, Conjecture.status).where(
            Conjecture.project_id == project_id,
            Conjecture.status.in_(["open", "decomposed"]),
        )
    )
    conjs = active_conjectures.all()

    if not conjs:
        return "(no active conjectures)"

    parts = []
    for conj in conjs:
        conj_id = conj.id
        lean_stmt = conj.lean_statement[:80]

        # Get latest summary
        summary_stmt = (
            select(Comment.body, Comment.created_at)
            .where(
                Comment.conjecture_id == conj_id,
                Comment.is_summary.is_(True),
            )
            .order_by(Comment.created_at.desc())
            .limit(1)
        )
        summary_row = (await db.execute(summary_stmt)).first()
        summary_text = summary_row[0] if summary_row else "(no summary)"
        summary_time = summary_row[1] if summary_row else None

        # Get comments since summary (or since last invocation if no summary)
        cutoff = summary_time or last_invocation
        comments_after = []
        if cutoff:
            comments_stmt = (
                select(Comment.body, Comment.created_at, Agent.handle)
                .join(Agent, Agent.id == Comment.author_id)
                .where(
                    Comment.conjecture_id == conj_id,
                    Comment.created_at > cutoff,
                    Comment.is_summary.is_(False),
                )
                .order_by(Comment.created_at)
            )
            rows = (await db.execute(comments_stmt)).all()
            for row in rows:
                time_str = row[1].strftime("%Y-%m-%d %H:%M UTC")
                body_preview = row[0][:300]
                comments_after.append(f"  {time_str} | {row[2]}: {body_preview}")

        entry = f'Conjecture {conj_id} -- "{lean_stmt}"\n'
        entry += f"Summary: {summary_text}\n"
        if comments_after:
            entry += "Comments since summary:\n" + "\n".join(comments_after)
        else:
            entry += "Comments since summary: (none)"

        parts.append(entry)

    return "\n\n".join(parts)


async def _build_stuck_nodes(project_id: UUID, db: AsyncSession) -> str:
    """Find open conjectures with no activity in 48+ hours."""
    threshold = datetime.now(UTC) - timedelta(hours=48)

    # Open conjectures with no recent comments or activity
    stuck_stmt = select(Conjecture.id, Conjecture.lean_statement).where(
        Conjecture.project_id == project_id,
        Conjecture.status == "open",
    )
    conjs = (await db.execute(stuck_stmt)).all()

    stuck_entries = []
    for conj in conjs:
        # Check if there's any recent activity
        recent_activity = await db.scalar(
            select(func.count()).where(
                ActivityLog.conjecture_id == conj.id,
                ActivityLog.created_at > threshold,
            )
        )
        recent_comments = await db.scalar(
            select(func.count()).where(
                Comment.conjecture_id == conj.id,
                Comment.created_at > threshold,
            )
        )

        if (recent_activity or 0) == 0 and (recent_comments or 0) == 0:
            # This node is stuck
            comment_count = await db.scalar(
                select(func.count()).where(Comment.conjecture_id == conj.id)
            )

            # Get last 5 comments
            last_comments = (
                await db.execute(
                    select(Comment.body, Comment.created_at, Agent.handle)
                    .join(Agent, Agent.id == Comment.author_id)
                    .where(Comment.conjecture_id == conj.id)
                    .order_by(Comment.created_at.desc())
                    .limit(5)
                )
            ).all()

            entry = f'{conj.id} | "{conj.lean_statement}" | {comment_count or 0} comments'
            if last_comments:
                entry += "\nLast 5 comments:"
                for c in reversed(last_comments):
                    time_str = c[1].strftime("%Y-%m-%d %H:%M UTC")
                    body_preview = c[0][:300]
                    entry += f"\n  {time_str} | {c[2]}: {body_preview}"

            stuck_entries.append(entry)

    return "\n\n".join(stuck_entries) if stuck_entries else "(no stuck nodes)"
