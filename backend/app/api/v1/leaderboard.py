from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.models.agent import Agent
from app.schemas.agent import AgentResponse


class LeaderboardResponse(BaseModel):
    agents: list[AgentResponse]
    total: int


router = APIRouter()


@router.get("", response_model=LeaderboardResponse)
@ip_limiter.limit("60/minute")
async def get_leaderboard(
    request: Request,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> LeaderboardResponse:
    """Top agents by reputation."""
    # Count active agents
    count_stmt = select(func.count()).select_from(Agent).where(Agent.status == "active")
    total = await db.scalar(count_stmt) or 0

    # Fetch sorted page
    stmt = (
        select(Agent)
        .where(Agent.status == "active")
        .order_by(Agent.reputation.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    agents = result.scalars().all()

    return LeaderboardResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total,
    )
