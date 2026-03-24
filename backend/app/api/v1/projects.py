"""Project CRUD, sorries listing, tree, activity, and overview endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.config import settings
from app.errors import NotFoundError
from app.schemas.activity import ActivityFeedResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectDetail,
    ProjectListResponse,
    ProjectOverview,
    ProjectResponse,
    ProjectTreeResponse,
)
from app.schemas.sorry import SorryListResponse, SorryResponse
from app.services import activity_service, project_service, sorry_service

router = APIRouter()


class SorryImport(BaseModel):
    file_path: str = Field(min_length=1)
    declaration_name: str = Field(min_length=1)
    sorry_index: int = 0
    goal_state: str = Field(min_length=1)
    local_context: str | None = None
    line: int | None = None
    col: int | None = None
    priority: str = "normal"


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
    """Create a project with tracked files. Admin only."""
    await _require_admin(request)

    project = await project_service.create(
        db,
        data=body.model_dump(),
    )

    return ProjectResponse(
        id=project.id,
        title=project.title,
        description=project.description,
        upstream_repo=project.upstream_repo,
        fork_repo=project.fork_repo,
        fork_branch=project.fork_branch,
        lean_toolchain=project.lean_toolchain,
        total_sorries=0,
        filled_sorries=0,
        progress=0.0,
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
    """List all projects with computed progress."""
    project_dicts, total = await project_service.list_projects(db, limit=limit, offset=offset)
    projects = [ProjectResponse(**p) for p in project_dicts]
    return ProjectListResponse(projects=projects, total=total)


@router.get("/{project_id}", response_model=ProjectDetail)
@ip_limiter.limit("100/minute")
async def get_project(
    request: Request,
    project_id: UUID,
    db: DbSession,
) -> ProjectDetail:
    """Get project detail with files and progress."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    detail = await project_service.get_detail(db, project)
    return ProjectDetail(**detail)


@router.get("/{project_id}/sorries", response_model=SorryListResponse)
@ip_limiter.limit("100/minute")
async def list_project_sorries(
    request: Request,
    project_id: UUID,
    db: DbSession,
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    order_by: str = Query(default="priority"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SorryListResponse:
    """List all sorries in a project with goal states inline."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    items, total = await sorry_service.list_for_project(
        db,
        project_id=project_id,
        status=status,
        priority=priority,
        order_by=order_by,
        limit=limit,
        offset=offset,
    )
    sorries = [SorryResponse(**item) for item in items]
    return SorryListResponse(sorries=sorries, total=total)


@router.get("/{project_id}/tree", response_model=ProjectTreeResponse)
@ip_limiter.limit("100/minute")
async def get_project_tree(
    request: Request,
    project_id: UUID,
    db: DbSession,
) -> ProjectTreeResponse:
    """Full tree visualization data."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    nodes = await sorry_service.get_tree(db, project.id)
    return ProjectTreeResponse(nodes=nodes)


@router.get("/{project_id}/activity", response_model=ActivityFeedResponse)
@ip_limiter.limit("100/minute")
async def get_project_activity(
    request: Request,
    project_id: UUID,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ActivityFeedResponse:
    """Recent activity feed for a project."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    return await activity_service.get_activity_feed(db, project_id, limit=limit, offset=offset)


@router.get("/{project_id}/overview", response_model=ProjectOverview)
@ip_limiter.limit("100/minute")
async def get_project_overview(
    request: Request,
    project_id: UUID,
    db: DbSession,
) -> ProjectOverview:
    """Project overview for agents with flat sorry list and per-node metrics."""
    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")
    data = await project_service.get_overview(db, project)
    return ProjectOverview(**data)


@router.post("/{project_id}/import-sorries")
async def import_sorries(
    request: Request,
    project_id: UUID,
    body: list[SorryImport],
    db: DbSession,
) -> dict[str, Any]:
    """Bulk-import sorry records for a project. Admin only."""
    await _require_admin(request)

    project = await project_service.get_by_id(db, project_id)
    if not project:
        raise NotFoundError("Project")

    result = await project_service.import_sorries(
        db, project_id, [s.model_dump() for s in body]
    )
    return result
