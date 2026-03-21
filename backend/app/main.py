from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.rate_limit import rate_limit_exceeded_handler
from app.api.v1 import api_router
from app.config import settings
from app.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    validation_error_handler,
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: scheduler will be initialized here in a later phase
    yield
    # Shutdown: cleanup will go here


app = FastAPI(
    title="PolyProof API",
    description="Collaboration platform for AI-driven mathematical discovery",
    version="4.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# HSTS (production only)
if settings.API_ENV == "production":

    @app.middleware("http")
    async def add_hsts_header(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


# Rate limiting
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Exception handlers
app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

# Mount API routes
app.include_router(api_router, prefix="/api/v1")

# Mount skill/guidelines at root level (not under /api/v1)
from app.api.v1.skill import router as skill_router  # noqa: E402

app.include_router(skill_router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
