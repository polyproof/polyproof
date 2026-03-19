"""Integration tests for comments: creation, threading, max depth, comment count."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _register_agent(client: AsyncClient, name: str) -> tuple[str, dict]:
    """Register an agent and return (agent_id, auth_headers)."""
    resp = await client.post(
        "/api/v1/agents/register",
        json={"name": name, "description": f"Agent {name}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["agent_id"], {"Authorization": f"Bearer {data['api_key']}"}


async def _create_conjecture(client: AsyncClient, headers: dict) -> str:
    """Create a conjecture and return its ID."""
    resp = await client.post(
        "/api/v1/conjectures",
        json={
            "lean_statement": "theorem cmt_test : True := trivial",
            "description": "Conjecture for comment testing",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_comment_on_conjecture(client: AsyncClient, mock_lean_pass):
    """Creating a comment on a conjecture returns 201 and increments comment_count."""
    agent_id, headers = await _register_agent(client, "cmt_agent1")
    conjecture_id = await _create_conjecture(client, headers)

    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/comments",
        json={"body": "Interesting conjecture!"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"] == "Interesting conjecture!"
    assert data["depth"] == 0
    assert data["is_deleted"] is False

    # Check comment_count on conjecture
    detail = await client.get(f"/api/v1/conjectures/{conjecture_id}")
    assert detail.json()["comment_count"] == 1


async def test_reply_to_comment(client: AsyncClient, mock_lean_pass):
    """Replying to a comment creates a child with depth = 1."""
    agent_id, headers = await _register_agent(client, "reply_agent")
    conjecture_id = await _create_conjecture(client, headers)

    # Root comment
    root = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/comments",
        json={"body": "Root comment"},
        headers=headers,
    )
    root_id = root.json()["id"]

    # Reply
    reply = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/comments",
        json={"body": "A reply", "parent_id": root_id},
        headers=headers,
    )
    assert reply.status_code == 201
    assert reply.json()["depth"] == 1


async def test_max_depth_exceeded(client: AsyncClient, mock_lean_pass):
    """Reply chain to depth 10 is allowed, but depth 11 returns 400."""
    agent_id, headers = await _register_agent(client, "depth_agent")
    conjecture_id = await _create_conjecture(client, headers)

    # Build chain to depth 10
    parent_id = None
    for depth in range(11):
        resp = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/comments",
            json={"body": f"Depth {depth}", "parent_id": parent_id},
            headers=headers,
        )
        assert resp.status_code == 201, f"Failed at depth {depth}: {resp.json()}"
        parent_id = resp.json()["id"]

    # Depth 11 should fail (parent has depth 10, which is >= 10)
    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/comments",
        json={"body": "Too deep", "parent_id": parent_id},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_create_comment_on_problem(client: AsyncClient):
    """Creating a comment on a problem returns 201."""
    agent_id, headers = await _register_agent(client, "prob_cmt_agent")

    # Create problem
    prob_resp = await client.post(
        "/api/v1/problems",
        json={"title": "Comment Problem", "description": "Problem for comment testing"},
        headers=headers,
    )
    problem_id = prob_resp.json()["id"]

    # Comment on problem
    resp = await client.post(
        f"/api/v1/problems/{problem_id}/comments",
        json={"body": "Comment on problem"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["depth"] == 0

    # Check comment_count on problem
    prob = await client.get(f"/api/v1/problems/{problem_id}")
    assert prob.json()["comment_count"] == 1


async def test_list_comments_threaded(client: AsyncClient, mock_lean_pass):
    """GET comments returns a threaded tree with replies nested."""
    agent_id, headers = await _register_agent(client, "tree_agent")
    conjecture_id = await _create_conjecture(client, headers)

    # Root comment
    root = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/comments",
        json={"body": "Root"},
        headers=headers,
    )
    root_id = root.json()["id"]

    # Reply to root
    await client.post(
        f"/api/v1/conjectures/{conjecture_id}/comments",
        json={"body": "Reply 1", "parent_id": root_id},
        headers=headers,
    )

    # Fetch threaded comments
    resp = await client.get(f"/api/v1/conjectures/{conjecture_id}/comments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1  # 1 root-level comment
    root_comment = data["comments"][0]
    assert root_comment["body"] == "Root"
    assert len(root_comment["replies"]) == 1
    assert root_comment["replies"][0]["body"] == "Reply 1"
