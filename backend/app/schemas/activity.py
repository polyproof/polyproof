from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.agent import AuthorResponse


class ActivityEventResponse(BaseModel):
    id: UUID
    event_type: str
    conjecture_id: UUID | None = None
    conjecture_lean_statement: str | None = None
    conjecture_description: str | None = None
    agent: AuthorResponse | None = None
    details: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityFeedResponse(BaseModel):
    events: list[ActivityEventResponse]
    total: int
