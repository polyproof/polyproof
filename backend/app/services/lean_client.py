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


async def typecheck(lean_statement: str) -> LeanResult:
    """Typecheck a Lean statement (for conjecture submission).

    Wraps the statement as `theorem _check : <statement> := by sorry` and sends
    to Lean CI. This validates the statement is well-typed without requiring a proof.
    The sorry warning is intentionally ignored here — it's our wrapper, not the agent's.
    """
    wrapped = f"theorem _polyproof_typecheck : {lean_statement} := by sorry"
    return await _send_to_lean(wrapped, allow_sorry=True)


async def verify(lean_code: str) -> LeanResult:
    """Verify a complete Lean proof (for proof submission and /verify endpoint).

    Sends the code as-is to Lean CI. Rejects proofs that use sorry.
    """
    return await _send_to_lean(lean_code, allow_sorry=False)


async def _send_to_lean(lean_code: str, *, allow_sorry: bool) -> LeanResult:
    """Send lean code to the Kimina Lean Server.

    Kimina API:
      POST /verify
      {"codes": [{"custom_id": "...", "proof": "..."}], "timeout": 60}

    Response has two error paths:
      1. Top-level "error" field: timeout/crash (error is a string)
      2. response.messages with severity "error": compilation failure

    If allow_sorry is False, also rejects code that uses sorry.
    """
    request_id = uuid4().hex[:12]

    try:
        headers: dict[str, str] = {}
        if settings.LEAN_SERVER_SECRET:
            headers["X-Lean-Secret"] = settings.LEAN_SERVER_SECRET

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{settings.LEAN_SERVER_URL}/verify",
                headers=headers,
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

            # Path 1: Top-level error (timeout, REPL crash, etc.)
            top_error = result.get("error")
            if top_error is not None:
                if "timed out" in top_error.lower():
                    return LeanResult(status="timeout", error=top_error)
                return LeanResult(status="rejected", error=top_error)

            # Path 2: Check response.messages for compilation errors
            resp = result.get("response", {})
            messages = resp.get("messages", []) if resp else []

            error_messages = [
                msg.get("data", "Unknown error")
                for msg in messages
                if msg.get("severity") == "error"
            ]

            if error_messages:
                return LeanResult(
                    status="rejected",
                    error="\n".join(error_messages),
                )

            # Path 3: Reject code that uses 'sorry' (unless allowed for typechecking)
            if not allow_sorry:
                sorry_warnings = [
                    msg.get("data", "")
                    for msg in messages
                    if msg.get("severity") == "warning"
                    and "sorry" in msg.get("data", "").lower()
                ]
                if sorry_warnings:
                    return LeanResult(
                        status="rejected",
                        error="Proof uses 'sorry'",
                    )

            # No errors or sorry — compilation passed
            return LeanResult(status="passed")

    except httpx.TimeoutException:
        return LeanResult(status="timeout", error="Lean verification timed out")
    except httpx.HTTPError as e:
        return LeanResult(status="timeout", error=f"Failed to connect to Lean server: {e}")
