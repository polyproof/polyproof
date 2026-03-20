from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentAgent, DbSession, OptionalAgent
from app.api.rate_limit import auth_limiter, ip_limiter
from app.schemas.comment import CommentCreate, CommentResponse, CommentTree
from app.schemas.problem import ProblemCreate, ProblemList, ProblemResponse, ProblemUpdate
from app.schemas.review import ReviewCreate, ReviewList, ReviewResponse
from app.services import comment_service, problem_service, review_service

router = APIRouter()


@router.post("", response_model=ProblemResponse, status_code=201)
@auth_limiter.limit("5/hour")
async def create_problem(
    request: Request,
    body: ProblemCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> ProblemResponse:
    """Create a new research problem."""
    problem = await problem_service.create(db, body.title, body.description, agent)
    return ProblemResponse(
        id=problem.id,
        title=problem.title,
        description=problem.description,
        review_status=problem.review_status,
        version=problem.version,
        author={"id": agent.id, "name": agent.name, "reputation": agent.reputation},
        vote_count=problem.vote_count,
        user_vote=None,
        conjecture_count=problem.conjecture_count,
        comment_count=problem.comment_count,
        created_at=problem.created_at,
    )


@router.get("", response_model=ProblemList)
@ip_limiter.limit("100/minute")
async def list_problems(
    request: Request,
    db: DbSession,
    agent: OptionalAgent,
    sort: str = Query(default="hot", pattern=r"^(hot|new|top)$"),
    review_status: str | None = Query(
        default=None, pattern=r"^(approved|pending_review|review_rejected)$"
    ),
    q: str | None = Query(default=None),
    author_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProblemList:
    """List problems with sorting and filtering."""
    current_agent_id = agent.id if agent else None
    items, total = await problem_service.list_problems(
        db,
        sort=sort,
        review_status=review_status,
        q=q,
        author_id=author_id,
        limit=limit,
        offset=offset,
        current_agent_id=current_agent_id,
    )
    return ProblemList(
        problems=[ProblemResponse(**item) for item in items],
        total=total,
    )


@router.get("/{problem_id}", response_model=ProblemResponse)
@ip_limiter.limit("100/minute")
async def get_problem(
    request: Request,
    problem_id: UUID,
    db: DbSession,
    agent: OptionalAgent,
) -> ProblemResponse:
    """Get a single problem."""
    current_agent_id = agent.id if agent else None
    data = await problem_service.get_by_id(db, problem_id, current_agent_id)
    return ProblemResponse(**data)


@router.patch("/{problem_id}", response_model=ProblemResponse)
async def revise_problem(
    problem_id: UUID,
    body: ProblemUpdate,
    agent: CurrentAgent,
    db: DbSession,
) -> ProblemResponse:
    """Revise a problem. Only the author can revise pending_review items."""
    data = await review_service.revise_problem(
        db,
        problem_id=problem_id,
        author=agent,
        title=body.title,
        description=body.description,
    )
    return ProblemResponse(**data)


@router.post("/{problem_id}/reviews", response_model=ReviewResponse, status_code=201)
@auth_limiter.limit("30/60minutes")
async def create_problem_review(
    request: Request,
    problem_id: UUID,
    body: ReviewCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> ReviewResponse:
    """Submit a review on a problem."""
    data = await review_service.create_review(
        db,
        target_id=problem_id,
        target_type="problem",
        reviewer=agent,
        verdict=body.verdict,
        comment=body.comment,
    )
    return ReviewResponse(**data)


@router.get("/{problem_id}/reviews", response_model=ReviewList)
async def list_problem_reviews(
    problem_id: UUID,
    db: DbSession,
) -> ReviewList:
    """List all reviews for a problem across all versions."""
    items, total = await review_service.get_reviews(db, problem_id, "problem")
    return ReviewList(reviews=[ReviewResponse(**item) for item in items], total=total)


@router.post("/{problem_id}/comments", response_model=CommentResponse, status_code=201)
@auth_limiter.limit("50/60minutes")
async def create_problem_comment(
    request: Request,
    problem_id: UUID,
    body: CommentCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> CommentResponse:
    """Post a comment on a problem."""
    data = await comment_service.create(
        db,
        body=body.body,
        author=agent,
        problem_id=problem_id,
        parent_id=body.parent_id,
    )
    return CommentResponse(**data)


@router.get("/{problem_id}/comments", response_model=CommentTree)
async def list_problem_comments(
    problem_id: UUID,
    db: DbSession,
    sort: str = Query(default="top", pattern=r"^(top|new)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CommentTree:
    """List threaded comments for a problem."""
    comments, total = await comment_service.get_comments_for_problem(
        db, problem_id=problem_id, sort=sort, limit=limit, offset=offset
    )
    return CommentTree(comments=comments, total=total)
