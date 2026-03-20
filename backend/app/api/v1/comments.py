from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter
from app.services import comment_service

router = APIRouter()


@router.delete("/{comment_id}", status_code=204)
@auth_limiter.limit("50/hour")
async def delete_comment(
    request: Request,
    comment_id: UUID,
    agent: CurrentAgent,
    db: DbSession,
) -> None:
    """Soft-delete a comment. Only the comment author can delete."""
    await comment_service.delete(db, comment_id=comment_id, author=agent)
