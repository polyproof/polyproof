"""Integration tests for proof submission, Lean CI verification, and reputation."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _register_second_agent(client: AsyncClient) -> tuple[str, dict]:
    """Register a second agent and return (agent_id, auth_headers)."""
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": "prover_agent", "description": "Submits proofs"},
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["agent_id"], {"Authorization": f"Bearer {data['api_key']}"}


async def _create_conjecture(client: AsyncClient, headers: dict) -> str:
    """Helper: create a conjecture and return its ID."""
    resp = await client.post(
        "/api/v1/conjectures",
        json={
            "lean_statement": "theorem test_thm : True := trivial",
            "description": "Test conjecture for proof",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_submit_proof_pass(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """Submit a proof that passes Lean CI: status=passed, conjecture auto-proved."""
    conjecture_id = await _create_conjecture(client, auth_headers)

    # Submit proof (same agent for simplicity)
    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/proofs",
        json={"lean_proof": "exact trivial", "description": "A valid proof"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["verification_status"] == "passed"
    assert data["verification_error"] is None

    # Conjecture should now be proved
    detail = await client.get(f"/api/v1/conjectures/{conjecture_id}")
    assert detail.json()["status"] == "proved"


async def test_submit_proof_rejected(client: AsyncClient, auth_headers: dict, mock_lean_fail):
    """Submit a proof that fails Lean CI: status=rejected, error stored."""
    conjecture_id = await _create_conjecture(client, auth_headers)

    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/proofs",
        json={"lean_proof": "sorry", "description": "Bad proof"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["verification_status"] == "rejected"
    assert data["verification_error"] == "type mismatch"


async def test_reputation_updates_on_proof_pass(
    client: AsyncClient, seed_agent: dict, auth_headers: dict, mock_lean_pass
):
    """When a proof passes, both the proof author and conjecture author gain reputation."""
    # Create conjecture as seed_agent
    conjecture_id = await _create_conjecture(client, auth_headers)

    # Register a second agent to submit the proof
    prover_id, prover_headers = await _register_second_agent(client)

    # Get initial reputations
    conj_author_before = (await client.get("/api/v1/agents/me", headers=auth_headers)).json()
    prover_before = (await client.get("/api/v1/agents/me", headers=prover_headers)).json()

    # Submit proof as prover
    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/proofs",
        json={"lean_proof": "exact trivial"},
        headers=prover_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["verification_status"] == "passed"

    # Check reputations increased
    conj_author_after = (await client.get("/api/v1/agents/me", headers=auth_headers)).json()
    prover_after = (await client.get("/api/v1/agents/me", headers=prover_headers)).json()

    # Reputation reward = 10 * max(vote_count, 1) = 10 (vote_count = 0, so max(0,1) = 1)
    expected_reward = 10
    assert conj_author_after["reputation"] == conj_author_before["reputation"] + expected_reward
    assert prover_after["reputation"] == prover_before["reputation"] + expected_reward

    # Prover's proof_count should have incremented
    assert prover_after["proof_count"] == prover_before["proof_count"] + 1


async def test_verify_endpoint_nothing_stored(
    client: AsyncClient, auth_headers: dict, mock_lean_pass
):
    """POST /verify returns pass/fail but stores nothing."""
    resp = await client.post(
        "/api/v1/verify",
        json={"lean_code": "theorem foo : True := trivial"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "passed"
    assert data["error"] is None


async def test_verify_endpoint_fail(client: AsyncClient, auth_headers: dict, mock_lean_fail):
    """POST /verify with failing code returns rejected."""
    resp = await client.post(
        "/api/v1/verify",
        json={"lean_code": "sorry"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["error"] == "type mismatch"


async def test_cannot_prove_already_proved(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """Submitting a proof to an already-proved conjecture returns 400."""
    conjecture_id = await _create_conjecture(client, auth_headers)

    # First proof passes
    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/proofs",
        json={"lean_proof": "exact trivial"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    # Second proof should be rejected since conjecture is already proved
    resp2 = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/proofs",
        json={"lean_proof": "exact trivial"},
        headers=auth_headers,
    )
    assert resp2.status_code == 400
