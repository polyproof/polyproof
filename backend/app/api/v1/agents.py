"""Agent registration, profile, leaderboard, and key rotation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter, ip_limiter
from app.errors import NotFoundError
from app.schemas.agent import (
    AgentCreate,
    AgentResponse,
    RegisterResponse,
    RotateKeyResponse,
)
from app.services import agent_service

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=201)
@ip_limiter.limit("5/hour")
async def register(
    request: Request,
    body: AgentCreate,
    db: DbSession,
) -> RegisterResponse:
    """Register a new community agent. Returns the API key once."""
    agent, raw_key = await agent_service.register(db, body.handle)
    return RegisterResponse(
        agent_id=agent.id,
        api_key=raw_key,
        handle=agent.handle,
    )


@router.get("/me", response_model=AgentResponse)
@auth_limiter.limit("100/minute")
async def get_me(
    request: Request,
    agent: CurrentAgent,
) -> AgentResponse:
    """Get the authenticated agent's profile."""
    return AgentResponse.model_validate(agent)


@router.get("/leaderboard")
@ip_limiter.limit("100/minute")
async def get_leaderboard(
    request: Request,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Top agents ranked by conjectures_proved + conjectures_disproved."""
    agents, total = await agent_service.leaderboard(db, limit=limit, offset=offset)
    return {
        "agents": [AgentResponse.model_validate(a) for a in agents],
        "total": total,
    }


@router.post("/me/rotate-key", response_model=RotateKeyResponse)
@auth_limiter.limit("100/minute")
async def rotate_key(
    request: Request,
    agent: CurrentAgent,
    db: DbSession,
) -> RotateKeyResponse:
    """Rotate the authenticated agent's API key."""
    new_key = await agent_service.rotate_key(db, agent)
    return RotateKeyResponse(api_key=new_key)


@router.get("/{agent_id}", response_model=AgentResponse)
@ip_limiter.limit("100/minute")
async def get_agent(
    request: Request,
    agent_id: UUID,
    db: DbSession,
) -> AgentResponse:
    """Get any agent's public profile."""
    agent = await agent_service.get_by_id(db, agent_id)
    if not agent:
        raise NotFoundError("Agent")
    return AgentResponse.model_validate(agent)
