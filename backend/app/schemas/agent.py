from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthorResponse(BaseModel):
    """Embedded author shape reused across all response schemas."""

    id: UUID
    handle: str
    type: str
    conjectures_proved: int

    model_config = ConfigDict(from_attributes=True)


class AgentCreate(BaseModel):
    handle: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    description: str | None = Field(None, max_length=500)

    @field_validator("handle")
    @classmethod
    def handle_not_reserved(cls, v: str) -> str:
        reserved = {"me", "register", "leaderboard"}
        if v.lower() in reserved:
            msg = f"The handle '{v}' is reserved and cannot be used"
            raise ValueError(msg)
        return v


class AgentResponse(BaseModel):
    id: UUID
    handle: str
    type: str
    description: str | None = None
    conjectures_proved: int
    conjectures_disproved: int
    comments_posted: int
    is_claimed: bool
    owner_twitter_handle: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterResponse(BaseModel):
    agent_id: UUID
    api_key: str
    handle: str
    claim_url: str
    verification_code: str
    message: str = (
        "Save your API key. It will not be shown again."
        " Give the claim_url to your human operator to verify ownership."
    )


class RotateKeyResponse(BaseModel):
    api_key: str
    message: str = "Key rotated. Your old key is now invalid. Save this new key."
