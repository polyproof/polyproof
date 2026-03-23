"""Tests for decomposition_service: create, update (diff), revert, reactivation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import decomposition_service


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.api.rate_limit.ip_limiter.enabled", False)
    monkeypatch.setattr("app.api.rate_limit.auth_limiter.enabled", False)


pytestmark = pytest.mark.usefixtures("_disable_rate_limit")


@pytest.fixture
def mock_lean_sorry_pass(monkeypatch):
    """Mock Lean CI to pass for sorry-proof verification and all other checks."""
    from app.services.lean_client import LeanResult

    async def _mock(*args, **kwargs):
        return LeanResult(status="passed", error=None)

    monkeypatch.setattr("app.services.lean_client.verify_sorry_proof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.typecheck", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify_proof", _mock, raising=False)
    monkeypatch.setattr("app.services.lean_client.verify", _mock, raising=False)


async def test_create_decomposition(
    db_session: AsyncSession, seed_problem, seed_mega_agent, mock_lean_sorry_pass
):
    """First decomposition: creates children, sets parent to decomposed."""
    root = seed_problem["root_conjecture"]
    mega = seed_mega_agent["agent"]

    sorry_proof = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h1 : Nat.add_comm := sorry\n"
        "  have h2 : Nat.add_zero := sorry\n"
        "  exact h2"
    )

    result = await decomposition_service.update(
        parent_id=root.id,
        children=[
            {"lean_statement": "Nat.add_comm", "description": "First child"},
            {"lean_statement": "Nat.add_zero", "description": "Second child"},
        ],
        sorry_proof=sorry_proof,
        mega_agent_id=mega.id,
        db=db_session,
    )

    assert result["status"] == "ok"
    assert result["parent_status"] == "decomposed"
    assert len(result["children_created"]) == 2

    # Verify parent is decomposed
    await db_session.refresh(root)
    assert root.status == "decomposed"
    assert root.sorry_proof == sorry_proof


async def test_update_decomposition_diff(
    db_session: AsyncSession, seed_problem, seed_mega_agent, mock_lean_sorry_pass
):
    """Update decomposition: preserves matching children, creates new, invalidates removed."""
    root = seed_problem["root_conjecture"]
    mega = seed_mega_agent["agent"]

    sorry_proof_v1 = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h1 : Nat.add_comm := sorry\n"
        "  have h2 : Nat.add_zero := sorry\n"
        "  exact h2"
    )

    # Initial decomposition
    await decomposition_service.update(
        parent_id=root.id,
        children=[
            {"lean_statement": "Nat.add_comm", "description": "Preserved child"},
            {"lean_statement": "Nat.add_zero", "description": "Removed child"},
        ],
        sorry_proof=sorry_proof_v1,
        mega_agent_id=mega.id,
        db=db_session,
    )

    sorry_proof_v2 = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h1 : Nat.add_comm := sorry\n"
        "  have h3 : Nat.succ_add := sorry\n"
        "  exact h3"
    )

    # Update with diff: keep Nat.add_comm, remove Nat.add_zero, add Nat.succ_add
    result = await decomposition_service.update(
        parent_id=root.id,
        children=[
            {"lean_statement": "Nat.add_comm", "description": "Preserved child updated"},
            {"lean_statement": "Nat.succ_add", "description": "New child"},
        ],
        sorry_proof=sorry_proof_v2,
        mega_agent_id=mega.id,
        db=db_session,
    )

    assert result["status"] == "ok"
    assert len(result["children_preserved"]) == 1  # Nat.add_comm preserved
    assert len(result["children_created"]) == 1  # Nat.succ_add created
    assert len(result["children_invalidated"]) >= 1  # Nat.add_zero invalidated


async def test_revert_decomposition(
    db_session: AsyncSession, seed_problem, seed_mega_agent, mock_lean_sorry_pass
):
    """Revert: children invalidated, parent back to open."""
    root = seed_problem["root_conjecture"]
    mega = seed_mega_agent["agent"]

    sorry_proof = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h1 : Nat.add_comm := sorry\n"
        "  exact h1"
    )

    await decomposition_service.update(
        parent_id=root.id,
        children=[
            {"lean_statement": "Nat.add_comm", "description": "Child"},
        ],
        sorry_proof=sorry_proof,
        mega_agent_id=mega.id,
        db=db_session,
    )

    result = await decomposition_service.revert(
        conjecture_id=root.id,
        reason="Strategy change",
        mega_agent_id=mega.id,
        db=db_session,
    )

    assert result["status"] == "ok"
    assert result["conjecture_status"] == "open"
    assert len(result["children_invalidated"]) >= 1

    await db_session.refresh(root)
    assert root.status == "open"
    assert root.sorry_proof is None


async def test_reactivation(
    db_session: AsyncSession, seed_problem, seed_mega_agent, mock_lean_sorry_pass
):
    """Re-add a previously invalidated child -> reactivated."""
    root = seed_problem["root_conjecture"]
    mega = seed_mega_agent["agent"]

    sorry_proof_v1 = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h1 : Nat.add_comm := sorry\n"
        "  exact h1"
    )

    # V1: create child
    await decomposition_service.update(
        parent_id=root.id,
        children=[{"lean_statement": "Nat.add_comm", "description": "Child"}],
        sorry_proof=sorry_proof_v1,
        mega_agent_id=mega.id,
        db=db_session,
    )

    sorry_proof_v2 = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h2 : Nat.add_zero := sorry\n"
        "  exact h2"
    )

    # V2: remove the first child, add a different one (invalidates Nat.add_comm)
    await decomposition_service.update(
        parent_id=root.id,
        children=[{"lean_statement": "Nat.add_zero", "description": "Replacement"}],
        sorry_proof=sorry_proof_v2,
        mega_agent_id=mega.id,
        db=db_session,
    )

    sorry_proof_v3 = (
        "import Mathlib\n\n"
        "theorem root : forall n : Nat, n + 0 = n := by\n"
        "  have h1 : Nat.add_comm := sorry\n"
        "  have h2 : Nat.add_zero := sorry\n"
        "  exact h2"
    )

    # V3: re-add Nat.add_comm -> should reactivate
    result = await decomposition_service.update(
        parent_id=root.id,
        children=[
            {"lean_statement": "Nat.add_comm", "description": "Reactivated child"},
            {"lean_statement": "Nat.add_zero", "description": "Kept child"},
        ],
        sorry_proof=sorry_proof_v3,
        mega_agent_id=mega.id,
        db=db_session,
    )

    assert result["status"] == "ok"
    assert len(result["children_reactivated"]) >= 1


async def test_duplicate_lean_statement_rejected(
    db_session: AsyncSession, seed_problem, seed_mega_agent, mock_lean_sorry_pass
):
    """Duplicate lean_statements in children list should be rejected."""
    root = seed_problem["root_conjecture"]
    mega = seed_mega_agent["agent"]

    sorry_proof = (
        "import Mathlib\n\n"
        "theorem root : True := by\n"
        "  have h1 : True := sorry\n"
        "  have h2 : True := sorry\n"
        "  exact h1"
    )

    result = await decomposition_service.update(
        parent_id=root.id,
        children=[
            {"lean_statement": "True", "description": "Dup 1"},
            {"lean_statement": "True", "description": "Dup 2"},
        ],
        sorry_proof=sorry_proof,
        mega_agent_id=mega.id,
        db=db_session,
    )

    assert result["status"] == "error"
    assert "Duplicate" in result["error"]


async def test_decomposition_on_proved_conjecture(
    db_session: AsyncSession, seed_problem, seed_mega_agent, mock_lean_sorry_pass
):
    """Cannot decompose a proved conjecture."""
    root = seed_problem["root_conjecture"]
    root.status = "proved"
    await db_session.flush()

    mega = seed_mega_agent["agent"]

    result = await decomposition_service.update(
        parent_id=root.id,
        children=[{"lean_statement": "True", "description": "Child"}],
        sorry_proof="have h1 : True := sorry",
        mega_agent_id=mega.id,
        db=db_session,
    )

    assert result["status"] == "error"
    assert "proved" in result["error"].lower()
