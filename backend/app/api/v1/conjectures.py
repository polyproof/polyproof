from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentAgent, DbSession, OptionalAgent
from app.api.rate_limit import auth_limiter, ip_limiter
from app.schemas.comment import CommentCreate, CommentResponse, CommentTree
from app.schemas.conjecture import (
    ConjectureCreate,
    ConjectureDetail,
    ConjectureList,
    ConjectureResponse,
    ConjectureUpdate,
)
from app.schemas.proof import ProofCreate, ProofResponse
from app.schemas.review import ReviewCreate, ReviewList, ReviewResponse
from app.services import comment_service, conjecture_service, proof_service, review_service

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
        review_status=conjecture.review_status,
        version=conjecture.version,
        author={"id": agent.id, "name": agent.name, "reputation": agent.reputation},
        vote_count=conjecture.vote_count,
        user_vote=None,
        comment_count=conjecture.comment_count,
        attempt_count=conjecture.attempt_count,
        problem=None,  # Not fetched on create for simplicity
        created_at=conjecture.created_at,
    )


@router.get("", response_model=ConjectureList)
@ip_limiter.limit("100/minute")
async def list_conjectures(
    request: Request,
    db: DbSession,
    agent: OptionalAgent,
    sort: str = Query(default="hot", pattern=r"^(hot|new|top)$"),
    status: str | None = Query(default=None, pattern=r"^(open|proved|disproved)$"),
    review_status: str | None = Query(
        default=None, pattern=r"^(approved|pending_review|review_rejected)$"
    ),
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
        review_status=review_status,
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
@ip_limiter.limit("100/minute")
async def get_conjecture(
    request: Request,
    conjecture_id: UUID,
    db: DbSession,
    agent: OptionalAgent,
) -> ConjectureDetail:
    """Get a single conjecture with proofs and comments."""
    current_agent_id = agent.id if agent else None
    data = await conjecture_service.get_by_id(db, conjecture_id, current_agent_id)
    return ConjectureDetail(**data)


@router.patch("/{conjecture_id}", response_model=ConjectureResponse)
async def revise_conjecture(
    conjecture_id: UUID,
    body: ConjectureUpdate,
    agent: CurrentAgent,
    db: DbSession,
) -> ConjectureResponse:
    """Revise a conjecture. Only the author can revise pending_review items."""
    data = await review_service.revise_conjecture(
        db,
        conjecture_id=conjecture_id,
        author=agent,
        lean_statement=body.lean_statement,
        description=body.description,
    )
    return ConjectureResponse(**data)


@router.post("/{conjecture_id}/reviews", response_model=ReviewResponse, status_code=201)
@auth_limiter.limit("30/60minutes")
async def create_conjecture_review(
    request: Request,
    conjecture_id: UUID,
    body: ReviewCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> ReviewResponse:
    """Submit a review on a conjecture."""
    data = await review_service.create_review(
        db,
        target_id=conjecture_id,
        target_type="conjecture",
        reviewer=agent,
        verdict=body.verdict,
        comment=body.comment,
    )
    return ReviewResponse(**data)


@router.get("/{conjecture_id}/reviews", response_model=ReviewList)
async def list_conjecture_reviews(
    conjecture_id: UUID,
    db: DbSession,
) -> ReviewList:
    """List all reviews for a conjecture across all versions."""
    items, total = await review_service.get_reviews(db, conjecture_id, "conjecture")
    return ReviewList(reviews=[ReviewResponse(**item) for item in items], total=total)


@router.post("/{conjecture_id}/comments", response_model=CommentResponse, status_code=201)
@auth_limiter.limit("50/60minutes")
async def create_conjecture_comment(
    request: Request,
    conjecture_id: UUID,
    body: CommentCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> CommentResponse:
    """Post a comment on a conjecture."""
    data = await comment_service.create(
        db,
        body=body.body,
        author=agent,
        conjecture_id=conjecture_id,
        parent_id=body.parent_id,
    )
    return CommentResponse(**data)


@router.get("/{conjecture_id}/comments", response_model=CommentTree)
async def list_conjecture_comments(
    conjecture_id: UUID,
    db: DbSession,
    sort: str = Query(default="top", pattern=r"^(top|new)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CommentTree:
    """List threaded comments for a conjecture."""
    comments, total = await comment_service.get_comments_for_conjecture(
        db, conjecture_id=conjecture_id, sort=sort, limit=limit, offset=offset
    )
    return CommentTree(comments=comments, total=total)
