from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AuthorResponse


class ProblemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)


class ProblemResponse(BaseModel):
    id: UUID
    title: str
    description: str
    author: AuthorResponse
    vote_count: int
    user_vote: int | None = None
    conjecture_count: int
    comment_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProblemList(BaseModel):
    problems: list[ProblemResponse]
    total: int


class ProblemListParams(BaseModel):
    sort: str = Field(default="hot", pattern=r"^(hot|new|top)$")
    q: str | None = None
    author_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
