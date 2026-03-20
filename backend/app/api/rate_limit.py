"""Shared rate-limiting utilities.

IP-keyed limiter: use for unauthenticated endpoints (e.g. registration).
Auth-keyed limiter: use for authenticated endpoints — keys on API key hash
so that per-agent limits are enforced regardless of IP.
"""

import hashlib

from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

from app.config import settings


def _get_real_ip(request: Request) -> str:
    """Get the real client IP, respecting proxy headers.

    Checks X-Forwarded-For (Railway, Cloudflare proxies) before
    falling back to the direct connection address.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Use rightmost entry — Railway appends the real client IP,
        # so leftmost entries are client-controlled and spoofable.
        return forwarded.split(",")[-1].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


def _get_api_key_hash(request: Request) -> str:
    """Extract the Bearer token from the Authorization header and return its SHA-256 hash.

    Falls back to remote address if no valid bearer token is present
    (the auth dependency will reject the request anyway).
    """
    auth_header: str | None = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
        return hashlib.sha256(token.encode()).hexdigest()
    return _get_real_ip(request)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a proper 429 JSON response for rate limit violations.

    This replaces slowapi's default handler which crashes because it
    references request.app.state.limiter (never set).
    """
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": "Rate limit exceeded",
            "code": "RATE_LIMITED",
            "detail": str(exc.detail),
        },
        headers={"Retry-After": "60"},
    )


ip_limiter = Limiter(key_func=_get_real_ip, enabled=settings.RATE_LIMIT_ENABLED)
auth_limiter = Limiter(key_func=_get_api_key_hash, enabled=settings.RATE_LIMIT_ENABLED)
