"""Tests for claiming flow and owner routes."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.email_verification_token import EmailVerificationToken
from app.models.owner import Owner


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


@pytest.fixture
async def claimable_agent(db_session: AsyncSession) -> dict:
    """Create an agent with a claim token set up."""
    raw_claim_token = "pp_claim_" + secrets.token_hex(32)
    claim_token_hash = hashlib.sha256(raw_claim_token.encode()).hexdigest()
    verification_code = "theorem-" + secrets.token_hex(2).upper()
    raw_api_key = "pp_" + secrets.token_hex(32)
    api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()

    agent = Agent(
        id=uuid4(),
        handle="test_claimable_" + secrets.token_hex(4),
        description="A test agent for claiming",
        type="community",
        api_key_hash=api_key_hash,
        claim_token_hash=claim_token_hash,
        verification_code=verification_code,
        is_claimed=False,
    )
    db_session.add(agent)
    await db_session.flush()
    return {
        "agent": agent,
        "claim_token": raw_claim_token,
        "claim_token_hash": claim_token_hash,
        "verification_code": verification_code,
    }


async def test_get_claim_info_valid_token(client: AsyncClient, claimable_agent):
    token = claimable_agent["claim_token"]
    resp = await client.get(f"/api/v1/claim/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["handle"] == claimable_agent["agent"].handle
    assert data["description"] == "A test agent for claiming"
    assert data["is_claimed"] is False
    assert data["verification_code"] == claimable_agent["verification_code"]


async def test_get_claim_info_invalid_token(client: AsyncClient):
    resp = await client.get("/api/v1/claim/invalid-token-value")
    assert resp.status_code == 404


@patch("app.services.claim_service.send_verification_email", new_callable=AsyncMock)
async def test_start_claim_sends_email(mock_send, client: AsyncClient, claimable_agent):
    token = claimable_agent["claim_token"]
    resp = await client.post(
        f"/api/v1/claim/{token}/email",
        json={"email": "test@example.com"},
    )
    assert resp.status_code == 200
    assert "Verification email sent" in resp.json()["message"]
    mock_send.assert_called_once()


@patch("app.services.claim_service.send_verification_email", new_callable=AsyncMock)
async def test_start_claim_already_claimed(
    mock_send, client: AsyncClient, claimable_agent, db_session
):
    agent = claimable_agent["agent"]
    agent.is_claimed = True
    await db_session.flush()

    token = claimable_agent["claim_token"]
    resp = await client.post(
        f"/api/v1/claim/{token}/email",
        json={"email": "test@example.com"},
    )
    assert resp.status_code == 400
    mock_send.assert_not_called()


async def test_verify_email_valid_code(client: AsyncClient, claimable_agent, db_session):
    owner = Owner(id=uuid4(), email="verify@example.com")
    db_session.add(owner)
    await db_session.flush()

    raw_code = secrets.token_urlsafe(32)
    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    evt = EmailVerificationToken(
        id=uuid4(),
        owner_id=owner.id,
        claim_token_hash=claimable_agent["claim_token_hash"],
        token_hash=code_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(evt)
    await db_session.flush()

    token = claimable_agent["claim_token"]
    resp = await client.get(
        f"/api/v1/claim/{token}/verify-email",
        params={"code": raw_code},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert f"/claim/{token}?step=2" in resp.headers["location"]
    assert "pp_owner_session" in resp.headers.get("set-cookie", "")


async def test_verify_email_invalid_code(client: AsyncClient, claimable_agent):
    token = claimable_agent["claim_token"]
    resp = await client.get(
        f"/api/v1/claim/{token}/verify-email",
        params={"code": "invalid-code"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


async def test_verify_email_expired_code(client: AsyncClient, claimable_agent, db_session):
    owner = Owner(id=uuid4(), email="expired@example.com")
    db_session.add(owner)
    await db_session.flush()

    raw_code = secrets.token_urlsafe(32)
    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    evt = EmailVerificationToken(
        id=uuid4(),
        owner_id=owner.id,
        claim_token_hash=claimable_agent["claim_token_hash"],
        token_hash=code_hash,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(evt)
    await db_session.flush()

    token = claimable_agent["claim_token"]
    resp = await client.get(
        f"/api/v1/claim/{token}/verify-email",
        params={"code": raw_code},
        follow_redirects=False,
    )
    assert resp.status_code == 400


async def test_twitter_auth_requires_session(client: AsyncClient, claimable_agent):
    token = claimable_agent["claim_token"]
    resp = await client.get(
        f"/api/v1/claim/{token}/twitter-auth",
        follow_redirects=False,
    )
    assert resp.status_code == 400


# Owner routes tests


async def test_owner_dashboard_without_cookie(client: AsyncClient):
    resp = await client.get("/api/v1/owners/me")
    assert resp.status_code == 401


async def test_owner_dashboard_invalid_cookie(client: AsyncClient):
    resp = await client.get(
        "/api/v1/owners/me",
        cookies={"pp_owner_session": "invalid-token-value"},
    )
    assert resp.status_code == 401


async def test_owner_logout(client: AsyncClient):
    resp = await client.post("/api/v1/owners/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out"
    assert "pp_owner_session" in resp.headers.get("set-cookie", "")


# Platform stats


async def test_platform_stats(client: AsyncClient):
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_agents" in data
    assert "total_proofs" in data
    assert "active_problems" in data
    assert "open_conjectures" in data
    for key in ["total_agents", "total_proofs", "active_problems", "open_conjectures"]:
        assert isinstance(data[key], int)
        assert data[key] >= 0


# Heartbeat


async def test_heartbeat_md_served(client: AsyncClient):
    resp = await client.get("/heartbeat.md")
    assert resp.status_code == 200
    assert "PolyProof Heartbeat" in resp.text
    assert resp.headers.get("content-type", "").startswith("text/plain")
