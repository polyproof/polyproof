"""Lean verification endpoints: sorry-scoped and freeform."""

from fastapi import APIRouter, Request

from app.api.deps import CurrentAgent, DbSession
from app.api.rate_limit import auth_limiter
from app.errors import NotFoundError
from app.models.sorry import Sorry
from app.models.tracked_file import TrackedFile
from app.schemas.verify import FreeformVerifyRequest, VerifyRequest, VerifyResult
from app.services import lean_client, project_service

router = APIRouter()


@router.post("", response_model=VerifyResult)
@auth_limiter.limit("300/hour")
async def verify_lean(
    request: Request,
    body: VerifyRequest,
    _agent: CurrentAgent,
    db: DbSession,
) -> VerifyResult:
    """Verify tactics against a sorry (sync, sorry allowed).

    Requires sorry_id. Wraps tactics with the sorry's goal_state in a locked
    signature and compiles via Lean CI.
    """
    if body.sorry_id is not None:
        sorry = await db.get(Sorry, body.sorry_id)
        if not sorry:
            raise NotFoundError("Sorry", f"No sorry with id {body.sorry_id}")

        tracked_file = await db.get(TrackedFile, sorry.file_id)
        import_path = tracked_file.file_path if tracked_file else None

        result = await lean_client.verify_fill(
            goal_state=sorry.goal_state,
            tactics=body.tactics,
            sorry_id=sorry.id,
            project_id=sorry.project_id,
            allow_sorry=True,
            import_path=import_path,
        )

        return VerifyResult(
            status=result.status,
            error=result.error,
            sorry_status=sorry.status,
            would_be_decomposition="sorry" in body.tactics.lower() and result.status == "passed",
        )
    else:
        result = await lean_client.verify_freeform(body.tactics)
        return VerifyResult(
            status=result.status,
            error=result.error,
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

    Requires project_id for context (toolchain, imports, etc.).
    """
    project = await project_service.get_by_id(db, body.project_id)
    if not project:
        raise NotFoundError("Project", f"No project with id {body.project_id}")

    result = await lean_client.verify_freeform(body.code, project_id=project.id)

    return VerifyResult(
        status=result.status,
        error=result.error,
    )
