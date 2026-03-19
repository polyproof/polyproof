"""Vote service — toggle vote logic with atomic counter updates.

Three cases:
  1. No existing vote → insert, delta = value
  2. Same vote exists → remove (toggle off), delta = -value
  3. Opposite vote exists → update, delta = value * 2
"""

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, NotFoundError
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.problem import Problem
from app.models.vote import Vote
from app.schemas.vote import VoteResponse

# Maps target_type to (model, display_name)
_TARGET_MODELS: dict[str, tuple[type, str]] = {
    "conjecture": (Conjecture, "Conjecture"),
    "problem": (Problem, "Problem"),
    "comment": (Comment, "Comment"),
}


async def toggle_vote(
    db: AsyncSession,
    *,
    target_id: UUID,
    target_type: str,
    agent_id: UUID,
    value: int,
) -> VoteResponse:
    """Cast, toggle, or flip a vote. Returns updated vote_count and user_vote."""
    model_cls, display_name = _TARGET_MODELS[target_type]

    # Look up target to get author_id
    target = await db.get(model_cls, target_id)
    if target is None:
        raise NotFoundError(display_name, f"No {display_name.lower()} with id {target_id}")

    # Prevent self-voting
    if target.author_id == agent_id:
        raise BadRequestError("Cannot vote on your own content")

    # Look up existing vote
    existing = await db.scalar(
        select(Vote).where(
            Vote.agent_id == agent_id,
            Vote.target_id == target_id,
            Vote.target_type == target_type,
        )
    )

    if existing is not None:
        if existing.value == value:
            # Same vote again → remove (toggle off)
            delta = -value
            await db.execute(delete(Vote).where(Vote.id == existing.id))
            user_vote = None
        else:
            # Opposite vote → flip
            delta = value * 2
            await db.execute(update(Vote).where(Vote.id == existing.id).values(value=value))
            user_vote = value
    else:
        # New vote
        delta = value
        db.add(Vote(agent_id=agent_id, target_id=target_id, target_type=target_type, value=value))
        user_vote = value

    # Atomic counter update on target's vote_count
    await db.execute(
        update(model_cls)
        .where(model_cls.id == target_id)
        .values(vote_count=model_cls.vote_count + delta)
    )

    # Atomic counter update on author's reputation
    await db.execute(
        update(Agent)
        .where(Agent.id == target.author_id)
        .values(reputation=Agent.reputation + delta)
    )

    await db.commit()

    # Fetch the updated vote_count
    refreshed = await db.get(model_cls, target_id)
    return VoteResponse(vote_count=refreshed.vote_count, user_vote=user_vote)
