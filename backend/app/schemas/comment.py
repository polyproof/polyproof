from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AuthorResponse


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10_000)
    parent_comment_id: UUID | None = None


class CommentResponse(BaseModel):
    id: UUID
    body: str
    author: AuthorResponse
    is_summary: bool = False
    parent_comment_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentThread(BaseModel):
    summary: CommentResponse | None = None
    comments_after_summary: list[CommentResponse] = []
    total: int = 0
