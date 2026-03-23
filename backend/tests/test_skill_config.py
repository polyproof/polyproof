"""Tests for skill.md serving, config endpoint, CORS, and schema validation."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


async def test_skill_md_served(client: AsyncClient):
    """GET /skill.md should return the skill.md file as text/plain."""
    resp = await client.get("/skill.md")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    assert len(resp.text) > 0


async def test_guidelines_md_served(client: AsyncClient):
    """GET /guidelines.md should return the guidelines.md file as text/plain."""
    resp = await client.get("/guidelines.md")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")
    assert len(resp.text) > 0


async def test_config_endpoint(client: AsyncClient):
    """GET /api/v1/config should return platform config."""
    resp = await client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "lean_version" in data
    assert "mathlib_version" in data
    assert "api_version" in data
    assert data["api_version"] == "v1"


async def test_health_endpoint(client: AsyncClient):
    """GET /health should return ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_cors_headers(client: AsyncClient):
    """CORS preflight should return correct headers."""
    resp = await client.options(
        "/api/v1/config",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    # FastAPI CORS middleware should respond
    assert resp.status_code in (200, 204)


async def test_lean_code_max_length(client: AsyncClient, seed_agent, seed_problem, mock_lean_pass):
    """lean_code over 100k chars should be rejected by schema validation."""
    conj_id = str(seed_problem["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    # 100_001 chars should fail
    long_code = "a" * 100_001
    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        headers=headers,
        json={"lean_code": long_code},
    )
    assert resp.status_code == 422


async def test_comment_body_max_length(client: AsyncClient, seed_agent, seed_problem):
    """Comment body over 10k chars should be rejected."""
    conj_id = str(seed_problem["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    long_body = "x" * 10_001
    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/comments",
        headers=headers,
        json={"body": long_body},
    )
    assert resp.status_code == 422


async def test_project_description_max_length(client: AsyncClient, monkeypatch, mock_lean_pass):
    """Project description over 10k chars should be rejected."""
    from app.config import settings

    monkeypatch.setattr(settings, "ADMIN_API_KEY", "admin_key_test")
    headers = {"Authorization": "Bearer admin_key_test"}

    long_desc = "d" * 10_001
    resp = await client.post(
        "/api/v1/problems",
        headers=headers,
        json={
            "title": "Test",
            "description": long_desc,
            "root_conjecture": {
                "lean_statement": "True",
                "description": "Root",
            },
        },
    )
    assert resp.status_code == 422
