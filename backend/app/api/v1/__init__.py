"""Aggregate all v4 API routers."""

from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.api.v1.agents import router as agents_router
from app.api.v1.claim import router as claim_router
from app.api.v1.comments import router as comments_router
from app.api.v1.config import router as config_router
from app.api.v1.conjectures import router as conjectures_router
from app.api.v1.owners import router as owners_router
from app.api.v1.problems import router as problems_router
from app.api.v1.verify import router as verify_router
from app.services import owner_service

api_router = APIRouter()

api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(problems_router, prefix="/problems", tags=["problems"])
api_router.include_router(conjectures_router, prefix="/conjectures", tags=["conjectures"])
api_router.include_router(comments_router, tags=["comments"])
api_router.include_router(verify_router, prefix="/verify", tags=["verify"])
api_router.include_router(config_router, prefix="/config", tags=["config"])
api_router.include_router(claim_router, prefix="/claim", tags=["claim"])
api_router.include_router(owners_router, prefix="/owners", tags=["owners"])


@api_router.get("/stats", tags=["stats"])
@ip_limiter.limit("100/minute")
async def platform_stats(request: Request, db: DbSession) -> dict:
    """Get platform-wide statistics."""
    return await owner_service.get_platform_stats(db)
