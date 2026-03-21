"""Tests for project creation, listing, and detail endpoints."""

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


@pytest.fixture
def admin_headers(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test_admin_key_123")
    return {"Authorization": "Bearer test_admin_key_123"}


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


async def test_create_project_admin(client: AsyncClient, admin_headers, mock_lean_pass):
    resp = await client.post(
        "/api/v1/projects",
        headers=admin_headers,
        json={
            "title": "Fermat's Last Theorem",
            "description": "Prove FLT",
            "root_conjecture": {
                "lean_statement": "forall n : Nat, n > 2 -> True",
                "description": "The root conjecture",
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Fermat's Last Theorem"
    assert data["root_conjecture_id"] is not None
    assert data["progress"] == 0.0
    assert data["root_status"] == "open"


async def test_create_project_non_admin(client: AsyncClient, seed_agent, mock_lean_pass):
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}
    resp = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": "Not Allowed",
            "description": "Unauthorized project",
            "root_conjecture": {
                "lean_statement": "True",
                "description": "Root",
            },
        },
    )
    assert resp.status_code == 401


async def test_create_project_no_auth(client: AsyncClient, mock_lean_pass):
    resp = await client.post(
        "/api/v1/projects",
        json={
            "title": "No Auth",
            "description": "No auth",
            "root_conjecture": {
                "lean_statement": "True",
                "description": "Root",
            },
        },
    )
    assert resp.status_code == 401


async def test_list_projects_with_progress(client: AsyncClient, seed_project):
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    project = data["projects"][0]
    assert "progress" in project
    assert "root_status" in project
    assert "root_conjecture_id" in project


async def test_get_project_detail(client: AsyncClient, seed_project):
    project_id = str(seed_project["project"]["id"])
    resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test Project"
    assert "total_conjectures" in data
    assert "open_conjectures" in data
    assert "proved_conjectures" in data
    assert "total_leaves" in data
    assert "proved_leaves" in data
    assert "progress" in data


async def test_get_project_not_found(client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"/api/v1/projects/{fake_id}")
    assert resp.status_code == 404
