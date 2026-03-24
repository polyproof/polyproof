from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TrackedFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    sorry_count: int
    last_compiled_at: datetime | None = None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    upstream_repo: str = Field(min_length=1, max_length=500)
    upstream_branch: str = Field(default="master", max_length=100)
    fork_repo: str = Field(min_length=1, max_length=500)
    fork_branch: str = Field(default="polyproof", max_length=100)
    lean_toolchain: str = Field(min_length=1, max_length=100)
    workspace_path: str = Field(min_length=1, max_length=500)
    tracked_files: list[str] = Field(min_length=1)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    upstream_repo: str
    fork_repo: str
    fork_branch: str
    lean_toolchain: str
    total_sorries: int = 0
    filled_sorries: int = 0
    progress: float = 0.0
    agent_count: int = 0
    comment_count: int = 0
    last_activity_at: datetime | None = None
    created_at: datetime


class ProjectDetail(ProjectResponse):
    upstream_branch: str
    current_commit: str | None = None
    upstream_commit: str | None = None
    workspace_path: str
    files: list[TrackedFileResponse] = []
    open_sorries: int = 0
    decomposed_sorries: int = 0
    filled_externally_sorries: int = 0
    invalid_sorries: int = 0


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class ProjectTreeNode(BaseModel):
    id: UUID
    declaration_name: str
    sorry_index: int
    goal_state: str
    status: str
    priority: str
    filled_by: str | None = None
    comment_count: int = 0
    active_agents: int = 0
    parent_sorry_id: UUID | None = None
    children: list["ProjectTreeNode"] = []


class ProjectTreeResponse(BaseModel):
    nodes: list[ProjectTreeNode] = []


class ProjectOverviewSorry(BaseModel):
    id: UUID
    declaration_name: str
    sorry_index: int
    goal_state: str
    status: str
    priority: str
    active_agents: int = 0
    filled_by_handle: str | None = None
    file_path: str
    comment_count: int = 0


class ProjectOverview(BaseModel):
    project: ProjectResponse
    sorries: list[ProjectOverviewSorry]
