from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AuthorResponse


class RootConjectureCreate(BaseModel):
    lean_statement: str = Field(..., min_length=1, max_length=100_000)
    description: str = Field(..., min_length=1, max_length=10_000)


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=10_000)
    root_conjecture: RootConjectureCreate


class ProjectResponse(BaseModel):
    id: UUID
    title: str
    description: str
    root_conjecture_id: UUID | None
    root_status: str | None = None
    progress: float = 0.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectDetail(BaseModel):
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


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class ProjectTreeNode(BaseModel):
    id: UUID
    lean_statement: str
    description: str
    status: str
    priority: str
    proved_by: AuthorResponse | None = None
    disproved_by: AuthorResponse | None = None
    comment_count: int = 0
    children: list["ProjectTreeNode"] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectTreeResponse(BaseModel):
    root: ProjectTreeNode | None = None
