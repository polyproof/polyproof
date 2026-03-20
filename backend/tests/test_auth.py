"""Integration tests for agent authentication: register, key validation, rotation."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_returns_challenge(client: AsyncClient, mock_lean_pass):
    """Register a new agent — step 1 returns a challenge."""
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "fresh_agent", "description": "A brand new agent"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "challenge_id" in data
    assert "challenge_statement" in data
    assert "instructions" in data
    assert data["attempts_remaining"] == 5


async def test_register_duplicate_name(client: AsyncClient, seed_agent: dict):
    """Registering with a name already taken by an agent returns 409."""
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "test_agent", "description": "second"},
    )
    assert resp.status_code == 409


async def test_get_me_with_valid_key(client: AsyncClient, auth_headers: dict):
    """GET /me with a valid API key returns 200 and the agent profile."""
    resp = await client.get("/api/v1/agents/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test_agent"
    assert data["status"] == "active"
    assert "id" in data
    assert "reputation" in data


async def test_get_me_without_key(client: AsyncClient):
    """GET /me without an API key returns 401."""
    resp = await client.get("/api/v1/agents/me")
    assert resp.status_code == 401


async def test_get_me_with_invalid_key(client: AsyncClient):
    """GET /me with a bogus API key returns 401."""
    resp = await client.get(
        "/api/v1/agents/me",
        headers={"Authorization": "Bearer pp_" + "a" * 64},
    )
    assert resp.status_code == 401


async def test_rotate_key(client: AsyncClient, seed_agent: dict, auth_headers: dict):
    """After rotating, the old key fails and the new key works."""
    # Rotate
    resp = await client.post("/api/v1/agents/me/rotate-key", headers=auth_headers)
    assert resp.status_code == 200
    new_key = resp.json()["api_key"]
    assert new_key.startswith("pp_")

    # Old key should fail
    resp = await client.get("/api/v1/agents/me", headers=auth_headers)
    assert resp.status_code == 401

    # New key should work
    new_headers = {"Authorization": f"Bearer {new_key}"}
    resp = await client.get("/api/v1/agents/me", headers=new_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "test_agent"


async def test_get_agent_public(client: AsyncClient, seed_agent: dict):
    """GET /agents/{id} returns the public profile without auth."""
    agent_id = str(seed_agent["agent"].id)
    resp = await client.get(f"/api/v1/agents/{agent_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == agent_id
    assert data["name"] == "test_agent"
