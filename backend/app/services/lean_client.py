"""HTTP client for the Kimina Lean Server.

v5 entry points:
- verify_in_file(file_content, declaration_name, tactics) — compile by patching the source file
- verify_freeform(code, import_path)                      — compile as-is for exploration
- typecheck(goal_state, import_path)                      — wrap with sorry, validate goal
"""

from dataclasses import dataclass, field
from uuid import uuid4

import httpx

from app.config import settings

_TIMEOUT = 120.0  # HTTP timeout for short compilations
_FILE_TIMEOUT = 360.0  # HTTP timeout for full-file compilation
_LEAN_TIMEOUT = 60  # Lean compilation timeout for short code
_FILE_LEAN_TIMEOUT = 300  # Lean compilation timeout for full files

# Forbidden keywords for fill tactics (code that gets committed).
# Sorry is checked separately via axiom analysis, not keyword scan.
FILL_FORBIDDEN_KEYWORDS = [
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

# Reduced list for freeform exploration. Allows #check, #eval, sorry
# (freeform code is never committed — it's compile-and-discard).
FREEFORM_FORBIDDEN_KEYWORDS = [
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
]

ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


@dataclass
class LeanSorry:
    """A sorry position + goal state from the Lean REPL."""

    line: int
    col: int
    end_line: int
    end_col: int
    goal: str  # tactic goal state, e.g. "n : Nat\n⊢ n + 0 = n"


@dataclass
class LeanResult:
    status: str  # "passed" | "rejected" | "timeout"
    error: str | None = None
    messages: list[dict] | None = field(default=None)
    sorries: list[LeanSorry] | None = field(default=None)


async def verify_in_file(
    file_content: str,
    declaration_name: str,
    tactics: str,
    allow_sorry: bool = False,
) -> LeanResult:
    """Verify tactics by patching them into the actual source file.

    This is the primary verification path. It replaces the sorry in the
    declaration with the agent's tactics, then compiles the full file.
    The surrounding code provides all the context (imports, variables,
    namespaces, typeclasses) that the sorry originally had.

    When allow_sorry=False (fill submissions), appends ``#print axioms``
    and rejects if the filled declaration depends on ``sorryAx``.
    """
    from app.services.github_service import GitHubError, replace_sorry_in_declaration

    # Check forbidden keywords on the tactics only (not the full file)
    rejected = _check_keywords(tactics, FILL_FORBIDDEN_KEYWORDS)
    if rejected:
        return rejected

    # Patch the sorry with the agent's tactics
    try:
        patched = replace_sorry_in_declaration(file_content, declaration_name, tactics)
    except GitHubError as e:
        return LeanResult(status="rejected", error=str(e))

    # For fill submissions, append axiom check on the specific declaration
    if not allow_sorry:
        patched += f"\n#print axioms {declaration_name}\n"

    # Compile the full patched file — allow_sorry=True because other
    # declarations in the file still have sorry's (that's normal)
    result = await _send_to_lean(
        patched, allow_sorry=True, timeout=_FILE_LEAN_TIMEOUT
    )

    # For fill submissions, check that THIS declaration doesn't use sorryAx
    if result.status == "passed" and not allow_sorry:
        result = _check_axioms(result)

    return result


async def typecheck(
    goal_state: str,
    import_path: str | None = None,
) -> LeanResult:
    """Typecheck a goal state (for sorry validation).

    Wraps as ``theorem _polyproof_check : <goal_state> := by sorry`` and compiles.
    """
    header = _build_header(import_path=import_path)
    wrapped = f"{header}theorem _polyproof_check : {goal_state} := by sorry"
    return await _send_to_lean(wrapped, allow_sorry=True)


async def verify_freeform(
    code: str,
    import_path: str | None = None,
) -> LeanResult:
    """Compile code as-is for freeform exploration.

    Allows #check, #eval, #print, sorry (exploration tools).
    Blocks dangerous constructs (axiom, opaque, unsafe, etc.).
    """
    rejected = _check_freeform_forbidden(code)
    if rejected:
        return rejected

    if import_path is not None and "import" not in code[:50]:
        header = _build_header(import_path=import_path)
        code = header + code
    return await _send_to_lean(code, allow_sorry=True)


def _build_header(*, import_path: str | None = None) -> str:
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


def _check_freeform_forbidden(code: str) -> LeanResult | None:
    """Scan freeform code for dangerous constructs (allows #check, #eval, sorry)."""
    return _check_keywords(code, FREEFORM_FORBIDDEN_KEYWORDS)


def _check_keywords(code: str, keywords: list[str]) -> LeanResult | None:
    """Scan code against a keyword list. Returns LeanResult on rejection."""
    code_lower = code.lower()
    for keyword in keywords:
        if keyword.lower() in code_lower:
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

        # Parse the axiom list from #print axioms output (severity "info" only).
        # We only check for sorryAx in these lines — not in warning messages,
        # which may mention sorryAx from OTHER sorry's elsewhere in the file.
        if msg.get("severity") == "info" and "depends on axioms" in data:
            found_axiom_info = True

            if "sorryAx" in data:
                return LeanResult(status="rejected", error="Tactics use sorry")

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
      {"codes": [{"custom_id": "...", "proof": "..."}], "timeout": N}
    """
    request_id = uuid4().hex[:12]
    http_timeout = _FILE_TIMEOUT if timeout > _LEAN_TIMEOUT else _TIMEOUT

    try:
        headers: dict[str, str] = {}
        if settings.LEAN_SERVER_SECRET:
            headers["X-Lean-Secret"] = settings.LEAN_SERVER_SECRET

        async with httpx.AsyncClient(timeout=http_timeout) as client:
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

            # Path 3: Reject code that uses 'sorry' (unless allowed)
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
                        error="Tactics use 'sorry'",
                        messages=messages,
                    )

            # Parse sorry positions + goal states from the REPL
            raw_sorries = resp.get("sorries", []) if resp else []
            parsed_sorries = [
                LeanSorry(
                    line=s["pos"]["line"],
                    col=s["pos"]["column"],
                    end_line=s["endPos"]["line"],
                    end_col=s["endPos"]["column"],
                    goal=s.get("goal", ""),
                )
                for s in raw_sorries
                if "pos" in s and "endPos" in s
            ]

            # No errors -- compilation passed
            return LeanResult(
                status="passed",
                messages=messages,
                sorries=parsed_sorries or None,
            )

    except httpx.TimeoutException:
        return LeanResult(
            status="timeout", error=f"Compilation timed out ({timeout}s limit)."
        )
    except httpx.HTTPError as e:
        return LeanResult(
            status="timeout", error=f"Failed to connect to Lean server: {e}"
        )
