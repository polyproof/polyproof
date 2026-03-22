"""HTTP client for the Kimina Lean Server.

v4 entry points:
- typecheck(lean_statement)          — wrap with sorry, validate statement is well-typed
- verify_proof(lean_statement, tactics, conjecture_id) — locked proof signature
- verify_disproof(lean_statement, tactics, conjecture_id) — locked disproof (negated)
- verify_sorry_proof(sorry_proof_code) — compile sorry-proof as-is (with sorry allowed)
- verify_freeform(code)              — compile as-is, reject sorry
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import httpx

from app.config import settings

_TIMEOUT = 120.0  # HTTP timeout (Kimina has its own internal timeout too)
_LEAN_TIMEOUT = 60  # Lean compilation timeout sent to Kimina

# Forbidden keywords checked against agent-submitted code (tactics, full programs).
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


async def typecheck(lean_statement: str, lean_header: str | None = None) -> LeanResult:
    """Typecheck a Lean statement (for project creation / conjecture validation).

    Wraps as ``theorem _polyproof_check : <statement> := by sorry`` and compiles.
    The sorry warning is intentionally ignored — it's our wrapper, not agent code.
    """
    header = _build_header(lean_header)
    wrapped = f"{header}theorem _polyproof_check : {lean_statement} := by sorry"
    return await _send_to_lean(wrapped, allow_sorry=True)


async def verify_proof(
    lean_statement: str,
    tactics: str,
    conjecture_id: UUID,
    lean_header: str | None = None,
) -> LeanResult:
    """Verify a proof against a conjecture's lean_statement.

    Constructs: ``theorem proof_<id> : <statement> := by <tactics>``
    Then runs ``#print axioms`` to reject non-standard axioms.
    """
    rejected = _check_forbidden(tactics)
    if rejected:
        return rejected

    header = _build_header(lean_header)
    safe_id = str(conjecture_id).replace("-", "_")
    indented = "\n  ".join(tactics.splitlines())
    code = (
        f"{header}"
        f"theorem proof_{safe_id} : {lean_statement} := by\n"
        f"  {indented}\n\n"
        f"#print axioms proof_{safe_id}\n"
    )

    result = await _send_to_lean(code, allow_sorry=False)
    if result.status == "passed":
        result = _check_axioms(result)
    return result


async def verify_disproof(
    lean_statement: str,
    tactics: str,
    conjecture_id: UUID,
    lean_header: str | None = None,
) -> LeanResult:
    r"""Verify a disproof against a conjecture's lean_statement.

    Constructs: ``theorem disproof_<id> : ¬(<statement>) := by <tactics>``
    Then runs ``#print axioms`` to reject non-standard axioms.
    """
    rejected = _check_forbidden(tactics)
    if rejected:
        return rejected

    header = _build_header(lean_header)
    safe_id = str(conjecture_id).replace("-", "_")
    indented = "\n  ".join(tactics.splitlines())
    code = (
        f"{header}"
        f"theorem disproof_{safe_id} : ¬({lean_statement}) := by\n"
        f"  {indented}\n\n"
        f"#print axioms disproof_{safe_id}\n"
    )

    result = await _send_to_lean(code, allow_sorry=False)
    if result.status == "passed":
        result = _check_axioms(result)
    return result


async def verify_sorry_proof(sorry_proof_code: str, lean_header: str | None = None) -> LeanResult:
    """Compile a sorry-proof as-is (typechecks with sorry allowed).

    Used during decomposition to validate the sorry-proof structure.
    The header is prepended if the sorry-proof doesn't already include imports.
    """
    if "import" not in sorry_proof_code[:50]:
        sorry_proof_code = _build_header(lean_header) + sorry_proof_code
    return await _send_to_lean(sorry_proof_code, allow_sorry=True)


async def verify_freeform(code: str) -> LeanResult:
    """Compile code as-is for the /verify endpoint (without conjecture_id).

    Rejects sorry and forbidden keywords.
    """
    return await _send_to_lean(code, allow_sorry=False)


def _build_header(lean_header: str | None) -> str:
    """Build the Lean file header (import + optional project-level context)."""
    parts = ["import Mathlib\n"]
    if lean_header:
        parts.append(lean_header.strip() + "\n")
    parts.append("\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_forbidden(tactics: str) -> LeanResult | None:
    """Scan agent tactics for forbidden constructs. Returns LeanResult on rejection."""
    tactics_lower = tactics.lower()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword.lower() in tactics_lower:
            return LeanResult(
                status="rejected",
                error=f"Proof uses forbidden construct: {keyword.strip()}",
            )
    return None


def _check_axioms(result: LeanResult) -> LeanResult:
    """Check that only standard axioms are used.

    Parses the ``#print axioms`` output from Lean messages and rejects proofs
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

        # '#print axioms' with no dependencies
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

            # No errors — compilation passed
            return LeanResult(status="passed", messages=messages)

    except httpx.TimeoutException:
        return LeanResult(status="timeout", error="Compilation timed out (60s limit).")
    except httpx.HTTPError as e:
        return LeanResult(status="timeout", error=f"Failed to connect to Lean server: {e}")
