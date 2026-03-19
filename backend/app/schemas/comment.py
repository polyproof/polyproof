from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AuthorResponse


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)
    parent_id: UUID | None = None


class CommentResponse(BaseModel):
    id: UUID
    body: str
    author: AuthorResponse
    depth: int
    vote_count: int
    user_vote: int | None = None
    is_deleted: bool = False
    created_at: datetime
    replies: list["CommentResponse"] = []

    model_config = ConfigDict(from_attributes=True)


class CommentTree(BaseModel):
    comments: list[CommentResponse]
    total: int


class CommentListParams(BaseModel):
    sort: str = Field(default="top", pattern=r"^(top|new)$")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
