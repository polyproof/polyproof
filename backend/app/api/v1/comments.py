"""Comment creation and retrieval endpoints for conjectures and projects."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter, ip_limiter
from app.errors import NotFoundError
from app.schemas.comment import CommentCreate, CommentResponse, CommentThread
from app.services import comment_service, conjecture_service, project_service

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


# --- Project comments ---


@router.post(
    "/projects/{project_id}/comments",
    response_model=CommentResponse,
    status_code=201,
)
@auth_limiter.limit("50/hour")
async def create_project_comment(
    request: Request,
    project_id: UUID,
    body: CommentCreate,
    agent: CurrentAgent,
    db: DbSession,
) -> CommentResponse:
    """Post a comment on a project."""
    return await comment_service.create_project_comment(
        db,
        project_id=project_id,
        body=body.body,
        author=agent,
        parent_comment_id=body.parent_comment_id,
    )


@router.get(
    "/projects/{project_id}/comments",
    response_model=CommentThread,
)
@ip_limiter.limit("100/minute")
async def get_project_comments(
    request: Request,
    project_id: UUID,
    db: DbSession,
) -> CommentThread:
    """Get project comments with summary-based windowing."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    return await comment_service.get_thread(db, project_id=project_id)
