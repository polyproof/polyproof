"""HTTP client for the Kimina Lean Server."""

from dataclasses import dataclass

import httpx

from app.config import settings

_TIMEOUT = 60.0  # seconds


@dataclass
class LeanResult:
    status: str  # "passed" | "rejected" | "timeout"
    error: str | None = None


async def verify(lean_code: str) -> LeanResult:
    """Send lean code to the Kimina Lean Server for verification.

    Returns a LeanResult with status and optional error message.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{settings.LEAN_SERVER_URL}/verify",
                json={"lean_code": lean_code},
            )
            data = response.json()
            return LeanResult(
                status=data.get("status", "rejected"),
                error=data.get("error"),
            )
    except httpx.TimeoutException:
        return LeanResult(status="timeout", error="Lean verification timed out")
    except httpx.HTTPError:
        return LeanResult(status="timeout", error="Failed to connect to Lean server")
