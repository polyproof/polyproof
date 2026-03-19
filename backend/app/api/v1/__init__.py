from fastapi import APIRouter

from app.api.v1 import agents, comments, config, conjectures, leaderboard, problems, verify, votes

api_router = APIRouter()

api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(problems.router, prefix="/problems", tags=["problems"])
api_router.include_router(conjectures.router, prefix="/conjectures", tags=["conjectures"])
api_router.include_router(comments.router, prefix="/comments", tags=["comments"])
api_router.include_router(leaderboard.router, prefix="/leaderboard", tags=["leaderboard"])
api_router.include_router(verify.router, prefix="/verify", tags=["verify"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(votes.router, tags=["votes"])
