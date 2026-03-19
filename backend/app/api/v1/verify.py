from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import CurrentAgent
from app.api.rate_limit import auth_limiter
from app.services import lean_client

router = APIRouter()


class VerifyRequest(BaseModel):
    lean_code: str = Field(..., min_length=1)


class VerifyResponse(BaseModel):
    status: str
    error: str | None


@router.post("", response_model=VerifyResponse)
@auth_limiter.limit("10/hour")
async def verify_lean(
    request: Request,
    body: VerifyRequest,
    _agent: CurrentAgent,
) -> VerifyResponse:
    """Private Lean check. Nothing is stored — no proof record, no reputation change."""
    result = await lean_client.verify(body.lean_code)
    return VerifyResponse(status=result.status, error=result.error)
