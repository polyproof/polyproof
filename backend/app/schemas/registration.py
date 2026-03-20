from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    description: str = Field(..., min_length=1, max_length=5000)

    @field_validator("name")
    @classmethod
    def name_not_reserved(cls, v: str) -> str:
        reserved = {"me", "register"}
        if v.lower() in reserved:
            msg = f"The name '{v}' is reserved and cannot be used"
            raise ValueError(msg)
        return v


class ChallengeResponse(BaseModel):
    challenge_id: UUID
    challenge_statement: str
    instructions: str
    attempts_remaining: int


class VerifyRequest(BaseModel):
    challenge_id: UUID
    name: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    description: str = Field(..., min_length=1, max_length=5000)
    proof: str = Field(..., min_length=1, max_length=100_000)

    @field_validator("name")
    @classmethod
    def name_not_reserved(cls, v: str) -> str:
        reserved = {"me", "register"}
        if v.lower() in reserved:
            msg = f"The name '{v}' is reserved and cannot be used"
            raise ValueError(msg)
        return v


class RegisterResponse(BaseModel):
    agent_id: UUID
    api_key: str
    name: str
    message: str
