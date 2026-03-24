"""HTTP client for the Kimina Lean Server.

v5 entry points:
- typecheck(goal_state, project_id)      — wrap with sorry, validate goal is well-typed
- verify_fill(goal_state, tactics, sorry_id, project_id) — locked fill signature
- verify_freeform(code, project_id)      — compile as-is, reject sorry
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


async def typecheck(
    goal_state: str,
    project_id: UUID | None = None,
) -> LeanResult:
    """Typecheck a goal state (for sorry validation).

    Wraps as ``theorem _polyproof_check : <goal_state> := by sorry`` and compiles.
    The sorry warning is intentionally ignored -- it's our wrapper, not agent code.
    """
    header = _build_header(project_id)
    wrapped = f"{header}theorem _polyproof_check : {goal_state} := by sorry"
    return await _send_to_lean(wrapped, allow_sorry=True)


async def verify_fill(
    goal_state: str,
    tactics: str,
    sorry_id: UUID,
    project_id: UUID | None = None,
    allow_sorry: bool = False,
    import_path: str | None = None,
) -> LeanResult:
    """Verify a fill against a sorry's goal state.

    Constructs: ``theorem fill_<id> : <goal_state> := by <tactics>``
    Then runs ``#print axioms`` to reject non-standard axioms.

    When allow_sorry=True (used by /verify), sorry is permitted for incremental
    testing. Forbidden keyword checks still apply for everything except sorry.
    """
    if allow_sorry:
        # Check forbidden keywords except sorry
        tactics_lower = tactics.lower()
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword.lower() == "sorry":
                continue
            if keyword.lower() in tactics_lower:
                return LeanResult(
                    status="rejected",
                    error=f"Tactics use forbidden construct: {keyword.strip()}",
                )
    else:
        rejected = _check_forbidden(tactics)
        if rejected:
            return rejected

    header = _build_header(project_id, import_path=import_path)
    safe_id = str(sorry_id).replace("-", "_")
    indented = "\n  ".join(tactics.splitlines())
    code = (
        f"{header}"
        f"theorem fill_{safe_id} : {goal_state} := by\n"
        f"  {indented}\n\n"
        f"#print axioms fill_{safe_id}\n"
    )

    result = await _send_to_lean(code, allow_sorry=allow_sorry)
    if result.status == "passed" and not allow_sorry:
        result = _check_axioms(result)
    return result


async def verify_freeform(
    code: str,
    project_id: UUID | None = None,
    import_path: str | None = None,
) -> LeanResult:
    """Compile code as-is for the /verify endpoint (freeform).

    Rejects sorry and forbidden keywords.
    """
    if project_id is not None:
        header = _build_header(project_id, import_path=import_path)
        if "import" not in code[:50]:
            code = header + code
    return await _send_to_lean(code, allow_sorry=False)


def _build_header(project_id: UUID | None = None, *, import_path: str | None = None) -> str:
    """Build the Lean file header from the file path.

    Converts a file path like ``Carleson/Foo/Bar.lean`` into
    ``import Carleson.Foo.Bar``. Falls back to ``import Mathlib`` if no
    import_path is provided.
    """
    if import_path:
        module = import_path.replace("/", ".").removesuffix(".lean")
        return f"import {module}\n\n"
    return "import Mathlib\n\n"


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
                error=f"Tactics use forbidden construct: {keyword.strip()}",
            )
    return None


def _check_axioms(result: LeanResult) -> LeanResult:
    """Check that only standard axioms are used.

    Parses the ``#print axioms`` output from Lean messages and rejects fills
    that rely on non-standard axioms (e.g. custom axioms or sorryAx).
    """
    if not result.messages:
        return LeanResult(
            status="rejected",
            error="No axiom information returned from Lean -- fill cannot be verified",
        )

    found_axiom_info = False
    for msg in result.messages:
        data = msg.get("data", "")

        # Check for sorryAx anywhere in the output
        if "sorryAx" in data:
            return LeanResult(status="rejected", error="Tactics use sorry")

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
                        error=f"Tactics use non-standard axioms: {', '.join(sorted(unknown))}",
                    )

        # '#print axioms' with no dependencies
        if msg.get("severity") == "info" and "does not depend on any axioms" in data:
            found_axiom_info = True

    if not found_axiom_info:
        return LeanResult(
            status="rejected",
            error="No axiom information returned from Lean -- fill cannot be verified",
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
                        error="Tactics use 'sorry'",
                        messages=messages,
                    )

            # No errors -- compilation passed
            return LeanResult(status="passed", messages=messages)

    except httpx.TimeoutException:
        return LeanResult(status="timeout", error="Compilation timed out (60s limit).")
    except httpx.HTTPError as e:
        return LeanResult(status="timeout", error=f"Failed to connect to Lean server: {e}")
