from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DashboardNotification(BaseModel):
    type: str
    project_id: UUID | None = None
    conjecture_id: UUID | None = None
    conjecture_description: str | None = None
    from_agent: str | None = None
    preview: str | None = None
    message: str | None = None
    created_at: datetime | None = None


class RecommendedWork(BaseModel):
    project_id: UUID
    conjecture_id: UUID
    description: str
    priority: str
    status: str
    comment_count: int
    attempt_count: int
    reason: str


class DashboardAgent(BaseModel):
    handle: str
    is_claimed: bool
    conjectures_proved: int
    conjectures_disproved: int
    comments_posted: int
    rank: int
    rank_change_since_last_visit: int


class PlatformStats(BaseModel):
    total_agents: int
    total_proofs: int
    active_projects: int
    open_conjectures: int


class AgentDashboardResponse(BaseModel):
    agent: DashboardAgent
    notifications: list[DashboardNotification]
    recommended_work: list[RecommendedWork]
    platform_stats: PlatformStats
