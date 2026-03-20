"""HTTP client for the Kimina Lean Server."""

from dataclasses import dataclass, field
from uuid import uuid4

import httpx

from app.config import settings

_TIMEOUT = 120.0  # HTTP timeout (Kimina has its own internal timeout too)
_LEAN_TIMEOUT = 60  # Lean compilation timeout sent to Kimina
_TRIVIALITY_TIMEOUT = 10  # short timeout — if tactics can't solve in 10s, it's non-trivial

# Unified list of forbidden keywords — checked case-insensitively against
# agent-submitted code (tactics, full programs, etc.).
FORBIDDEN_KEYWORDS = [
    "sorry",
    "axiom ",
    "axiom\n",
    "axiom\t",
    "constant ",
    "opaque ",
    "unsafe ",
    "native_decide",
    "implemented_by",
    "unsafeAxiom",
    "@[extern",
    "Lean.Elab",
    "elab ",
    "macro ",
    "syntax ",
    "#eval ",
    "#eval\n",
    "#eval\t",
    "#check ",
    "#check\n",
    "#check\t",
]

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


@dataclass
class LeanResult:
    status: str  # "passed" | "rejected" | "timeout"
    error: str | None = None
    messages: list[dict] | None = field(default=None)


async def typecheck(lean_statement: str) -> LeanResult:
    """Typecheck a Lean statement (for conjecture submission).

    Wraps the statement as `theorem _check : <statement> := by sorry` and sends
    to Lean CI. This validates the statement is well-typed without requiring a proof.
    The sorry warning is intentionally ignored here — it's our wrapper, not the agent's.
    """
    wrapped = f"import Mathlib\n\ntheorem _polyproof_typecheck : {lean_statement} := by sorry"
    return await _send_to_lean(wrapped, allow_sorry=True)


async def triviality_check(lean_statement: str) -> bool:
    """Returns True if the statement is trivially provable.

    Attempts to prove the statement using standard automation tactics with a
    short timeout. If the tactics succeed, the statement is considered trivial.
    """
    code = (
        f"import Mathlib\n\n"
        f"theorem _trivial : {lean_statement} := by\n"
        f"  first | decide | simp | omega | norm_num | ring"
    )
    result = await _send_to_lean(code, allow_sorry=False, timeout=_TRIVIALITY_TIMEOUT)
    return result.status == "passed"


async def verify(lean_code: str) -> LeanResult:
    """Verify a complete Lean proof (for /verify endpoint backward compatibility).

    Sends the code as-is to Lean CI. Rejects proofs that use sorry.
    """
    return await _send_to_lean(lean_code, allow_sorry=False)


async def verify_proof(lean_statement: str, agent_tactics: str) -> LeanResult:
    """Verify a proof against a specific conjecture statement.

    Constructs a locked Lean file with the conjecture's type as the theorem
    statement and the agent's tactics as the proof body. Also runs #print axioms
    to ensure only standard axioms are used.
    """
    # Scan for forbidden constructs in agent tactics
    tactics_lower = agent_tactics.lower()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword.lower() in tactics_lower:
            return LeanResult(
                status="rejected",
                error=f"Proof uses forbidden construct: {keyword.strip()}",
            )

    # Construct locked Lean file — indent every line of tactics
    indented = "\n  ".join(agent_tactics.splitlines())
    code = (
        f"import Mathlib\n\n"
        f"theorem _polyproof_proof : {lean_statement} := by\n"
        f"  {indented}\n\n"
        f"#print axioms _polyproof_proof\n"
    )

    result = await _send_to_lean(code, allow_sorry=False)

    if result.status == "passed":
        result = _check_axioms(result)

    return result


def _check_axioms(result: LeanResult) -> LeanResult:
    """Check that only standard axioms are used.

    Parses the #print axioms output from Lean messages and rejects proofs
    that rely on non-standard axioms (e.g. custom axioms or sorryAx).
    """
    if not result.messages:
        return LeanResult(
            status="rejected",
            error="No axiom information returned from Lean — proof cannot be verified",
        )

    found_axiom_info = False
    for msg in result.messages:
        data = msg.get("data", "")

        # Check for sorryAx anywhere in the output
        if "sorryAx" in data:
            return LeanResult(status="rejected", error="Proof uses sorry")

        # Parse the axiom list from #print axioms output
        if msg.get("severity") == "info" and "depends on axioms" in data:
            found_axiom_info = True
            start = data.find("[")
            end = data.find("]")
            if start >= 0 and end >= 0:
                axioms = {a.strip() for a in data[start + 1 : end].split(",")}
                unknown = axioms - ALLOWED_AXIOMS
                if unknown:
                    return LeanResult(
                        status="rejected",
                        error=f"Proof uses non-standard axioms: {', '.join(sorted(unknown))}",
                    )

        # '#print axioms' with no dependencies outputs
        # "... declaration does not depend on any axioms"
        if msg.get("severity") == "info" and "does not depend on any axioms" in data:
            found_axiom_info = True

    if not found_axiom_info:
        return LeanResult(
            status="rejected",
            error="No axiom information returned from Lean — proof cannot be verified",
        )

    return result


async def _send_to_lean(
    lean_code: str, *, allow_sorry: bool, timeout: int = _LEAN_TIMEOUT
) -> LeanResult:
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
                    "timeout": timeout,
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
                    messages=messages,
                )

            # Path 3: Reject code that uses 'sorry' (unless allowed for typechecking)
            if not allow_sorry:
                sorry_warnings = [
                    msg.get("data", "")
                    for msg in messages
                    if msg.get("severity") == "warning" and "sorry" in msg.get("data", "").lower()
                ]
                if sorry_warnings:
                    return LeanResult(
                        status="rejected",
                        error="Proof uses 'sorry'",
                        messages=messages,
                    )

            # Path 4: Reject code with forbidden keywords (axiom exploits, etc.)
            # These bypass Lean's logic checker without producing warnings.
            # Note: For locked-signature proofs (verify_proof), agent tactics are
            # already checked before assembly. This check is intentionally kept
            # for backward compatibility with the free-form verify() path.
            if not allow_sorry:
                code_lower = lean_code.lower()
                for keyword in FORBIDDEN_KEYWORDS:
                    if keyword.lower() in code_lower:
                        return LeanResult(
                            status="rejected",
                            error=f"Proof uses forbidden keyword: {keyword.strip()}",
                            messages=messages,
                        )

            # No errors, sorry, or forbidden keywords — compilation passed
            return LeanResult(status="passed", messages=messages)

    except httpx.TimeoutException:
        return LeanResult(status="timeout", error="Lean verification timed out")
    except httpx.HTTPError as e:
        return LeanResult(status="timeout", error=f"Failed to connect to Lean server: {e}")
