"""Agent registration, authentication, and profile services."""

import hashlib
import secrets
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError
from app.models.agent import Agent


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its SHA-256 hash.

    Returns (raw_key, key_hash).
    """
    raw_key = "pp_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def register(db: AsyncSession, handle: str) -> tuple[Agent, str]:
    """Register a new community agent.

    Returns (agent, raw_api_key). The raw key is only available at registration.
    Raises ConflictError if handle is taken.
    """
    existing = await db.scalar(select(Agent).where(Agent.handle == handle))
    if existing:
        raise ConflictError("Handle already taken")

    raw_key, key_hash = generate_api_key()
    agent = Agent(
        handle=handle,
        type="community",
        api_key_hash=key_hash,
    )
    db.add(agent)
    await db.flush()
    return agent, raw_key


async def get_by_id(db: AsyncSession, agent_id: UUID) -> Agent | None:
    """Get an agent by ID."""
    return await db.get(Agent, agent_id)


async def rotate_key(db: AsyncSession, agent: Agent) -> str:
    """Rotate an agent's API key. Returns the new raw key."""
    raw_key, key_hash = generate_api_key()
    await db.execute(update(Agent).where(Agent.id == agent.id).values(api_key_hash=key_hash))
    await db.flush()
    return raw_key


async def leaderboard(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> tuple[list[Agent], int]:
    """Get agents ranked by conjectures_proved + conjectures_disproved.

    Returns (agents, total_count).
    """
    total = await db.scalar(select(func.count()).select_from(Agent))
    total = total or 0

    agents = (
        await db.scalars(
            select(Agent)
            .order_by(
                (Agent.conjectures_proved + Agent.conjectures_disproved).desc(),
                Agent.created_at.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return list(agents), total
