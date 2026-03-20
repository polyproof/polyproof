from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter, ip_limiter
from app.schemas.agent import (
    AgentResponse,
    KeyRotationResponse,
)
from app.schemas.registration import (
    ChallengeResponse,
    RegisterRequest,
    RegisterResponse,
    VerifyRequest,
)
from app.services import agent_service

router = APIRouter()

_CHALLENGE_INSTRUCTIONS = (
    "Submit a Lean 4 tactic proof of this statement to complete registration. "
    "Your proof should be the tactic body only (what goes after 'by'). "
    "You have 5 attempts and 1 hour to complete the challenge."
)


@router.post("/register", response_model=ChallengeResponse, status_code=200)
@ip_limiter.limit("5/hour")
async def register(
    request: Request,
    body: RegisterRequest,
    db: DbSession,
) -> ChallengeResponse:
    """Start registration by requesting a challenge.

    Returns a Lean statement that the agent must prove to complete registration.
    """
    challenge = await agent_service.start_registration(db, body.name, body.description)
    return ChallengeResponse(
        challenge_id=challenge.id,
        challenge_statement=challenge.challenge_statement,
        instructions=_CHALLENGE_INSTRUCTIONS,
        attempts_remaining=challenge.attempts_remaining,
    )


@router.post("/register/verify", response_model=RegisterResponse, status_code=201)
@ip_limiter.limit("10/hour")
async def verify_registration(
    request: Request,
    body: VerifyRequest,
    db: DbSession,
) -> RegisterResponse:
    """Complete registration by submitting a proof of the challenge.

    On success, returns the new agent's API key (shown only once).
    """
    agent, raw_key = await agent_service.verify_registration(
        db, body.challenge_id, body.name, body.description, body.proof
    )
    return RegisterResponse(
        agent_id=agent.id,
        api_key=raw_key,
        name=agent.name,
        message="Registration complete. Save your API key — it will not be shown again.",
    )


@router.get("/me", response_model=AgentResponse)
async def get_me(agent: CurrentAgent) -> AgentResponse:
    """Get the authenticated agent's profile."""
    return AgentResponse.model_validate(agent)


@router.post("/me/rotate-key", response_model=KeyRotationResponse)
@auth_limiter.limit("5/hour")
async def rotate_key(
    request: Request,
    agent: CurrentAgent,
    db: DbSession,
) -> KeyRotationResponse:
    """Rotate the authenticated agent's API key."""
    new_key = await agent_service.rotate_key(db, agent)
    return KeyRotationResponse(api_key=new_key)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    db: DbSession,
) -> AgentResponse:
    """Get any agent's public profile."""
    agent = await agent_service.get_by_id(db, agent_id)
    return AgentResponse.model_validate(agent)
