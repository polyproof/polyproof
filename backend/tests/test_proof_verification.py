"""Tests for locked proof signature, forbidden keywords, axiom checking, and dedup."""

import pytest
from httpx import AsyncClient

from app.services.lean_client import (
    ALLOWED_AXIOMS,
    FORBIDDEN_KEYWORDS,
    LeanResult,
    _check_axioms,
    verify_proof,
)

pytestmark = pytest.mark.asyncio

# Description that meets the 50-char minimum requirement
_PROOF_DESC = "Applied the canonical Mathlib lemma directly to solve the statement."


# ---------------------------------------------------------------------------
# Unit tests for lean_client functions
# ---------------------------------------------------------------------------


class TestForbiddenKeywords:
    """Forbidden keyword rejection in verify_proof."""

    async def test_sorry_rejected(self):
        result = await verify_proof("True", "sorry")
        assert result.status == "rejected"
        assert "sorry" in result.error

    async def test_axiom_rejected(self):
        result = await verify_proof("True", "axiom myAx : False")
        assert result.status == "rejected"
        assert "axiom" in result.error

    async def test_native_decide_rejected(self):
        result = await verify_proof("True", "native_decide")
        assert result.status == "rejected"
        assert "native_decide" in result.error

    async def test_unsafe_rejected(self):
        result = await verify_proof("True", "unsafe def foo := 1")
        assert result.status == "rejected"
        assert "unsafe" in result.error

    async def test_macro_rejected(self):
        result = await verify_proof("True", "macro foo : term => sorry")
        assert result.status == "rejected"
        assert "macro" in result.error

    async def test_case_insensitive(self):
        result = await verify_proof("True", "SORRY")
        assert result.status == "rejected"
        assert "sorry" in result.error.lower()

    async def test_all_forbidden_keywords_present(self):
        """Ensure FORBIDDEN_KEYWORDS list has the expected entries."""
        keywords_lower = [k.lower().strip() for k in FORBIDDEN_KEYWORDS]
        assert "sorry" in keywords_lower
        assert "axiom" in keywords_lower
        assert "native_decide" in keywords_lower
        assert "implemented_by" in keywords_lower
        assert "unsafeaxiom" in keywords_lower
        assert "#eval" in keywords_lower
        assert "#check" in keywords_lower

    async def test_eval_rejected(self):
        result = await verify_proof("True", '#eval IO.println "pwned"')
        assert result.status == "rejected"
        assert "#eval" in result.error

    async def test_check_rejected(self):
        result = await verify_proof("True", "#check Nat")
        assert result.status == "rejected"
        assert "#check" in result.error


class TestLockedSignature:
    """Locked Lean file construction in verify_proof."""

    async def test_locked_signature_sent_to_lean(self, monkeypatch):
        """verify_proof constructs a locked Lean file with the correct structure."""
        captured_code = []

        async def _mock_send(code, *, allow_sorry, timeout=60):
            captured_code.append(code)
            return LeanResult(
                status="passed",
                messages=[
                    {
                        "severity": "info",
                        "data": "'_polyproof_proof' depends on axioms: [propext]",
                    }
                ],
            )

        monkeypatch.setattr("app.services.lean_client._send_to_lean", _mock_send)

        await verify_proof("1 + 1 = 2", "ring")

        assert len(captured_code) == 1
        code = captured_code[0]
        assert "import Mathlib" in code
        assert "theorem _polyproof_proof : 1 + 1 = 2 := by" in code
        assert "  ring" in code
        assert "#print axioms _polyproof_proof" in code

    async def test_locked_signature_preserves_multiline_tactics(self, monkeypatch):
        """Multi-line tactics are properly indented in the locked file."""
        captured_code = []

        async def _mock_send(code, *, allow_sorry, timeout=60):
            captured_code.append(code)
            return LeanResult(
                status="passed",
                messages=[
                    {
                        "severity": "info",
                        "data": "'_polyproof_proof' depends on axioms: [propext]",
                    }
                ],
            )

        monkeypatch.setattr("app.services.lean_client._send_to_lean", _mock_send)

        await verify_proof("True", "constructor\nexact trivial")

        code = captured_code[0]
        assert "  constructor\n  exact trivial" in code


class TestCheckAxioms:
    """Axiom checking via _check_axioms."""

    def test_standard_axioms_pass(self):
        messages = [
            {
                "severity": "info",
                "data": "'_polyproof_proof' depends on axioms: "
                "[propext, Classical.choice, Quot.sound]",
            }
        ]
        result = _check_axioms(LeanResult(status="passed", messages=messages))
        assert result.status == "passed"

    def test_non_standard_axiom_rejected(self):
        messages = [
            {
                "severity": "info",
                "data": "'_polyproof_proof' depends on axioms: [propext, myCustomAxiom]",
            }
        ]
        result = _check_axioms(LeanResult(status="passed", messages=messages))
        assert result.status == "rejected"
        assert "myCustomAxiom" in result.error

    def test_sorry_ax_rejected(self):
        messages = [
            {
                "severity": "info",
                "data": "'_polyproof_proof' depends on axioms: [sorryAx]",
            }
        ]
        result = _check_axioms(LeanResult(status="passed", messages=messages))
        assert result.status == "rejected"
        assert "sorry" in result.error.lower()

    def test_no_axioms_info_rejected(self):
        """If #print axioms produces no 'depends on axioms' line, reject."""
        messages = [{"severity": "info", "data": "some other info"}]
        result = _check_axioms(LeanResult(status="passed", messages=messages))
        assert result.status == "rejected"
        assert "axiom information" in result.error.lower()

    def test_empty_messages_rejected(self):
        """Empty messages means no axiom output — reject."""
        result = _check_axioms(LeanResult(status="passed", messages=[]))
        assert result.status == "rejected"
        assert "axiom information" in result.error.lower()

    def test_none_messages_rejected(self):
        """None messages means no axiom output — reject."""
        result = _check_axioms(LeanResult(status="passed", messages=None))
        assert result.status == "rejected"
        assert "axiom information" in result.error.lower()

    def test_no_dependency_axioms_pass(self):
        """If #print axioms says 'does not depend on any axioms', pass."""
        messages = [
            {
                "severity": "info",
                "data": "'_polyproof_proof' does not depend on any axioms",
            }
        ]
        result = _check_axioms(LeanResult(status="passed", messages=messages))
        assert result.status == "passed"

    def test_allowed_axioms_set(self):
        assert ALLOWED_AXIOMS == {"propext", "Classical.choice", "Quot.sound"}


# ---------------------------------------------------------------------------
# Integration tests (API level)
# ---------------------------------------------------------------------------


async def _create_conjecture(client: AsyncClient, headers: dict) -> str:
    """Helper: create a conjecture and return its ID."""
    resp = await client.post(
        "/api/v1/conjectures",
        json={
            "lean_statement": "theorem test_thm : True := trivial",
            "description": "Test conjecture for proof verification tests",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestProofDeduplication:
    """Platform-wide proof deduplication."""

    async def test_duplicate_proof_rejected(
        self, client: AsyncClient, auth_headers: dict, mock_lean_fail
    ):
        """Submitting the same tactics twice for one conjecture returns 409."""
        conjecture_id = await _create_conjecture(client, auth_headers)

        # First submission — fails Lean CI so conjecture stays open
        resp1 = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "exact trivial", "description": _PROOF_DESC},
            headers=auth_headers,
        )
        assert resp1.status_code == 201
        assert resp1.json()["verification_status"] == "rejected"

        # Second submission with same tactics — should hit dedup 409
        resp2 = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "exact trivial", "description": _PROOF_DESC},
            headers=auth_headers,
        )
        assert resp2.status_code == 409

    async def test_different_tactics_allowed(
        self, client: AsyncClient, auth_headers: dict, mock_lean_fail
    ):
        """Different tactics for the same conjecture are allowed."""
        conjecture_id = await _create_conjecture(client, auth_headers)

        resp1 = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "exact trivial", "description": _PROOF_DESC},
            headers=auth_headers,
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "simp", "description": _PROOF_DESC},
            headers=auth_headers,
        )
        assert resp2.status_code == 201

    async def test_whitespace_normalized_for_dedup(
        self, client: AsyncClient, auth_headers: dict, mock_lean_fail
    ):
        """Whitespace differences don't bypass dedup."""
        conjecture_id = await _create_conjecture(client, auth_headers)

        # First submission with normal whitespace
        resp1 = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "exact trivial", "description": _PROOF_DESC},
            headers=auth_headers,
        )
        assert resp1.status_code == 201

        # Second submission with extra whitespace — should still hit dedup
        resp2 = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "exact  \t trivial", "description": _PROOF_DESC},
            headers=auth_headers,
        )
        assert resp2.status_code == 409


class TestVerifyEndpointWithConjectureId:
    """POST /verify with optional conjecture_id."""

    async def test_verify_with_conjecture_id(
        self, client: AsyncClient, auth_headers: dict, mock_lean_pass
    ):
        """When conjecture_id is provided, wraps as locked proof."""
        conjecture_id = await _create_conjecture(client, auth_headers)

        resp = await client.post(
            "/api/v1/verify",
            json={
                "lean_code": "exact trivial",
                "conjecture_id": conjecture_id,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "passed"

    async def test_verify_without_conjecture_id(
        self, client: AsyncClient, auth_headers: dict, mock_lean_pass
    ):
        """When conjecture_id is omitted, sends code as-is (backward compatible)."""
        resp = await client.post(
            "/api/v1/verify",
            json={"lean_code": "theorem foo : True := trivial"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "passed"

    async def test_verify_with_invalid_conjecture_id(
        self, client: AsyncClient, auth_headers: dict, mock_lean_pass
    ):
        """When conjecture_id doesn't exist, returns 404."""
        resp = await client.post(
            "/api/v1/verify",
            json={
                "lean_code": "exact trivial",
                "conjecture_id": "00000000-0000-0000-0000-000000000000",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_verify_forbidden_keyword_with_conjecture(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Forbidden keywords are rejected even through /verify with conjecture_id."""
        conjecture_id = await _create_conjecture(client, auth_headers)

        resp = await client.post(
            "/api/v1/verify",
            json={
                "lean_code": "sorry",
                "conjecture_id": conjecture_id,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert "sorry" in data["error"].lower()


class TestProofDescriptionRequired:
    """Proof description is now required with min 50 chars."""

    async def test_missing_description_rejected(
        self, client: AsyncClient, auth_headers: dict, mock_lean_pass
    ):
        """Proof without description returns 422."""
        conjecture_id = await _create_conjecture(client, auth_headers)

        resp = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "exact trivial"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_short_description_rejected(
        self, client: AsyncClient, auth_headers: dict, mock_lean_pass
    ):
        """Proof with too-short description returns 422."""
        conjecture_id = await _create_conjecture(client, auth_headers)

        resp = await client.post(
            f"/api/v1/conjectures/{conjecture_id}/proofs",
            json={"lean_proof": "exact trivial", "description": "Too short"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
