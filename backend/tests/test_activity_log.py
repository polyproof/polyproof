"""Tests for activity log recording and retrieval."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


async def test_proof_event_recorded(client: AsyncClient, seed_agent, seed_project, mock_lean_pass):
    """Submitting a proof records a 'proof' activity event."""
    conj_id = str(seed_project["root_conjecture"].id)
    project_id = str(seed_project["project"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        headers=headers,
        json={"lean_code": "simp"},
    )

    resp = await client.get(f"/api/v1/projects/{project_id}/activity")
    assert resp.status_code == 200
    data = resp.json()
    event_types = [e["event_type"] for e in data["events"]]
    assert "proof" in event_types

    # Verify the proof event has agent info
    proof_event = next(e for e in data["events"] if e["event_type"] == "proof")
    assert proof_event["agent"] is not None
    assert proof_event["agent"]["handle"].startswith("test_agent")
    assert proof_event["conjecture_id"] == conj_id


async def test_comment_event_recorded(client: AsyncClient, seed_agent, seed_project):
    """Posting a comment records a 'comment' activity event."""
    conj_id = str(seed_project["root_conjecture"].id)
    project_id = str(seed_project["project"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    await client.post(
        f"/api/v1/conjectures/{conj_id}/comments",
        headers=headers,
        json={"body": "Test comment for activity log"},
    )

    resp = await client.get(f"/api/v1/projects/{project_id}/activity")
    assert resp.status_code == 200
    data = resp.json()
    event_types = [e["event_type"] for e in data["events"]]
    assert "comment" in event_types


async def test_disproof_event_recorded(
    client: AsyncClient, seed_agent, seed_project, mock_lean_pass
):
    """Submitting a disproof records a 'disproof' activity event."""
    conj_id = str(seed_project["root_conjecture"].id)
    project_id = str(seed_project["project"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    await client.post(
        f"/api/v1/conjectures/{conj_id}/disproofs",
        headers=headers,
        json={"lean_code": "exact absurd rfl"},
    )

    resp = await client.get(f"/api/v1/projects/{project_id}/activity")
    assert resp.status_code == 200
    data = resp.json()
    event_types = [e["event_type"] for e in data["events"]]
    assert "disproof" in event_types


async def test_activity_feed_pagination(client: AsyncClient, seed_agent, seed_project):
    """Activity feed supports limit and offset."""
    project_id = str(seed_project["project"].id)
    conj_id = str(seed_project["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    # Create multiple events
    for i in range(5):
        await client.post(
            f"/api/v1/conjectures/{conj_id}/comments",
            headers=headers,
            json={"body": f"Comment {i}"},
        )

    resp = await client.get(f"/api/v1/projects/{project_id}/activity?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["events"]) == 2
    assert data["total"] >= 5


async def test_activity_feed_empty_project(client: AsyncClient, seed_project):
    """Activity feed for a project with no activity returns empty."""
    project_id = str(seed_project["project"].id)
    resp = await client.get(f"/api/v1/projects/{project_id}/activity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["events"] == []
    assert data["total"] == 0
