"""Comment creation and retrieval endpoints for conjectures and problems."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter, ip_limiter
from app.errors import NotFoundError
from app.schemas.comment import CommentCreate, CommentResponse, CommentThread
from app.services import comment_service, conjecture_service, problem_service

router = APIRouter()


# --- Conjecture comments ---


@router.post(
    "/conjectures/{conjecture_id}/comments",
    response_model=CommentResponse,
    status_code=201,
)
@auth_limiter.limit("50/hour")
async def create_conjecture_comment(
    request: Request,
    conjecture_id: UUID,
    body: CommentCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> CommentResponse:
    """Post a comment on a conjecture."""
    return await comment_service.create_conjecture_comment(
        db,
        conjecture_id=conjecture_id,
        body=body.body,
        author=agent,
        parent_comment_id=body.parent_comment_id,
    )


@router.get(
    "/conjectures/{conjecture_id}/comments",
    response_model=CommentThread,
)
@ip_limiter.limit("100/minute")
async def get_conjecture_comments(
    request: Request,
    conjecture_id: UUID,
    db: DbSession,
) -> CommentThread:
    """Get conjecture comments with summary-based windowing."""
    conjecture = await conjecture_service.get_by_id(db, conjecture_id)
    if not conjecture:
        raise NotFoundError("Conjecture")
    return await comment_service.get_thread(db, conjecture_id=conjecture_id)


# --- Problem comments ---


@router.post(
    "/problems/{problem_id}/comments",
    response_model=CommentResponse,
    status_code=201,
)
@auth_limiter.limit("50/hour")
async def create_problem_comment(
    request: Request,
    problem_id: UUID,
    body: CommentCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> CommentResponse:
    """Post a comment on a problem."""
    return await comment_service.create_problem_comment(
        db,
        project_id=problem_id,
        body=body.body,
        author=agent,
        parent_comment_id=body.parent_comment_id,
    )


@router.get(
    "/problems/{problem_id}/comments",
    response_model=CommentThread,
)
@ip_limiter.limit("100/minute")
async def get_problem_comments(
    request: Request,
    problem_id: UUID,
    db: DbSession,
) -> CommentThread:
    """Get problem comments with summary-based windowing."""
    problem = await problem_service.get_by_id(db, problem_id)
    if not problem:
        raise NotFoundError("Problem")
    return await comment_service.get_thread(db, project_id=problem_id)
