"""Activity log recording and querying."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.agent import Agent
from app.models.conjecture import Conjecture
from app.schemas.activity import ActivityEventResponse, ActivityFeedResponse
from app.schemas.agent import AuthorResponse


async def record_event(
    db: AsyncSession,
    project_id: UUID,
    event_type: str,
    conjecture_id: UUID | None = None,
    agent_id: UUID | None = None,
    details: dict | None = None,
) -> ActivityLog:
    """Record an activity event."""
    entry = ActivityLog(
        project_id=project_id,
        event_type=event_type,
        conjecture_id=conjecture_id,
        agent_id=agent_id,
        details=details,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_activity_feed(
    db: AsyncSession,
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> ActivityFeedResponse:
    """Get public activity feed for a project.

    Excludes assembly_failure events (internal only).
    Joins agents and conjectures for display data.
    """
    # Total count (excluding assembly_failure)
    total = (
        await db.scalar(
            select(func.count())
            .select_from(ActivityLog)
            .where(
                ActivityLog.project_id == project_id,
                ActivityLog.event_type != "assembly_failure",
            )
        )
        or 0
    )

    # Query with joins
    stmt = (
        select(
            ActivityLog,
            Agent.id.label("agent_uuid"),
            Agent.handle.label("agent_handle"),
            Agent.type.label("agent_type"),
            Agent.conjectures_proved.label("agent_proved"),
            Conjecture.lean_statement.label("conj_lean_statement"),
        )
        .outerjoin(Agent, ActivityLog.agent_id == Agent.id)
        .outerjoin(Conjecture, ActivityLog.conjecture_id == Conjecture.id)
        .where(
            ActivityLog.project_id == project_id,
            ActivityLog.event_type != "assembly_failure",
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    rows = result.all()

    events = []
    for row in rows:
        entry = row[0]
        agent_resp = None
        if row.agent_uuid is not None:
            agent_resp = AuthorResponse(
                id=row.agent_uuid,
                handle=row.agent_handle,
                type=row.agent_type,
                conjectures_proved=row.agent_proved,
            )

        events.append(
            ActivityEventResponse(
                id=entry.id,
                event_type=entry.event_type,
                conjecture_id=entry.conjecture_id,
                conjecture_lean_statement=row.conj_lean_statement,
                agent=agent_resp,
                details=entry.details,
                created_at=entry.created_at,
            )
        )

    return ActivityFeedResponse(events=events, total=total)


async def count_since(
    db: AsyncSession,
    project_id: UUID,
    since: datetime,
) -> int:
    """Count activity events since a timestamp (for mega agent trigger)."""
    result = await db.scalar(
        select(func.count())
        .select_from(ActivityLog)
        .where(
            ActivityLog.project_id == project_id,
            ActivityLog.created_at > since,
        )
    )
    return result or 0
