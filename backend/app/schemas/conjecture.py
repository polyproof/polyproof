from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AuthorResponse
from app.schemas.comment import CommentResponse
from app.schemas.proof import ProofResponse


class ProblemRef(BaseModel):
    """Minimal problem reference embedded in conjecture responses."""

    id: UUID
    title: str

    model_config = ConfigDict(from_attributes=True)


class ConjectureCreate(BaseModel):
    problem_id: UUID | None = None
    lean_statement: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class ConjectureResponse(BaseModel):
    id: UUID
    lean_statement: str
    description: str
    status: str
    author: AuthorResponse
    vote_count: int
    user_vote: int | None = None
    comment_count: int
    attempt_count: int
    problem: ProblemRef | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConjectureDetail(BaseModel):
    id: UUID
    lean_statement: str
    description: str
    status: str
    author: AuthorResponse
    vote_count: int
    user_vote: int | None = None
    comment_count: int
    attempt_count: int
    proofs: list[ProofResponse]
    comments: list[CommentResponse]
    problem: ProblemRef | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConjectureList(BaseModel):
    conjectures: list[ConjectureResponse]
    total: int


class ConjectureListParams(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(open|proved|disproved)$")
    sort: str = Field(default="hot", pattern=r"^(hot|new|top)$")
    problem_id: UUID | None = None
    author_id: UUID | None = None
    since: datetime | None = None
    q: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
