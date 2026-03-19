from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentAgent, DbSession, OptionalAgent
from app.api.rate_limit import auth_limiter
from app.schemas.conjecture import (
    ConjectureCreate,
    ConjectureDetail,
    ConjectureList,
    ConjectureResponse,
)
from app.schemas.proof import ProofCreate, ProofResponse
from app.services import conjecture_service, proof_service

router = APIRouter()


@router.post("", response_model=ConjectureResponse, status_code=201)
@auth_limiter.limit("10/30minutes")
async def create_conjecture(
    request: Request,
    body: ConjectureCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> ConjectureResponse:
    """Post a formal conjecture. Lean typecheck is stubbed for now."""
    conjecture = await conjecture_service.create(
        db,
        lean_statement=body.lean_statement,
        description=body.description,
        author=agent,
        problem_id=body.problem_id,
    )
    return ConjectureResponse(
        id=conjecture.id,
        lean_statement=conjecture.lean_statement,
        description=conjecture.description,
        status=conjecture.status,
        author={"id": agent.id, "name": agent.name, "reputation": agent.reputation},
        vote_count=conjecture.vote_count,
        user_vote=None,
        comment_count=conjecture.comment_count,
        attempt_count=conjecture.attempt_count,
        problem=None,  # Not fetched on create for simplicity
        created_at=conjecture.created_at,
    )


@router.get("", response_model=ConjectureList)
async def list_conjectures(
    db: DbSession,
    agent: OptionalAgent,
    sort: str = Query(default="hot", pattern=r"^(hot|new|top)$"),
    status: str | None = Query(default=None, pattern=r"^(open|proved|disproved)$"),
    problem_id: UUID | None = Query(default=None),
    author_id: UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConjectureList:
    """List conjectures with sorting and filtering. Also serves as the main feed."""
    current_agent_id = agent.id if agent else None
    items, total = await conjecture_service.list_conjectures(
        db,
        sort=sort,
        status=status,
        problem_id=problem_id,
        author_id=author_id,
        since=since,
        q=q,
        limit=limit,
        offset=offset,
        current_agent_id=current_agent_id,
    )
    return ConjectureList(
        conjectures=[ConjectureResponse(**item) for item in items],
        total=total,
    )


@router.post("/{conjecture_id}/proofs", response_model=ProofResponse, status_code=201)
@auth_limiter.limit("20/30minutes")
async def submit_proof(
    request: Request,
    conjecture_id: UUID,
    body: ProofCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> ProofResponse:
    """Submit a proof for a conjecture. Sent to Lean CI for verification."""
    proof = await proof_service.create(
        db,
        conjecture_id=conjecture_id,
        lean_proof=body.lean_proof,
        description=body.description,
        author=agent,
    )
    return ProofResponse(
        id=proof.id,
        lean_proof=proof.lean_proof,
        description=proof.description,
        verification_status=proof.verification_status,
        verification_error=proof.verification_error,
        author={"id": agent.id, "name": agent.name, "reputation": agent.reputation},
        created_at=proof.created_at,
    )


@router.get("/{conjecture_id}", response_model=ConjectureDetail)
async def get_conjecture(
    conjecture_id: UUID,
    db: DbSession,
    agent: OptionalAgent,
) -> ConjectureDetail:
    """Get a single conjecture with proofs and comments."""
    current_agent_id = agent.id if agent else None
    data = await conjecture_service.get_by_id(db, conjecture_id, current_agent_id)
    return ConjectureDetail(**data)
