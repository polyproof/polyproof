"""Owner authentication and dashboard endpoints."""

from uuid import UUID

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field, field_validator

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.config import settings
from app.schemas.owner import OwnerDashboardResponse
from app.services import owner_service

router = APIRouter()

_SESSION_COOKIE = "pp_owner_session"
_SESSION_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SESSION_SECRET)


def create_owner_session(owner_id: UUID) -> str:
    """Create a signed session token for an owner."""
    serializer = _get_serializer()
    return serializer.dumps({"owner_id": str(owner_id)})


def verify_owner_session(token: str) -> UUID | None:
    """Verify a session token. Returns owner_id or None."""
    serializer = _get_serializer()
    try:
        data = serializer.loads(token, max_age=_SESSION_MAX_AGE)
        # Support both dict format {"owner_id": "..."} and legacy string format
        if isinstance(data, dict):
            owner_id_str = data.get("owner_id")
        else:
            owner_id_str = data
        if not owner_id_str:
            return None
        return UUID(owner_id_str)
    except (BadSignature, ValueError):
        return None


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


@router.get("/me", response_model=OwnerDashboardResponse)
@ip_limiter.limit("100/minute")
async def get_dashboard(
    request: Request,
    db: DbSession,
    pp_owner_session: str | None = Cookie(default=None),
) -> OwnerDashboardResponse:
    """Get the authenticated owner's dashboard. Requires session cookie."""
    if not pp_owner_session:
        raise HTTPException(status_code=401, detail="Authentication required")
    owner_id = verify_owner_session(pp_owner_session)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return await owner_service.get_owner_dashboard(db, owner_id)


@router.post("/login")
@ip_limiter.limit("3/hour")
async def login(
    request: Request,
    body: LoginRequest,
    db: DbSession,
) -> dict:
    """Send a magic link login email to the owner."""
    await owner_service.initiate_login(db, body.email)
    return {"message": "Check your inbox"}


@router.get("/verify-login")
@ip_limiter.limit("100/minute")
async def verify_login(
    request: Request,
    code: str,
    db: DbSession,
) -> RedirectResponse:
    """Verify a magic link token, set session cookie, redirect to dashboard."""
    owner_id = await owner_service.verify_login_token(db, code)
    if not owner_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    session_token = create_owner_session(owner_id)
    response = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard", status_code=302)
    response.set_cookie(
        key=_SESSION_COOKIE,
        value=session_token,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        secure=settings.API_ENV == "production",
        samesite="lax",
    )
    return response


@router.post("/logout")
@ip_limiter.limit("100/minute")
async def logout(request: Request) -> JSONResponse:
    """Clear the owner session cookie."""
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie(key=_SESSION_COOKIE)
    return response
