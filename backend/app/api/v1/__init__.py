from fastapi import APIRouter

api_router = APIRouter()

# Routes are added incrementally as they are implemented.
# Example (uncomment when the module exists):
# from app.api.v1 import agents, problems, conjectures, comments, votes
# from app.api.v1 import leaderboard, verify, config as config_routes, skill
# api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
# ...
