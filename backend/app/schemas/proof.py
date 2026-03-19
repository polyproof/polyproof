from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AuthorResponse


class ProofCreate(BaseModel):
    lean_proof: str = Field(..., min_length=1)
    description: str | None = None


class ProofResponse(BaseModel):
    id: UUID
    lean_proof: str
    description: str | None
    verification_status: str
    verification_error: str | None
    author: AuthorResponse
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
