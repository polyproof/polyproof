"""Search tactic suggestions (exact?, apply?, rw?, simp?)."""

import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter
from app.errors import NotFoundError
from app.models.project import Project
from app.models.sorry import Sorry
from app.models.tracked_file import TrackedFile
from app.services import github_service, lean_client

logger = logging.getLogger(__name__)
router = APIRouter()


class SuggestRequest(BaseModel):
    sorry_id: UUID = Field(..., description="UUID of the sorry to search")
    tactic: Literal["exact?", "apply?", "rw?", "simp?"] = Field(
        ..., description="Search tactic to run"
    )


class SuggestResult(BaseModel):
    status: str  # "ok", "no_results", "error", "timeout"
    suggestions: list[str] | None = None
    error: str | None = None
    messages: list[dict] | None = None


@router.post("", response_model=SuggestResult)
@auth_limiter.limit("30/hour")
async def suggest_tactics(
    request: Request,
    body: SuggestRequest,
    _agent: CurrentAgent,
    db: DbSession,
) -> SuggestResult:
    """Run a search tactic against a sorry and return suggestions.

    Search tactics are slow (30-120s). Use sparingly.
    """
    sorry = await db.get(Sorry, body.sorry_id)
    if not sorry:
        raise NotFoundError("Sorry", f"No sorry with id {body.sorry_id}")

    tracked_file = await db.get(TrackedFile, sorry.file_id)
    if not tracked_file:
        raise NotFoundError("File", "Tracked file not found")

    project = await db.get(Project, sorry.project_id)
    if not project:
        raise NotFoundError("Project")

    # Fetch source file from the fork
    try:
        repo = github_service.parse_repo(project.fork_repo)
        file_content, _sha = await github_service.get_file_content(
            repo, tracked_file.file_path, project.fork_branch
        )
    except github_service.GitHubError as e:
        return SuggestResult(status="error", error=f"Could not fetch source file: {e}")

    # Use verify_in_file to patch the sorry with the search tactic and compile.
    # This goes through the standard keyword safety checks.
    result = await lean_client.verify_in_file(
        file_content=file_content,
        declaration_name=sorry.declaration_name,
        tactics=body.tactic,
        allow_sorry=True,
        sorry_index=sorry.sorry_index,
    )

    if result.status == "timeout":
        return SuggestResult(status="timeout", error="Search tactic timed out")

    # Parse suggestions from messages
    suggestions = _parse_suggestions(result.messages)

    return SuggestResult(
        status="ok" if suggestions else "no_results",
        suggestions=suggestions or None,
        messages=result.messages,
    )


def _parse_suggestions(messages: list[dict] | None) -> list[str]:
    """Parse search tactic suggestions from Lean messages.

    All search tactics (exact?, apply?, rw?, simp?) use the same
    "Try this: <tactic>" output format.
    """
    if not messages:
        return []

    suggestions = []
    for msg in messages:
        if msg.get("severity") != "info":
            continue
        data = msg.get("data", "")
        if not data:
            continue

        for line in data.split("\n"):
            line = line.strip()
            if line.startswith("Try this:"):
                suggestion = line.removeprefix("Try this:").strip()
                if suggestion:
                    suggestions.append(suggestion)

    return suggestions
