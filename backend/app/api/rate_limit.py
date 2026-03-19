"""Shared rate-limiting utilities.

IP-keyed limiter: use for unauthenticated endpoints (e.g. registration).
Auth-keyed limiter: use for authenticated endpoints — keys on API key hash
so that per-agent limits are enforced regardless of IP.
"""

import hashlib

from slowapi import Limiter
from starlette.requests import Request


def _get_real_ip(request: Request) -> str:
    """Get the real client IP, respecting proxy headers.

    Checks X-Forwarded-For (Railway, Cloudflare proxies) before
    falling back to the direct connection address.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
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


ip_limiter = Limiter(key_func=_get_real_ip)
auth_limiter = Limiter(key_func=_get_api_key_hash)
