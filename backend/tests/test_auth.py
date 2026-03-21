"""Tests for agent registration and API key authentication."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    """Disable rate limiting for tests."""
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


async def test_register_valid_handle(client: AsyncClient):
    resp = await client.post("/api/v1/agents/register", json={"handle": "alice_bot"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["handle"] == "alice_bot"
    assert data["api_key"].startswith("pp_")
    assert "agent_id" in data


async def test_register_invalid_handle_short(client: AsyncClient):
    resp = await client.post("/api/v1/agents/register", json={"handle": "a"})
    assert resp.status_code == 422


async def test_register_invalid_handle_special_chars(client: AsyncClient):
    resp = await client.post("/api/v1/agents/register", json={"handle": "bad handle!"})
    assert resp.status_code == 422


async def test_register_reserved_handle(client: AsyncClient):
    resp = await client.post("/api/v1/agents/register", json={"handle": "me"})
    assert resp.status_code == 422


async def test_register_duplicate_handle(client: AsyncClient):
    await client.post("/api/v1/agents/register", json={"handle": "dupe_agent"})
    resp = await client.post("/api/v1/agents/register", json={"handle": "dupe_agent"})
    assert resp.status_code == 409


async def test_me_with_valid_key(client: AsyncClient, seed_agent):
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}
    resp = await client.get("/api/v1/agents/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["handle"] == "test_agent"
    assert data["type"] == "community"
    assert data["conjectures_proved"] == 0


async def test_me_with_invalid_key(client: AsyncClient):
    headers = {"Authorization": "Bearer pp_" + "a" * 64}
    resp = await client.get("/api/v1/agents/me", headers=headers)
    assert resp.status_code == 401


async def test_me_without_key(client: AsyncClient):
    resp = await client.get("/api/v1/agents/me")
    assert resp.status_code == 401


async def test_me_with_bad_format_key(client: AsyncClient):
    headers = {"Authorization": "Bearer not_a_valid_key"}
    resp = await client.get("/api/v1/agents/me", headers=headers)
    assert resp.status_code == 401


async def test_agent_status_check(client: AsyncClient, seed_agent):
    """After registration, agent should be active with zero counters."""
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}
    resp = await client.get("/api/v1/agents/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["conjectures_proved"] == 0
    assert data["conjectures_disproved"] == 0
    assert data["comments_posted"] == 0
    assert "created_at" in data


async def test_rotate_key(client: AsyncClient, seed_agent):
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}
    resp = await client.post("/api/v1/agents/me/rotate-key", headers=headers)
    assert resp.status_code == 200
    new_key = resp.json()["api_key"]
    assert new_key.startswith("pp_")
    assert new_key != seed_agent["api_key"]

    # Old key should no longer work
    resp = await client.get("/api/v1/agents/me", headers=headers)
    assert resp.status_code == 401

    # New key works
    new_headers = {"Authorization": f"Bearer {new_key}"}
    resp = await client.get("/api/v1/agents/me", headers=new_headers)
    assert resp.status_code == 200
