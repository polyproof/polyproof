"""Tests for automatic parent assembly when all children are proved."""

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


@pytest.fixture
async def decomposed_project(db_session: AsyncSession, seed_problem):
    """Create a decomposed root with two children and a sorry_proof."""
    project = seed_problem["problem"]
    root = seed_problem["root_conjecture"]

    # Set root to decomposed with a sorry_proof that references children
    root.status = "decomposed"
    root.sorry_proof = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h1 : Nat.add_comm := sorry\n"
        "  have h2 : Nat.add_zero := sorry\n"
        "  exact h2"
    )
    await db_session.flush()

    child1 = Conjecture(
        id=uuid4(),
        project_id=project.id,
        parent_id=root.id,
        lean_statement="Nat.add_comm",
        description="Child 1",
        status="open",
        priority="normal",
    )
    child2 = Conjecture(
        id=uuid4(),
        project_id=project.id,
        parent_id=root.id,
        lean_statement="Nat.add_zero",
        description="Child 2",
        status="open",
        priority="normal",
    )
    db_session.add(child1)
    db_session.add(child2)
    await db_session.flush()

    return {
        "problem": project,
        "root": root,
        "child1": child1,
        "child2": child2,
    }


async def test_assembly_triggered_when_all_children_proved(
    client: AsyncClient,
    seed_agent,
    db_session: AsyncSession,
    decomposed_project,
    monkeypatch,
):
    """Prove all children -> parent auto-assembled (assembly_triggered=True)."""
    child1 = decomposed_project["child1"]
    child2 = decomposed_project["child2"]
    root = decomposed_project["root"]
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    # Mock lean to pass for proofs and for assembly verification
    from app.services.lean_client import LeanResult

    async def _mock_pass(*args, **kwargs):
        return LeanResult(status="passed", error=None)

    monkeypatch.setattr("app.services.lean_client.verify_proof", _mock_pass, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_sorry_proof", _mock_pass, raising=False)

    # Prove child1
    resp = await client.post(
        f"/api/v1/conjectures/{child1.id}/proofs",
        headers=headers,
        json={"lean_code": "exact Nat.add_comm"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "proved"
    # Assembly not triggered yet (child2 still open)
    assert data["assembly_triggered"] is False

    # Prove child2 — this should trigger assembly
    resp = await client.post(
        f"/api/v1/conjectures/{child2.id}/proofs",
        headers=headers,
        json={"lean_code": "exact Nat.add_zero"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "proved"
    assert data["assembly_triggered"] is True
    assert data["parent_proved"] is True

    # Verify root is now proved
    await db_session.refresh(root)
    assert root.status == "proved"
    assert root.proof_lean is not None


async def test_assembly_not_triggered_with_open_children(
    client: AsyncClient,
    seed_agent,
    decomposed_project,
    mock_lean_pass,
):
    """Prove one child but not the other -> assembly not triggered."""
    child1 = decomposed_project["child1"]
    headers = {"Authorization": f"Bearer {seed_agent['api_key']}"}

    resp = await client.post(
        f"/api/v1/conjectures/{child1.id}/proofs",
        headers=headers,
        json={"lean_code": "exact Nat.add_comm"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "proved"
    assert data["assembly_triggered"] is False
