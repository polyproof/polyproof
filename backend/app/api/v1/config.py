"""Platform configuration endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ConfigResponse(BaseModel):
    lean_version: str
    mathlib_version: str
    api_version: str


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Return platform configuration (Lean version, mathlib version, API version)."""
    return ConfigResponse(
        lean_version="v4.8.0",
        mathlib_version="2026-04-01",
        api_version="v1",
    )
