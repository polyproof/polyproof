from uuid import UUID

from pydantic import BaseModel, Field


class ProofSubmit(BaseModel):
    lean_code: str = Field(..., min_length=1, max_length=100_000)


class ProofResult(BaseModel):
    status: str
    conjecture_id: UUID
    assembly_triggered: bool = False
    parent_proved: bool = False
    error: str | None = None
    message: str | None = None


class DisproofSubmit(BaseModel):
    lean_code: str = Field(..., min_length=1, max_length=100_000)


class DisproofResult(BaseModel):
    status: str
    conjecture_id: UUID
    descendants_invalidated: int = 0
    error: str | None = None
    message: str | None = None
