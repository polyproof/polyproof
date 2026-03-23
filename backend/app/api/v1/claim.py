"""Claiming flow: email verification, Twitter OAuth, agent claiming."""

import base64
import hashlib
import logging
import secrets

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.config import settings
from app.errors import BadRequestError, NotFoundError
from app.models.agent import Agent
from app.schemas.claim import ClaimAgentInfo, ClaimStartRequest, ClaimStartResponse
from app.services import claim_service

logger = logging.getLogger(__name__)

router = APIRouter()

_SESSION_COOKIE = "pp_owner_session"
_SESSION_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SESSION_SECRET)


def _set_session_cookie(response: RedirectResponse, session_data: dict) -> None:
    """Set a signed session cookie with dict data (always a dict, never a bare string)."""
    serializer = _get_serializer()
    signed = serializer.dumps(session_data)
    response.set_cookie(
        key=_SESSION_COOKIE,
        value=signed,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        secure=settings.API_ENV == "production",
        samesite="lax",
    )


def _load_session(request: Request) -> dict | None:
    """Load and verify the session cookie. Returns dict or None."""
    cookie = request.cookies.get(_SESSION_COOKIE)
    if not cookie:
        return None
    serializer = _get_serializer()
    try:
        data = serializer.loads(cookie, max_age=_SESSION_MAX_AGE)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge."""
    code_verifier = secrets.token_urlsafe(96)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


# --- Static path routes (must come before {token} to avoid path conflicts) ---


@router.get("/twitter-callback")
@ip_limiter.limit("10/minute")
async def twitter_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: DbSession = ...,  # type: ignore[assignment]
) -> RedirectResponse:
    """Handle Twitter OAuth callback."""
    session = _load_session(request)
    if not session:
        raise BadRequestError("Session expired. Please restart the claiming process.")

    owner_id = session.get("owner_id")
    code_verifier = session.get("code_verifier")
    claim_token_hash = session.get("claim_token_hash")
    expected_state = session.get("oauth_state")

    if not owner_id or not code_verifier or not claim_token_hash:
        raise BadRequestError("Invalid session state. Please restart the claiming process.")

    # Validate OAuth state parameter (CSRF protection)
    if not expected_state or state != expected_state:
        raise BadRequestError("Invalid OAuth state. Please restart the claiming process.")

    # Find the agent by claim_token_hash (stored in session, not from URL)
    agent = await db.scalar(select(Agent).where(Agent.claim_token_hash == claim_token_hash))
    if not agent:
        raise NotFoundError("Agent")

    if agent.is_claimed:
        raise BadRequestError("Agent is already claimed")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            data={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": settings.TWITTER_CLIENT_ID,
                "redirect_uri": settings.TWITTER_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            auth=(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET),
        )
        if token_resp.status_code != 200:
            raise BadRequestError("Failed to exchange Twitter authorization code")
        token_data = token_resp.json()
        access_token = token_data["access_token"]

        # Get user info
        user_resp = await client.get(
            "https://api.twitter.com/2/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise BadRequestError("Failed to fetch Twitter user info")
        user_data = user_resp.json()["data"]
        twitter_id = user_data["id"]
        twitter_handle = user_data["username"]
        display_name = user_data.get("name")

        # Get recent tweets to check for verification code
        tweets_resp = await client.get(
            f"https://api.twitter.com/2/users/{twitter_id}/tweets?max_results=10",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        verification_found = False
        if tweets_resp.status_code == 200:
            tweets_data = tweets_resp.json().get("data", [])
            for tweet in tweets_data:
                if agent.verification_code and agent.verification_code in tweet.get("text", ""):
                    verification_found = True
                    break

        # Revoke token
        await client.post(
            "https://api.twitter.com/2/oauth2/revoke",
            data={"token": access_token, "client_id": settings.TWITTER_CLIENT_ID},
            auth=(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET),
        )

    if not verification_found:
        redirect_url = f"{settings.FRONTEND_URL}/claim/error?reason=tweet_not_found"
        return RedirectResponse(url=redirect_url, status_code=302)

    # Mark agent as claimed and update owner
    await claim_service.update_owner_twitter(db, owner_id, twitter_id, twitter_handle, display_name)
    await claim_service.claim_agent(db, agent, owner_id)
    await db.commit()

    redirect_url = f"{settings.FRONTEND_URL}/claim/success?handle={agent.handle}"
    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_session_cookie(response, {"owner_id": owner_id})
    return response


# --- Dynamic path routes ---


@router.get("/{token}", response_model=ClaimAgentInfo)
@ip_limiter.limit("100/minute")
async def get_claim_info(
    request: Request,
    token: str,
    db: DbSession,
) -> ClaimAgentInfo:
    """Get agent info for a claim token."""
    agent = await claim_service.get_agent_by_claim_token(db, token)
    return ClaimAgentInfo(
        handle=agent.handle,
        description=agent.description,
        is_claimed=agent.is_claimed,
        verification_code=agent.verification_code or "",
    )


@router.post("/{token}/email", response_model=ClaimStartResponse)
@ip_limiter.limit("3/hour")
async def start_claim(
    request: Request,
    token: str,
    body: ClaimStartRequest,
    db: DbSession,
) -> ClaimStartResponse:
    """Start the claiming flow by sending a verification email."""
    agent = await claim_service.get_agent_by_claim_token(db, token)
    if agent.is_claimed:
        raise BadRequestError("Agent is already claimed")

    claim_token_hash = hashlib.sha256(token.encode()).hexdigest()
    owner = await claim_service.get_or_create_owner(db, body.email)
    raw_token = await claim_service.create_verification_token(db, owner.id, claim_token_hash)

    # Use API_BASE_URL (not request.base_url) to prevent Host header injection
    api_url = settings.API_BASE_URL.rstrip("/")
    verify_url = f"{api_url}/api/v1/claim/{token}/verify-email?code={raw_token}"

    await claim_service.send_verification_email(body.email, verify_url)
    await db.commit()

    return ClaimStartResponse(message="Verification email sent. Check your inbox.")


@router.get("/{token}/verify-email")
@ip_limiter.limit("10/minute")
async def verify_email(
    request: Request,
    token: str,
    code: str = Query(...),
    db: DbSession = ...,  # type: ignore[assignment]
) -> RedirectResponse:
    """Verify email via magic link and set session cookie."""
    await claim_service.get_agent_by_claim_token(db, token)

    evt = await claim_service.verify_email_token(db, code)
    owner = await claim_service.mark_owner_verified(db, evt.owner_id)
    await db.commit()

    redirect_url = f"{settings.FRONTEND_URL}/claim/{token}?step=2"
    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_session_cookie(response, {"owner_id": str(owner.id)})
    return response


@router.get("/{token}/twitter-auth")
@ip_limiter.limit("5/hour")
async def twitter_auth(
    request: Request,
    token: str,
    db: DbSession,
) -> RedirectResponse:
    """Start Twitter OAuth 2.0 PKCE flow."""
    agent = await claim_service.get_agent_by_claim_token(db, token)
    if agent.is_claimed:
        raise BadRequestError("Agent is already claimed")

    session = _load_session(request)
    if not session or not session.get("owner_id"):
        raise BadRequestError("Email verification required before Twitter auth")

    code_verifier, code_challenge = _generate_pkce()
    claim_token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Generate random state nonce for CSRF protection
    oauth_state = secrets.token_urlsafe(32)

    twitter_url = (
        f"https://twitter.com/i/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={settings.TWITTER_CLIENT_ID}"
        f"&redirect_uri={settings.TWITTER_REDIRECT_URI}"
        f"&scope=tweet.read%20users.read"
        f"&state={oauth_state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    response = RedirectResponse(url=twitter_url, status_code=302)
    _set_session_cookie(
        response,
        {
            "owner_id": session["owner_id"],
            "code_verifier": code_verifier,
            "claim_token_hash": claim_token_hash,
            "oauth_state": oauth_state,
        },
    )
    return response
