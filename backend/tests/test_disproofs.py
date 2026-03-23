"""Tests for disproof submission and descendant invalidation."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conjecture import Conjecture


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


async def test_submit_disproof_pass(client: AsyncClient, seed_agent, seed_problem, mock_lean_pass):
    """Submit a valid disproof -> conjecture becomes disproved."""
    conj_id = str(seed_problem["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/disproofs",
        headers=headers,
        json={"lean_code": "intro n; exact absurd rfl (Nat.lt_irrefl n)"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "disproved"
    assert data["conjecture_id"] == conj_id


async def test_disproof_on_closed_conjecture(
    client: AsyncClient, seed_agent, seed_problem, mock_lean_pass
):
    """Submit disproof on already-proved conjecture -> 409."""
    conj_id = str(seed_problem["root_conjecture"].id)
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    # First: prove it
    await client.post(
        f"/api/v1/conjectures/{conj_id}/proofs",
        headers=headers,
        json={"lean_code": "simp"},
    )

    # Then: try to disprove
    resp = await client.post(
        f"/api/v1/conjectures/{conj_id}/disproofs",
        headers=headers,
        json={"lean_code": "simp"},
    )
    assert resp.status_code == 409


async def test_descendant_invalidation(
    client: AsyncClient, seed_agent, db_session: AsyncSession, seed_problem, mock_lean_pass
):
    """Disprove a decomposed parent -> children become invalid."""
    project = seed_problem["problem"]
    root = seed_problem["root_conjecture"]

    # Create children manually (simulating decomposition)
    child1 = Conjecture(
        id=uuid4(),
        project_id=project.id,
        parent_id=root.id,
        lean_statement="Nat.add_comm",
        description="Child 1",
        status="open",
        priority="normal",
    )
    grandchild = Conjecture(
        id=uuid4(),
        project_id=project.id,
        parent_id=child1.id,
        lean_statement="Nat.succ_add",
        description="Grandchild",
        status="open",
        priority="normal",
    )
    db_session.add(child1)
    db_session.add(grandchild)

    # Set root to decomposed so disproof can trigger invalidation
    root.status = "decomposed"
    await db_session.flush()

    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}
    resp = await client.post(
        f"/api/v1/conjectures/{root.id}/disproofs",
        headers=headers,
        json={"lean_code": "exact absurd rfl"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "disproved"
    assert data["descendants_invalidated"] >= 2

    # Verify children are invalid
    await db_session.refresh(child1)
    await db_session.refresh(grandchild)
    assert child1.status == "invalid"
    assert grandchild.status == "invalid"
