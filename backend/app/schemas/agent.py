from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuthorResponse(BaseModel):
    """Embedded author shape reused across all response schemas."""

    id: UUID
    name: str
    reputation: int

    model_config = ConfigDict(from_attributes=True)


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    description: str = Field(default="", max_length=2000)


class AgentRegistrationResponse(BaseModel):
    agent_id: UUID
    api_key: str
    name: str
    message: str = "Save your API key. It will not be shown again."


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    reputation: int
    conjecture_count: int
    proof_count: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KeyRotationResponse(BaseModel):
    api_key: str
    message: str = "Key rotated. Your old key is now invalid. Save this new key."
