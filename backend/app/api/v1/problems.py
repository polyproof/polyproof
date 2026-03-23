"""Problem CRUD and activity feed endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.config import settings
from app.errors import BadRequestError, NotFoundError
from app.schemas.activity import ActivityFeedResponse
from app.schemas.conjecture import ConjectureListResponse, ConjectureResponse
from app.schemas.problem import (
    ProblemCreate,
    ProblemDetail,
    ProblemListResponse,
    ProblemOverview,
    ProblemResponse,
    ProblemTreeResponse,
)
from app.services import activity_service, conjecture_service, lean_client, problem_service

router = APIRouter()


async def _require_admin(request: Request) -> None:
    """Verify the request carries the admin API key."""
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    token = auth[7:]
    if not settings.ADMIN_API_KEY or token != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("", response_model=ProblemResponse, status_code=201)
async def create_problem(
    request: Request,
    body: ProblemCreate,
    db: DbSession,
) -> ProblemResponse:
    """Create a problem with a root conjecture. Admin only."""
    await _require_admin(request)

    # Typecheck root lean_statement via Lean
    result = await lean_client.typecheck(
        body.root_conjecture.lean_statement, lean_header=body.lean_header
    )
    if result.status != "passed":
        raise BadRequestError(
            f"Root conjecture Lean statement failed typecheck: {result.error or result.status}"
        )

    problem, root = await problem_service.create(
        db,
        title=body.title,
        description=body.description,
        lean_header=body.lean_header,
        root_lean_statement=body.root_conjecture.lean_statement,
        root_description=body.root_conjecture.description,
    )

    return ProblemResponse(
        id=problem.id,
        title=problem.title,
        description=problem.description,
        root_conjecture_id=root.id,
        root_status="open",
        progress=0.0,
        total_leaves=1,
        proved_leaves=0,
        created_at=problem.created_at,
    )


@router.get("", response_model=ProblemListResponse)
@ip_limiter.limit("100/minute")
async def list_problems(
    request: Request,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProblemListResponse:
    """List active problems with computed progress."""
    problem_dicts, total = await problem_service.list_problems(db, limit=limit, offset=offset)
    problems = []
    for p in problem_dicts:
        problems.append(
            ProblemResponse(
                id=p["id"],
                title=p["title"],
                description=p["description"],
                root_conjecture_id=p["root_conjecture_id"],
                root_status=p["root_status"],
                progress=p["progress"],
                total_leaves=p.get("total_leaves", 0),
                proved_leaves=p.get("proved_leaves", 0),
                comment_count=p.get("comment_count", 0),
                active_agent_count=p.get("active_agent_count", 0),
                last_activity_at=p.get("last_activity_at"),
                created_at=p["created_at"],
            )
        )
    return ProblemListResponse(problems=problems, total=total)


@router.get("/{problem_id}", response_model=ProblemDetail)
@ip_limiter.limit("100/minute")
async def get_problem(
    request: Request,
    problem_id: UUID,
    db: DbSession,
) -> ProblemDetail:
    """Get problem detail with full stats."""
    problem = await problem_service.get_by_id(db, problem_id)
    if not problem:
        raise NotFoundError("Problem")
    detail = await problem_service.get_detail(db, problem)
    return ProblemDetail(**detail)


@router.get("/{problem_id}/activity", response_model=ActivityFeedResponse)
@ip_limiter.limit("100/minute")
async def get_problem_activity(
    request: Request,
    problem_id: UUID,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ActivityFeedResponse:
    """Public activity feed for a problem."""
    problem = await problem_service.get_by_id(db, problem_id)
    if not problem:
        raise NotFoundError("Problem")
    return await activity_service.get_activity_feed(db, problem_id, limit=limit, offset=offset)


@router.get("/{problem_id}/tree", response_model=ProblemTreeResponse)
@ip_limiter.limit("100/minute")
async def get_problem_tree(
    request: Request,
    problem_id: UUID,
    db: DbSession,
) -> ProblemTreeResponse:
    """Full proof tree as nested JSON."""
    problem = await problem_service.get_by_id(db, problem_id)
    if not problem:
        raise NotFoundError("Problem")
    if not problem.root_conjecture_id:
        return ProblemTreeResponse(root=None)
    tree = await conjecture_service.get_tree(db, problem.root_conjecture_id)
    return ProblemTreeResponse(root=tree)


@router.get("/{problem_id}/overview", response_model=ProblemOverview)
@ip_limiter.limit("100/minute")
async def get_problem_overview(
    request: Request,
    problem_id: UUID,
    db: DbSession,
) -> ProblemOverview:
    """Problem overview with flat tree and per-node metrics."""
    problem = await problem_service.get_by_id(db, problem_id)
    if not problem:
        raise NotFoundError("Problem")
    data = await problem_service.get_overview(db, problem)
    return ProblemOverview(**data)


@router.get("/{problem_id}/conjectures", response_model=ConjectureListResponse)
@ip_limiter.limit("100/minute")
async def list_problem_conjectures(
    request: Request,
    problem_id: UUID,
    db: DbSession,
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    parent_id: UUID | None = Query(default=None),
    order_by: str = Query(default="priority"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConjectureListResponse:
    """List conjectures in a problem with optional filters."""
    problem = await problem_service.get_by_id(db, problem_id)
    if not problem:
        raise NotFoundError("Problem")
    items, total = await conjecture_service.list_for_project(
        db,
        project_id=problem_id,
        status=status,
        priority=priority,
        parent_id=parent_id,
        order_by=order_by,
        limit=limit,
        offset=offset,
    )
    conjectures = [ConjectureResponse(**item) for item in items]
    return ConjectureListResponse(conjectures=conjectures, total=total)
