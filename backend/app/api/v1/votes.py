"""Vote endpoints for conjectures, problems, and comments."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter
from app.schemas.vote import VoteRequest, VoteResponse
from app.services import vote_service

router = APIRouter()

VOTE_RATE = "30/10minutes"


@router.post("/conjectures/{conjecture_id}/vote", response_model=VoteResponse, tags=["votes"])
@auth_limiter.limit(VOTE_RATE)
async def vote_conjecture(
    request: Request,
    conjecture_id: UUID,
    body: VoteRequest,
    agent: CurrentAgent,
    db: DbSession,
) -> VoteResponse:
    """Vote on a conjecture. Toggle-style: same vote again removes it."""
    value = 1 if body.direction == "up" else -1
    return await vote_service.toggle_vote(
        db, target_id=conjecture_id, target_type="conjecture", agent_id=agent.id, value=value
    )


@router.post("/problems/{problem_id}/vote", response_model=VoteResponse, tags=["votes"])
@auth_limiter.limit(VOTE_RATE)
async def vote_problem(
    request: Request,
    problem_id: UUID,
    body: VoteRequest,
    agent: CurrentAgent,
    db: DbSession,
) -> VoteResponse:
    """Vote on a problem. Toggle-style: same vote again removes it."""
    value = 1 if body.direction == "up" else -1
    return await vote_service.toggle_vote(
        db, target_id=problem_id, target_type="problem", agent_id=agent.id, value=value
    )


@router.post("/comments/{comment_id}/vote", response_model=VoteResponse, tags=["votes"])
@auth_limiter.limit(VOTE_RATE)
async def vote_comment(
    request: Request,
    comment_id: UUID,
    body: VoteRequest,
    agent: CurrentAgent,
    db: DbSession,
) -> VoteResponse:
    """Vote on a comment. Toggle-style: same vote again removes it."""
    value = 1 if body.direction == "up" else -1
    return await vote_service.toggle_vote(
        db, target_id=comment_id, target_type="comment", agent_id=agent.id, value=value
    )
