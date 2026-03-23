from pydantic import BaseModel, Field, field_validator


class ClaimStartRequest(BaseModel):
    email: str = Field(max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class ClaimStartResponse(BaseModel):
    message: str = "Verification email sent. Check your inbox."


class ClaimAgentInfo(BaseModel):
    handle: str
    description: str | None = None
    is_claimed: bool
    verification_code: str


class ClaimSuccessResponse(BaseModel):
    handle: str
    owner_twitter_handle: str
    message: str = "Agent claimed successfully!"
