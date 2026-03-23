from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AuthorResponse


class RootConjectureCreate(BaseModel):
    lean_statement: str = Field(..., min_length=1, max_length=100_000)
    description: str = Field(..., min_length=1, max_length=10_000)


class ProblemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=10_000)
    lean_header: str | None = Field(None, max_length=10_000)
    root_conjecture: RootConjectureCreate


class ProblemResponse(BaseModel):
    id: UUID
    title: str
    description: str
    root_conjecture_id: UUID | None
    root_status: str | None = None
    progress: float = 0.0
    total_leaves: int = 0
    proved_leaves: int = 0
    comment_count: int = 0
    active_agent_count: int = 0
    last_activity_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProblemDetail(BaseModel):
    id: UUID
    title: str
    description: str
    root_conjecture_id: UUID | None
    progress: float = 0.0
    root_status: str | None = None
    total_conjectures: int = 0
    proved_conjectures: int = 0
    open_conjectures: int = 0
    decomposed_conjectures: int = 0
    disproved_conjectures: int = 0
    invalid_conjectures: int = 0
    total_leaves: int = 0
    proved_leaves: int = 0
    last_activity_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProblemListResponse(BaseModel):
    problems: list[ProblemResponse]
    total: int


class ProblemTreeNode(BaseModel):
    id: UUID
    lean_statement: str
    description: str
    status: str
    priority: str
    proved_by: AuthorResponse | None = None
    disproved_by: AuthorResponse | None = None
    comment_count: int = 0
    children: list["ProblemTreeNode"] = []

    model_config = ConfigDict(from_attributes=True)


class ProblemTreeResponse(BaseModel):
    root: ProblemTreeNode | None = None


class OverviewProblem(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    progress: float


class OverviewNode(BaseModel):
    id: UUID
    description: str
    status: str
    priority: str
    comment_count: int = 0
    last_activity_at: datetime | None = None
    proved_by: str | None = None
    parent_id: UUID | None = None
    summary: str | None = None


class ProblemOverview(BaseModel):
    problem: OverviewProblem
    tree: list[OverviewNode]
