"""HTTP client for the Kimina Lean Server."""

from dataclasses import dataclass
from uuid import uuid4

import httpx

from app.config import settings

_TIMEOUT = 120.0  # HTTP timeout (Kimina has its own internal timeout too)
_LEAN_TIMEOUT = 60  # Lean compilation timeout sent to Kimina


@dataclass
class LeanResult:
    status: str  # "passed" | "rejected" | "timeout"
    error: str | None = None


async def verify(lean_code: str) -> LeanResult:
    """Send lean code to the Kimina Lean Server for verification.

    Kimina API format:
      POST /verify
      {"codes": [{"custom_id": "...", "proof": "..."}], "timeout": 60}

    Response:
      {"results": [{"custom_id": "...", "error": null|"...", "response": {...}}]}

    If error is null, the proof compiled successfully (passed).
    If error is a string, the proof failed (rejected or timeout).
    """
    request_id = uuid4().hex[:12]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{settings.LEAN_SERVER_URL}/verify",
                json={
                    "codes": [{"custom_id": request_id, "proof": lean_code}],
                    "timeout": _LEAN_TIMEOUT,
                },
            )

            if response.status_code != 200:
                return LeanResult(
                    status="rejected",
                    error=f"Lean server returned HTTP {response.status_code}",
                )

            data = response.json()
            results = data.get("results", [])

            if not results:
                return LeanResult(status="rejected", error="No results from Lean server")

            result = results[0]
            error = result.get("error")

            if error is None:
                return LeanResult(status="passed")

            # Kimina returns timeout errors as error strings containing "timed out"
            if "timed out" in error.lower():
                return LeanResult(status="timeout", error=error)

            return LeanResult(status="rejected", error=error)

    except httpx.TimeoutException:
        return LeanResult(status="timeout", error="Lean verification timed out")
    except httpx.HTTPError as e:
        return LeanResult(status="timeout", error=f"Failed to connect to Lean server: {e}")
