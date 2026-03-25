"""Lean verification endpoints: sorry-scoped and freeform."""

import logging

from fastapi import APIRouter, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter
from app.errors import NotFoundError
from app.models.project import Project
from app.models.sorry import Sorry
from app.models.tracked_file import TrackedFile
from app.schemas.verify import (
    FreeformVerifyRequest,
    RemainingGoal,
    VerifyRequest,
    VerifyResult,
)
from app.services import github_service, lean_client, project_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=VerifyResult)
@auth_limiter.limit("300/hour")
async def verify_lean(
    request: Request,
    body: VerifyRequest,
    _agent: CurrentAgent,
    db: DbSession,
) -> VerifyResult:
    """Verify tactics against a sorry by patching the actual source file.

    Compiles the full file with the sorry replaced by the agent's tactics.
    Sorry IS allowed (agent is iterating, not submitting a final fill).
    """
    if body.sorry_id is None:
        return VerifyResult(
            status="rejected",
            error="sorry_id is required. Use /verify/freeform for exploration.",
        )

    sorry = await db.get(Sorry, body.sorry_id)
    if not sorry:
        raise NotFoundError("Sorry", f"No sorry with id {body.sorry_id}")

    tracked_file = await db.get(TrackedFile, sorry.file_id)
    if not tracked_file:
        raise NotFoundError("File", "Tracked file not found for this sorry")

    project = await db.get(Project, sorry.project_id)
    if not project:
        raise NotFoundError("Project")

    # Fetch the source file from GitHub
    try:
        repo = github_service.parse_repo(project.fork_repo)
        file_content, _sha = await github_service.get_file_content(
            repo, tracked_file.file_path, project.fork_branch
        )
    except github_service.GitHubError as e:
        return VerifyResult(
            status="rejected",
            error=f"Could not fetch source file: {e}",
        )

    # Compile by patching the sorry in the actual file
    result = await lean_client.verify_in_file(
        file_content=file_content,
        declaration_name=sorry.declaration_name,
        tactics=body.tactics,
        allow_sorry=True,
        sorry_index=sorry.sorry_index,
    )

    # Convert LeanSorry objects to RemainingGoal for the response
    remaining = None
    if result.sorries:
        remaining = [
            RemainingGoal(line=s.line, col=s.col, goal=s.goal) for s in result.sorries if s.goal
        ]

    return VerifyResult(
        status=result.status,
        error=result.error,
        sorry_status=sorry.status,
        would_be_decomposition="sorry" in body.tactics.lower() and result.status == "passed",
        messages=result.messages,
        remaining_goals=remaining or None,
    )


@router.post("/freeform", response_model=VerifyResult)
@auth_limiter.limit("300/hour")
async def verify_freeform(
    request: Request,
    body: FreeformVerifyRequest,
    _agent: CurrentAgent,
    db: DbSession,
) -> VerifyResult:
    """Verify arbitrary Lean code in project context (exploration, sync).

    Prepends the project's import if the code doesn't start with 'import'.
    Returns Lean messages (info, warning) so agents can see #check/#print output.
    """
    project = await project_service.get_by_id(db, body.project_id)
    if not project:
        raise NotFoundError("Project", f"No project with id {body.project_id}")

    # Use the first tracked file's path as the default import context
    from sqlalchemy import select

    first_file = (
        await db.scalars(
            select(TrackedFile)
            .where(TrackedFile.project_id == project.id)
            .order_by(TrackedFile.file_path.asc())
            .limit(1)
        )
    ).first()
    import_path = first_file.file_path if first_file else None

    result = await lean_client.verify_freeform(body.code, import_path=import_path)

    return VerifyResult(
        status=result.status,
        error=result.error,
        messages=result.messages,
    )
