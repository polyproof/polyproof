"""Aggregate all v4 API routers."""

from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.comments import router as comments_router
from app.api.v1.config import router as config_router
from app.api.v1.conjectures import router as conjectures_router
from app.api.v1.projects import router as projects_router
from app.api.v1.verify import router as verify_router

api_router = APIRouter()

api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(conjectures_router, prefix="/conjectures", tags=["conjectures"])
api_router.include_router(comments_router, tags=["comments"])
api_router.include_router(verify_router, prefix="/verify", tags=["verify"])
api_router.include_router(config_router, prefix="/config", tags=["config"])
