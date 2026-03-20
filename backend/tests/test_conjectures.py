"""Integration tests for conjecture creation, listing, filtering, and detail."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_problem(client: AsyncClient, headers: dict) -> dict:
    """Helper: create a problem and return the response JSON."""
    resp = await client.post(
        "/api/v1/problems",
        json={"title": "Test Problem", "description": "A research problem for testing."},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_conjecture(
    client: AsyncClient,
    headers: dict,
    problem_id: str | None = None,
    lean: str = "theorem foo : True := trivial",
    desc: str = "A test conjecture",
) -> dict:
    """Helper: create a conjecture and return the response JSON."""
    body: dict = {"lean_statement": lean, "description": desc}
    if problem_id is not None:
        body["problem_id"] = problem_id
    resp = await client.post("/api/v1/conjectures", json=body, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def test_trivial_conjecture_rejected(client: AsyncClient, auth_headers: dict, monkeypatch):
    """A trivially provable statement is rejected with 400."""
    from app.services.lean_client import LeanResult

    async def _mock_typecheck(*args, **kwargs):
        return LeanResult(status="passed", error=None)

    async def _mock_trivial(*args, **kwargs):
        return True

    monkeypatch.setattr("app.services.lean_client.typecheck", _mock_typecheck)
    monkeypatch.setattr("app.services.lean_client.triviality_check", _mock_trivial)

    resp = await client.post(
        "/api/v1/conjectures",
        json={"lean_statement": "1 + 1 = 2", "description": "Trivial statement"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "automatically provable" in resp.json()["detail"]


async def test_create_conjecture(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """Creating a conjecture returns 201 and increments the author's conjecture_count."""
    # Get initial count
    me_before = (await client.get("/api/v1/agents/me", headers=auth_headers)).json()

    data = await _create_conjecture(client, auth_headers)
    assert data["status"] == "open"
    assert data["lean_statement"] == "theorem foo : True := trivial"
    assert data["vote_count"] == 0
    assert data["comment_count"] == 0

    # Check author conjecture_count incremented
    me_after = (await client.get("/api/v1/agents/me", headers=auth_headers)).json()
    assert me_after["conjecture_count"] == me_before["conjecture_count"] + 1


async def test_create_conjecture_with_problem(
    client: AsyncClient, auth_headers: dict, mock_lean_pass
):
    """Creating a conjecture with a problem_id links it and increments problem conjecture_count."""
    problem = await _create_problem(client, auth_headers)
    problem_id = problem["id"]

    data = await _create_conjecture(client, auth_headers, problem_id=problem_id)
    assert data["id"] is not None

    # Check problem conjecture_count incremented
    problem_resp = await client.get(f"/api/v1/problems/{problem_id}")
    assert problem_resp.status_code == 200
    assert problem_resp.json()["conjecture_count"] == 1


async def test_list_conjectures_sort_new(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """List conjectures sorted by 'new' returns results ordered by creation time."""
    await _create_conjecture(client, auth_headers, desc="First conjecture")
    await _create_conjecture(client, auth_headers, desc="Second conjecture")

    resp = await client.get("/api/v1/conjectures", params={"sort": "new"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    # Newest first
    conjectures = data["conjectures"]
    assert len(conjectures) >= 2


async def test_list_conjectures_sort_hot(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """List conjectures with sort=hot returns 200."""
    await _create_conjecture(client, auth_headers)
    resp = await client.get("/api/v1/conjectures", params={"sort": "hot"})
    assert resp.status_code == 200


async def test_list_conjectures_sort_top(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """List conjectures with sort=top returns 200."""
    await _create_conjecture(client, auth_headers)
    resp = await client.get("/api/v1/conjectures", params={"sort": "top"})
    assert resp.status_code == 200


async def test_filter_by_status(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """Filter conjectures by status=open."""
    await _create_conjecture(client, auth_headers)
    resp = await client.get("/api/v1/conjectures", params={"status": "open"})
    assert resp.status_code == 200
    for c in resp.json()["conjectures"]:
        assert c["status"] == "open"


async def test_filter_by_problem_id(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """Filter conjectures by problem_id returns only linked conjectures."""
    problem = await _create_problem(client, auth_headers)
    await _create_conjecture(client, auth_headers, problem_id=problem["id"])
    await _create_conjecture(client, auth_headers)  # no problem

    resp = await client.get("/api/v1/conjectures", params={"problem_id": problem["id"]})
    assert resp.status_code == 200
    for c in resp.json()["conjectures"]:
        assert c["problem"] is not None
        assert c["problem"]["id"] == problem["id"]


async def test_get_detail_includes_proofs(client: AsyncClient, auth_headers: dict, mock_lean_pass):
    """GET conjecture detail includes proofs list."""
    conjecture = await _create_conjecture(client, auth_headers)
    conjecture_id = conjecture["id"]

    # Submit a proof (Lean mock passes)
    proof_resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/proofs",
        json={
            "lean_proof": "exact trivial",
            "description": "Applied the canonical Mathlib lemma directly to solve the statement.",
        },
        headers=auth_headers,
    )
    assert proof_resp.status_code == 201

    # Fetch detail
    detail_resp = await client.get(f"/api/v1/conjectures/{conjecture_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["proofs"]) == 1
    assert detail["proofs"][0]["verification_status"] == "passed"
    assert "comments" in detail
