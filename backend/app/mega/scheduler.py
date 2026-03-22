"""APScheduler-based trigger checking for the mega agent.

Checks triggers every 60 seconds for each active project:
- activity_threshold: fires when activity count >= ACTIVITY_THRESHOLD
- periodic_heartbeat: fires when 24+ hours since last invocation
- project_created: fires once when last_mega_invocation is NULL

Uses per-project asyncio locks to serialize invocations.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.connection import async_session_factory
from app.models.activity_log import ActivityLog
from app.models.project import Project

logger = logging.getLogger(__name__)

# Per-project locks to prevent concurrent mega agent invocations
_project_locks: dict[UUID, asyncio.Lock] = {}

# Default activity threshold (configurable via env var)
ACTIVITY_THRESHOLD = int(getattr(settings, "ACTIVITY_THRESHOLD", 5))

# Heartbeat interval in hours
HEARTBEAT_HOURS = 24

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the APScheduler with the trigger check job."""
    scheduler.add_job(
        _check_all_projects,
        trigger=IntervalTrigger(seconds=60),
        id="mega_agent_trigger_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Mega agent scheduler started (checking every 60s)")


def stop_scheduler() -> None:
    """Stop the APScheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Mega agent scheduler stopped")


async def _check_all_projects() -> None:
    """Check triggers for all active projects."""
    async with async_session_factory() as db:
        stmt = select(Project.id).where(Project.root_conjecture_id.isnot(None))
        result = await db.execute(stmt)
        project_ids = [row[0] for row in result.all()]

    for project_id in project_ids:
        try:
            await check_triggers(project_id)
        except Exception:
            logger.exception("Error checking triggers for project %s", project_id)


async def check_triggers(project_id: UUID) -> None:
    """Check if any trigger should fire for a project.

    Triggers (in priority order):
    1. project_created: last_mega_invocation is NULL
    2. activity_threshold: activity count >= ACTIVITY_THRESHOLD since last invocation
    3. periodic_heartbeat: 24+ hours since last invocation
    """
    async with async_session_factory() as db:
        project = await db.get(Project, project_id)
        if not project:
            return

        last_invocation = project.last_mega_invocation

        # Trigger 1: project_created (fire once on first invocation)
        if last_invocation is None:
            await _invoke_mega_agent(
                project_id,
                {"trigger": "project_created"},
                db,
            )
            return

        # Cooldown: don't invoke if last invocation was too recent
        seconds_since = (datetime.now(UTC) - last_invocation).total_seconds()
        if seconds_since < settings.MEGA_AGENT_COOLDOWN_SEC:
            return

        # Trigger 2: activity_threshold
        activity_count = await _count_activity_since(project_id, last_invocation, db)
        if activity_count >= ACTIVITY_THRESHOLD:
            await _invoke_mega_agent(
                project_id,
                {
                    "trigger": "activity_threshold",
                    "activity_count": activity_count,
                },
                db,
            )
            return

        # Trigger 3: periodic_heartbeat (24h+, only if unseen activity)
        hours_since = seconds_since / 3600
        if hours_since >= HEARTBEAT_HOURS and activity_count > 0:
            await _invoke_mega_agent(
                project_id,
                {"trigger": "periodic_heartbeat", "activity_count": activity_count},
                db,
            )
            return


async def _count_activity_since(project_id: UUID, since: datetime, db: AsyncSession) -> int:
    """Count activity_log entries since a given timestamp."""
    result = await db.scalar(
        select(func.count()).where(
            ActivityLog.project_id == project_id,
            ActivityLog.created_at > since,
        )
    )
    return result or 0


async def _invoke_mega_agent(
    project_id: UUID,
    trigger: dict,
    db: AsyncSession,
) -> None:
    """Invoke the mega agent for a project, serialized by project lock."""
    # Get or create a lock for this project
    if project_id not in _project_locks:
        _project_locks[project_id] = asyncio.Lock()

    lock = _project_locks[project_id]

    # Don't block if another invocation is running -- just skip
    if lock.locked():
        logger.debug("Mega agent already running for project %s, skipping", project_id)
        return

    async with lock:
        try:
            # Import here to avoid circular imports
            from app.mega.runner import run_mega_agent

            # Get the mega agent's agent_id
            mega_agent_id = await _get_or_create_mega_agent_id(db)

            result = await run_mega_agent(
                project_id=project_id,
                trigger=trigger,
                mega_agent_id=mega_agent_id,
                db=db,
            )

            # Only update timestamp on successful run (not on API failure)
            if result.get("status") == "ok":
                await db.execute(
                    update(Project)
                    .where(Project.id == project_id)
                    .values(last_mega_invocation=func.now())
                )
                await db.commit()

            logger.info(
                "Mega agent invocation complete for project %s: %s",
                project_id,
                result,
            )
        except Exception:
            logger.exception("Mega agent invocation failed for project %s", project_id)


async def fire_project_completed(project_id: UUID) -> None:
    """Fire a project_completed trigger after the caller's transaction commits.

    Called via asyncio.create_task when the root conjecture is proved (via
    direct proof or assembly). Waits briefly for the caller's transaction to
    commit, then verifies the root is actually proved before invoking.
    """
    # Wait for the caller's transaction to commit
    await asyncio.sleep(2)

    async with async_session_factory() as db:
        # Verify the root is actually proved (guards against rollbacks)
        project = await db.get(Project, project_id)
        if not project or not project.root_conjecture_id:
            return
        from app.models.conjecture import Conjecture

        root = await db.get(Conjecture, project.root_conjecture_id)
        if not root or root.status != "proved":
            logger.info("Root not proved for project %s, skipping project_completed", project_id)
            return

        logger.info("Firing project_completed trigger for project %s", project_id)
        await _invoke_mega_agent(
            project_id,
            {"trigger": "project_completed"},
            db,
        )


async def _get_or_create_mega_agent_id(db: AsyncSession) -> UUID:
    """Get the mega agent's agent ID, creating it if necessary.

    The mega agent is a special system agent with handle 'mega_agent'
    and type 'mega'.
    """
    from app.models.agent import Agent

    stmt = select(Agent.id).where(Agent.handle == "mega_agent", Agent.type == "mega")
    agent_id = await db.scalar(stmt)
    if agent_id:
        return agent_id

    # Create the mega agent if it doesn't exist
    import hashlib
    import secrets

    agent = Agent(
        handle="mega_agent",
        type="mega",
        api_key_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        status="active",
    )
    db.add(agent)
    await db.flush()
    await db.commit()
    logger.info("Created mega agent with id %s", agent.id)
    return agent.id
