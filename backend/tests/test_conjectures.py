"""Tests for conjecture detail, tree, and list endpoints."""

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
async def seed_tree(db_session: AsyncSession, seed_project):
    """Create a tree: root -> child1, child2 (child1 proved, child2 open)."""
    project = seed_project["project"]
    root = seed_project["root_conjecture"]

    child1 = Conjecture(
        id=uuid4(),
        project_id=project.id,
        parent_id=root.id,
        lean_statement="Nat.add_comm",
        description="Child 1 - proved",
        status="proved",
        priority="high",
        proof_lean="exact Nat.add_comm",
    )
    child2 = Conjecture(
        id=uuid4(),
        project_id=project.id,
        parent_id=root.id,
        lean_statement="Nat.add_assoc",
        description="Child 2 - open",
        status="open",
        priority="normal",
    )
    db_session.add(child1)
    db_session.add(child2)
    await db_session.flush()

    return {"root": root, "child1": child1, "child2": child2, "project": project}


async def test_get_conjecture_detail(client: AsyncClient, seed_project):
    conj_id = str(seed_project["root_conjecture"].id)
    resp = await client.get(f"/api/v1/conjectures/{conj_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == conj_id
    assert data["lean_statement"] == "∀ n : Nat, n + 0 = n"
    assert data["status"] == "open"
    assert "parent_chain" in data
    assert "children" in data
    assert "proved_siblings" in data
    assert "comments" in data


async def test_get_conjecture_detail_with_parent_chain(client: AsyncClient, seed_tree):
    """Child conjecture should have parent in its parent_chain."""
    child1_id = str(seed_tree["child1"].id)
    resp = await client.get(f"/api/v1/conjectures/{child1_id}")
    assert resp.status_code == 200
    data = resp.json()
    parent_chain = data["parent_chain"]
    assert len(parent_chain) >= 1
    assert parent_chain[-1]["id"] == str(seed_tree["root"].id)


async def test_get_conjecture_detail_with_children(client: AsyncClient, seed_tree):
    """Root conjecture should list its children."""
    root_id = str(seed_tree["root"].id)
    resp = await client.get(f"/api/v1/conjectures/{root_id}")
    assert resp.status_code == 200
    data = resp.json()
    children_ids = {c["id"] for c in data["children"]}
    assert str(seed_tree["child1"].id) in children_ids
    assert str(seed_tree["child2"].id) in children_ids


async def test_get_conjecture_detail_with_siblings(client: AsyncClient, seed_tree):
    """Open child should see proved siblings."""
    child2_id = str(seed_tree["child2"].id)
    resp = await client.get(f"/api/v1/conjectures/{child2_id}")
    assert resp.status_code == 200
    data = resp.json()
    sibling_ids = {s["id"] for s in data["proved_siblings"]}
    assert str(seed_tree["child1"].id) in sibling_ids


async def test_get_conjecture_not_found(client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"/api/v1/conjectures/{fake_id}")
    assert resp.status_code == 404


async def test_get_project_tree(client: AsyncClient, seed_tree):
    """Tree endpoint should return nested structure."""
    project_id = str(seed_tree["project"].id)
    resp = await client.get(f"/api/v1/projects/{project_id}/tree")
    assert resp.status_code == 200
    data = resp.json()
    root = data["root"]
    assert root is not None
    assert root["id"] == str(seed_tree["root"].id)
    assert len(root["children"]) == 2
    child_ids = {c["id"] for c in root["children"]}
    assert str(seed_tree["child1"].id) in child_ids
    assert str(seed_tree["child2"].id) in child_ids


async def test_list_project_conjectures(client: AsyncClient, seed_tree):
    """List conjectures for a project with filters."""
    project_id = str(seed_tree["project"].id)

    # List all (non-invalid)
    resp = await client.get(f"/api/v1/projects/{project_id}/conjectures")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3  # root + 2 children

    # Filter by status
    resp = await client.get(f"/api/v1/projects/{project_id}/conjectures?status=open")
    assert resp.status_code == 200
    data = resp.json()
    for conj in data["conjectures"]:
        assert conj["status"] == "open"
