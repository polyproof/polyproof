"""Integration tests for two-step registration with capability challenge."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registration_challenge import RegistrationChallenge

pytestmark = pytest.mark.asyncio


async def test_start_registration_returns_challenge(client: AsyncClient):
    """POST /register returns a challenge with statement and instructions."""
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "reg_agent_1", "description": "Test agent for registration"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "challenge_id" in data
    assert "challenge_statement" in data
    assert len(data["challenge_statement"]) > 0
    assert "instructions" in data
    assert data["attempts_remaining"] == 5


async def test_start_registration_returns_same_challenge(client: AsyncClient):
    """Requesting registration twice with the same name returns the same challenge."""
    body = {"name": "reg_same_name", "description": "Same name test"}
    resp1 = await client.post("/api/v1/agents/register", json=body)
    resp2 = await client.post("/api/v1/agents/register", json=body)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["challenge_id"] == resp2.json()["challenge_id"]


async def test_verify_correct_proof_creates_agent(client: AsyncClient, mock_lean_pass):
    """Submitting a correct proof completes registration and returns API key."""
    # Step 1: get challenge
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "proven_agent", "description": "Agent that can prove things"},
    )
    assert resp.status_code == 200
    challenge = resp.json()

    # Step 2: verify with correct proof
    resp = await client.post(
        "/api/v1/agents/register/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "name": "proven_agent",
            "description": "Agent that can prove things",
            "proof": "exact some_tactic",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "proven_agent"
    assert data["api_key"].startswith("pp_")
    assert "agent_id" in data
    assert "message" in data

    # Verify agent can authenticate
    headers = {"Authorization": f"Bearer {data['api_key']}"}
    me_resp = await client.get("/api/v1/agents/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "proven_agent"


async def test_verify_wrong_proof_decrements_attempts(client: AsyncClient, mock_lean_fail):
    """Submitting an incorrect proof decrements attempts and returns error."""
    # Step 1: get challenge
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "failing_agent", "description": "Agent with wrong proof"},
    )
    assert resp.status_code == 200
    challenge = resp.json()

    # Step 2: verify with wrong proof
    resp = await client.post(
        "/api/v1/agents/register/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "name": "failing_agent",
            "description": "Agent with wrong proof",
            "proof": "sorry",
        },
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "Proof rejected" in data["error"]
    assert "4" in data.get("detail", "")


async def test_expired_challenge_rejected(
    client: AsyncClient, db_session: AsyncSession, mock_lean_pass
):
    """An expired challenge cannot be used for verification."""
    # Step 1: get challenge
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "expired_agent", "description": "Expired challenge test"},
    )
    assert resp.status_code == 200
    challenge = resp.json()

    # Manually expire the challenge
    past = datetime.now(tz=UTC) - timedelta(hours=2)
    await db_session.execute(
        update(RegistrationChallenge)
        .where(RegistrationChallenge.id == challenge["challenge_id"])
        .values(expires_at=past)
    )
    await db_session.commit()

    # Step 2: try to verify
    resp = await client.post(
        "/api/v1/agents/register/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "name": "expired_agent",
            "description": "Expired challenge test",
            "proof": "exact trivial",
        },
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["error"].lower()


async def test_duplicate_name_rejected_at_start(client: AsyncClient, seed_agent: dict):
    """Starting registration with a name already taken by an agent returns 409."""
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "test_agent", "description": "Trying to take an existing name"},
    )
    assert resp.status_code == 409


async def test_max_attempts_exhausted(
    client: AsyncClient, db_session: AsyncSession, mock_lean_fail
):
    """After all attempts are used, verification is rejected."""
    # Step 1: get challenge
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "exhausted_agent", "description": "Will run out of attempts"},
    )
    assert resp.status_code == 200
    challenge = resp.json()

    # Set attempts to 1 so next failure exhausts them
    await db_session.execute(
        update(RegistrationChallenge)
        .where(RegistrationChallenge.id == challenge["challenge_id"])
        .values(attempts_remaining=1)
    )
    await db_session.commit()

    # Use the last attempt with a wrong proof
    resp = await client.post(
        "/api/v1/agents/register/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "name": "exhausted_agent",
            "description": "Will run out of attempts",
            "proof": "wrong_tactic",
        },
    )
    assert resp.status_code == 400

    # Now try again — should be rejected with no attempts remaining
    resp = await client.post(
        "/api/v1/agents/register/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "name": "exhausted_agent",
            "description": "Will run out of attempts",
            "proof": "another_try",
        },
    )
    assert resp.status_code == 400
    data = resp.json()
    has_attempts_info = (
        "attempts" in data.get("error", "").lower() or "attempts" in data.get("detail", "").lower()
    )
    assert has_attempts_info


async def test_nonexistent_challenge_rejected(client: AsyncClient):
    """Verifying with a nonexistent challenge ID returns 404."""
    resp = await client.post(
        "/api/v1/agents/register/verify",
        json={
            "challenge_id": str(uuid4()),
            "name": "ghost_agent",
            "description": "No such challenge",
            "proof": "exact trivial",
        },
    )
    assert resp.status_code == 404


async def test_name_mismatch_rejected(client: AsyncClient):
    """Verifying with a different name than the challenge returns 400."""
    # Step 1: get challenge
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "original_name", "description": "Name mismatch test"},
    )
    assert resp.status_code == 200
    challenge = resp.json()

    # Step 2: try to verify with different name
    resp = await client.post(
        "/api/v1/agents/register/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "name": "different_name",
            "description": "Name mismatch test",
            "proof": "exact trivial",
        },
    )
    assert resp.status_code == 400
    assert "mismatch" in resp.json()["error"].lower()
