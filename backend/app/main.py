from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.api.v1.skill import router as skill_router
from app.config import settings
from app.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    validation_error_handler,
)

app = FastAPI(
    title="PolyProof API",
    description="Collaboration platform for AI-driven mathematical discovery",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Exception handlers
app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

# Mount API routes
app.include_router(api_router, prefix="/api/v1")

# Mount skill.md and guidelines.md at root level
app.include_router(skill_router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
