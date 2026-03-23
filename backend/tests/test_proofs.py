"""Tests for proof submission."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


async def test_submit_proof_pass(client: AsyncClient, seed_agent, seed_problem, mock_lean_pass):
    """Submit a valid proof -> conjecture becomes proved."""
    conj_id = str(seed_problem["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        headers=headers,
        json={"lean_code": "simp"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "proved"
    assert data["conjecture_id"] == conj_id


async def test_submit_proof_on_closed_conjecture(
    client: AsyncClient, seed_agent, seed_problem, mock_lean_pass
):
    """Submit proof on already-proved conjecture -> 409."""
    conj_id = str(seed_problem["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    # First proof succeeds
    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        headers=headers,
        json={"lean_code": "simp"},
    )
    assert resp.status_code == 201

    # Second proof fails with conflict
    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        headers=headers,
        json={"lean_code": "simp"},
    )
    assert resp.status_code == 409


async def test_submit_proof_lean_failure(
    client: AsyncClient, seed_agent, seed_problem, mock_lean_fail
):
    """Submit proof that Lean rejects -> 200 with rejected status."""
    conj_id = str(seed_problem["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        headers=headers,
        json={"lean_code": "bad_tactic"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["error"] is not None


async def test_submit_proof_not_found(client: AsyncClient, seed_agent, mock_lean_pass):
    """Submit proof on nonexistent conjecture -> 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    resp = await client.post(
        f"/api/v1/conjectures/{fake_id}/proofs",
        headers=headers,
        json={"lean_code": "simp"},
    )
    assert resp.status_code == 404


async def test_submit_proof_no_auth(client: AsyncClient, seed_problem, mock_lean_pass):
    """Submit proof without auth -> 401."""
    conj_id = str(seed_problem["root_conjecture"].id)
    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        json={"lean_code": "simp"},
    )
    assert resp.status_code == 401
