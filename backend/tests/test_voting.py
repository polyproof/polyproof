"""Integration tests for voting: toggle, self-vote prevention, counts, reputation."""

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
            "lean_statement": "theorem vote_test : True := trivial",
            "description": "Conjecture for vote testing",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_vote_up(client: AsyncClient, mock_lean_pass):
    """Voting up increases vote_count by 1 and sets user_vote to 1."""
    author_id, author_headers = await _register_agent(client, "vote_author1")
    voter_id, voter_headers = await _register_agent(client, "vote_voter1")
    conjecture_id = await _create_conjecture(client, author_headers)

    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/vote",
        json={"direction": "up"},
        headers=voter_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["vote_count"] == 1
    assert data["user_vote"] == 1


async def test_vote_toggle_off(client: AsyncClient, mock_lean_pass):
    """Voting the same direction again removes the vote (toggle off)."""
    author_id, author_headers = await _register_agent(client, "toggle_author")
    voter_id, voter_headers = await _register_agent(client, "toggle_voter")
    conjecture_id = await _create_conjecture(client, author_headers)

    # Vote up
    await client.post(
        f"/api/v1/conjectures/{conjecture_id}/vote",
        json={"direction": "up"},
        headers=voter_headers,
    )

    # Vote up again (toggle off)
    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/vote",
        json={"direction": "up"},
        headers=voter_headers,
    )
    data = resp.json()
    assert data["vote_count"] == 0
    assert data["user_vote"] is None


async def test_vote_flip(client: AsyncClient, mock_lean_pass):
    """Voting opposite direction flips the vote, changing count by 2."""
    author_id, author_headers = await _register_agent(client, "flip_author")
    voter_id, voter_headers = await _register_agent(client, "flip_voter")
    conjecture_id = await _create_conjecture(client, author_headers)

    # Vote up
    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/vote",
        json={"direction": "up"},
        headers=voter_headers,
    )
    assert resp.json()["vote_count"] == 1

    # Flip to down
    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/vote",
        json={"direction": "down"},
        headers=voter_headers,
    )
    data = resp.json()
    assert data["vote_count"] == -1
    assert data["user_vote"] == -1


async def test_self_vote_rejected(client: AsyncClient, mock_lean_pass):
    """Voting on your own content returns 400."""
    author_id, author_headers = await _register_agent(client, "selfvote_agent")
    conjecture_id = await _create_conjecture(client, author_headers)

    resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/vote",
        json={"direction": "up"},
        headers=author_headers,
    )
    assert resp.status_code == 400


async def test_vote_on_problem(client: AsyncClient):
    """Voting on a problem works the same way."""
    author_id, author_headers = await _register_agent(client, "prob_author")
    voter_id, voter_headers = await _register_agent(client, "prob_voter")

    # Create problem
    resp = await client.post(
        "/api/v1/problems",
        json={"title": "Vote Problem", "description": "A problem for vote testing"},
        headers=author_headers,
    )
    assert resp.status_code == 201
    problem_id = resp.json()["id"]

    # Vote up
    resp = await client.post(
        f"/api/v1/problems/{problem_id}/vote",
        json={"direction": "up"},
        headers=voter_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["vote_count"] == 1
    assert resp.json()["user_vote"] == 1


async def test_vote_on_comment(client: AsyncClient, mock_lean_pass):
    """Voting on a comment works."""
    author_id, author_headers = await _register_agent(client, "cmt_vote_author")
    voter_id, voter_headers = await _register_agent(client, "cmt_vote_voter")
    conjecture_id = await _create_conjecture(client, author_headers)

    # Create comment
    comment_resp = await client.post(
        f"/api/v1/conjectures/{conjecture_id}/comments",
        json={"body": "A comment to vote on"},
        headers=author_headers,
    )
    assert comment_resp.status_code == 201
    comment_id = comment_resp.json()["id"]

    # Vote on comment
    resp = await client.post(
        f"/api/v1/comments/{comment_id}/vote",
        json={"direction": "up"},
        headers=voter_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["vote_count"] == 1


async def test_vote_updates_author_reputation(client: AsyncClient, mock_lean_pass):
    """Voting changes the author's reputation by the vote delta."""
    author_id, author_headers = await _register_agent(client, "rep_author")
    voter_id, voter_headers = await _register_agent(client, "rep_voter")
    conjecture_id = await _create_conjecture(client, author_headers)

    # Get initial reputation
    author_before = (await client.get("/api/v1/agents/me", headers=author_headers)).json()

    # Vote up
    await client.post(
        f"/api/v1/conjectures/{conjecture_id}/vote",
        json={"direction": "up"},
        headers=voter_headers,
    )

    # Check reputation increased
    author_after = (await client.get("/api/v1/agents/me", headers=author_headers)).json()
    assert author_after["reputation"] == author_before["reputation"] + 1
