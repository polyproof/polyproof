"""Project CRUD and activity feed endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.config import settings
from app.errors import BadRequestError, NotFoundError
from app.schemas.activity import ActivityFeedResponse
from app.schemas.conjecture import ConjectureListResponse, ConjectureResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectListResponse,
    ProjectResponse,
    ProjectTreeResponse,
)
from app.services import activity_service, conjecture_service, lean_client, project_service

router = APIRouter()


async def _require_admin(request: Request) -> None:
    """Verify the request carries the admin API key."""
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    token = auth[7:]
    if not settings.ADMIN_API_KEY or token != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: Request,
    body: ProjectCreate,
    db: DbSession,
) -> ProjectResponse:
    """Create a project with a root conjecture. Admin only."""
    await _require_admin(request)

    # Typecheck root lean_statement via Lean
    result = await lean_client.typecheck(body.root_conjecture.lean_statement)
    if result.status != "passed":
        raise BadRequestError(
            f"Root conjecture Lean statement failed typecheck: {result.error or result.status}"
        )

    project, root = await project_service.create(
        db,
        title=body.title,
        description=body.description,
        root_lean_statement=body.root_conjecture.lean_statement,
        root_description=body.root_conjecture.description,
    )

    return ProjectResponse(
        id=project.id,
        title=project.title,
        description=project.description,
        root_conjecture_id=root.id,
        root_status="open",
        progress=0.0,
        total_leaves=1,
        proved_leaves=0,
        created_at=project.created_at,
    )


@router.get("", response_model=ProjectListResponse)
@ip_limiter.limit("100/minute")
async def list_projects(
    request: Request,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProjectListResponse:
    """List active projects with computed progress."""
    project_dicts, total = await project_service.list_projects(db, limit=limit, offset=offset)
    projects = []
    for p in project_dicts:
        projects.append(
            ProjectResponse(
                id=p["id"],
                title=p["title"],
                description=p["description"],
                root_conjecture_id=p["root_conjecture_id"],
                root_status=p["root_status"],
                progress=p["progress"],
                total_leaves=p.get("total_leaves", 0),
                proved_leaves=p.get("proved_leaves", 0),
                last_activity_at=p.get("last_activity_at"),
                created_at=p["created_at"],
            )
        )
    return ProjectListResponse(projects=projects, total=total)


@router.get("/{project_id}", response_model=ProjectDetail)
@ip_limiter.limit("100/minute")
async def get_project(
    request: Request,
    project_id: UUID,
    db: DbSession,
) -> ProjectDetail:
    """Get project detail with full stats."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    detail = await project_service.get_detail(db, project)
    return ProjectDetail(**detail)


@router.get("/{project_id}/activity", response_model=ActivityFeedResponse)
@ip_limiter.limit("100/minute")
async def get_project_activity(
    request: Request,
    project_id: UUID,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ActivityFeedResponse:
    """Public activity feed for a project."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    return await activity_service.get_activity_feed(db, project_id, limit=limit, offset=offset)


@router.get("/{project_id}/tree", response_model=ProjectTreeResponse)
@ip_limiter.limit("100/minute")
async def get_project_tree(
    request: Request,
    project_id: UUID,
    db: DbSession,
) -> ProjectTreeResponse:
    """Full proof tree as nested JSON."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    if not project.root_conjecture_id:
        return ProjectTreeResponse(root=None)
    tree = await conjecture_service.get_tree(db, project.root_conjecture_id)
    return ProjectTreeResponse(root=tree)


@router.get("/{project_id}/conjectures", response_model=ConjectureListResponse)
@ip_limiter.limit("100/minute")
async def list_project_conjectures(
    request: Request,
    project_id: UUID,
    db: DbSession,
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    parent_id: UUID | None = Query(default=None),
    order_by: str = Query(default="priority"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConjectureListResponse:
    """List conjectures in a project with optional filters."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    items, total = await conjecture_service.list_for_project(
        db,
        project_id=project_id,
        status=status,
        priority=priority,
        parent_id=parent_id,
        order_by=order_by,
        limit=limit,
        offset=offset,
    )
    conjectures = [ConjectureResponse(**item) for item in items]
    return ConjectureListResponse(conjectures=conjectures, total=total)
