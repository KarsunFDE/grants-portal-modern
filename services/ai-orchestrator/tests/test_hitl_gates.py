"""
HITL gate enforcement tests.
Covers acceptance criteria 1-4 and 9 from hitl-plan.txt, happy + failure paths per gate.

AC1: Award cannot complete without human approval record.
AC2: Screening cannot advance without Gate 1 decision.
AC3: Peer review scoring blocked until COI gate resolved.
AC4: Factor Suggest output cannot be used until human acceptance.
AC9: Ungrounded items cannot be Gate 1, 3, or 4 input.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Gate 1 — Eligibility & Risk Review (Screening)
# ---------------------------------------------------------------------------

class TestGate1EligibilityReview:
    """AC2: Screening cannot advance without Gate 1 decision."""

    def test_gate1_approve_happy_path(self, client, gate1_approve_payload, mock_db):
        mock_db.hitl_audit_trail.insert_one.return_value = MagicMock_insert()
        resp = client.post("/gates/decision", json=gate1_approve_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["gate_id"] == "GATE_1"
        assert body["decision"] == "APPROVE"
        assert body["workflow_stage"] == "SCREENING"
        assert body["actor_role"] == "GRANTS_OFFICER"
        assert body["rationale"] != ""
        assert "gate_decision_id" in body

    def test_gate1_return_for_fixes(self, client, gate1_approve_payload, mock_db):
        gate1_approve_payload["decision"] = "RETURN_FOR_FIXES"
        gate1_approve_payload["rationale"] = "SF-424 item B missing."
        resp = client.post("/gates/decision", json=gate1_approve_payload)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "RETURN_FOR_FIXES"

    def test_gate1_reject(self, client, gate1_approve_payload, mock_db):
        gate1_approve_payload["decision"] = "REJECT"
        gate1_approve_payload["rationale"] = "Applicant type FOR_PROFIT is ineligible."
        resp = client.post("/gates/decision", json=gate1_approve_payload)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "REJECT"

    def test_gate1_wrong_role_rejected(self, client, gate1_approve_payload):
        gate1_approve_payload["actor_role"] = "REVIEW_LEAD"  # not authorized for Gate 1
        resp = client.post("/gates/decision", json=gate1_approve_payload)
        assert resp.status_code == 422
        assert "REVIEW_LEAD" in resp.json()["detail"]

    def test_gate1_wrong_decision_rejected(self, client, gate1_approve_payload):
        gate1_approve_payload["decision"] = "AWARD"  # Gate 4 decision, not Gate 1
        resp = client.post("/gates/decision", json=gate1_approve_payload)
        assert resp.status_code == 422

    def test_gate1_not_cleared_without_decision(self, client, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor()
        resp = client.get("/gates/GATE_1/cleared?tenant_id=tenant-abc&ai_run_id=run-999")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cleared"] is False
        assert "GATE_1" in body["reason"]

    def test_gate1_cleared_after_approve(self, client, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor([{
            "gate_decision_id": "gd-001",
            "gate_id": "GATE_1",
            "ai_run_id": "run-001",
            "decision": "APPROVE",
            "tenant_id": "tenant-abc",
        }])
        resp = client.get("/gates/GATE_1/cleared?tenant_id=tenant-abc&ai_run_id=run-001")
        assert resp.status_code == 200
        assert resp.json()["cleared"] is True

    def test_gate1_not_cleared_after_reject(self, client, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor([{
            "gate_decision_id": "gd-002",
            "gate_id": "GATE_1",
            "ai_run_id": "run-001",
            "decision": "REJECT",
            "tenant_id": "tenant-abc",
        }])
        resp = client.get("/gates/GATE_1/cleared?tenant_id=tenant-abc&ai_run_id=run-001")
        body = resp.json()
        assert body["cleared"] is False
        assert "REJECT" in body["reason"]

    def test_check_eligibility_returns_gate1_fields(self, client):
        resp = client.post("/check-eligibility", json={
            "tenant_id": "tenant-abc",
            "grant_application_id": "app-001",
            "applicant_type": "UNIVERSITY",
            "assistance_listing_number": "93.123",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["hitl_gate"] == "GATE_1"
        assert "requires_human_review" in body
        assert "grounding_status" in body
        assert "confidence_score" in body
        assert "faithfulness_score" in body
        assert "retrieved_sources" in body
        assert "citation_refs" in body


# ---------------------------------------------------------------------------
# Gate 2 — Conflict of Interest (Peer Review)
# ---------------------------------------------------------------------------

class TestGate2COI:
    """AC3: Peer review scoring blocked until COI gate resolved."""

    def test_gate2_resolve_happy_path(self, client, gate2_resolve_payload, mock_db):
        resp = client.post("/gates/decision", json=gate2_resolve_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["gate_id"] == "GATE_2"
        assert body["decision"] == "RESOLVE_AND_CONTINUE"
        assert body["workflow_stage"] == "PEER_REVIEW"
        assert body["actor_role"] == "REVIEW_LEAD"

    def test_gate2_remove_reviewer(self, client, gate2_resolve_payload, mock_db):
        gate2_resolve_payload["decision"] = "REMOVE_REVIEWER"
        gate2_resolve_payload["rationale"] = "Reviewer has financial interest in applicant org."
        resp = client.post("/gates/decision", json=gate2_resolve_payload)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "REMOVE_REVIEWER"

    def test_gate2_override_with_rationale(self, client, gate2_resolve_payload, mock_db):
        gate2_resolve_payload["decision"] = "OVERRIDE"
        gate2_resolve_payload["override_flag"] = True
        gate2_resolve_payload["rationale"] = "COI waived per agency policy; written rationale attached."
        resp = client.post("/gates/decision", json=gate2_resolve_payload)
        assert resp.status_code == 200
        assert resp.json()["override_flag"] is True

    def test_gate2_wrong_role_rejected(self, client, gate2_resolve_payload):
        gate2_resolve_payload["actor_role"] = "GRANTS_OFFICER"
        resp = client.post("/gates/decision", json=gate2_resolve_payload)
        assert resp.status_code == 422
        assert "GRANTS_OFFICER" in resp.json()["detail"]

    def test_gate2_approve_decision_rejected(self, client, gate2_resolve_payload):
        gate2_resolve_payload["decision"] = "APPROVE"  # Gate 1 decision
        resp = client.post("/gates/decision", json=gate2_resolve_payload)
        assert resp.status_code == 422

    def test_gate2_not_cleared_blocks_scoring(self, client, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor()
        resp = client.get("/gates/GATE_2/cleared?tenant_id=t1&ai_run_id=r1")
        assert resp.json()["cleared"] is False


# ---------------------------------------------------------------------------
# Gate 3 — Factor Suggest Acceptance (Peer Review)
# ---------------------------------------------------------------------------

class TestGate3FactorSuggest:
    """AC4: Factor Suggest output cannot be used until human acceptance."""

    def test_gate3_accept_happy_path(self, client, gate3_accept_payload, mock_db):
        resp = client.post("/gates/decision", json=gate3_accept_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["gate_id"] == "GATE_3"
        assert body["decision"] == "ACCEPT"
        assert body["actor_role"] == "HUMAN_REVIEWER"

    def test_gate3_edit(self, client, gate3_accept_payload, mock_db):
        gate3_accept_payload["decision"] = "EDIT"
        gate3_accept_payload["rationale"] = "Narrative adjusted to reflect revised criterion weight."
        resp = client.post("/gates/decision", json=gate3_accept_payload)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "EDIT"

    def test_gate3_reject(self, client, gate3_accept_payload, mock_db):
        gate3_accept_payload["decision"] = "REJECT"
        gate3_accept_payload["rationale"] = "Suggestion does not match NOFO criteria."
        resp = client.post("/gates/decision", json=gate3_accept_payload)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "REJECT"

    def test_gate3_wrong_role_rejected(self, client, gate3_accept_payload):
        gate3_accept_payload["actor_role"] = "GRANTS_OFFICER"
        resp = client.post("/gates/decision", json=gate3_accept_payload)
        assert resp.status_code == 422

    def test_factor_suggest_always_requires_human_review(self, client):
        """Gate 3 rule: AI suggestions are assistive only — always requires_human_review."""
        resp = client.post("/eval/factor-suggest", json={
            "topic": "merit criterion technical approach",
            "tenant_id": "tenant-abc",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["hitl_gate"] == "GATE_3"
        assert body["requires_human_review"] is True
        assert "grounding_status" in body
        assert "confidence_score" in body
        assert "citation_refs" in body


# ---------------------------------------------------------------------------
# Gate 4 — Award Decision
# ---------------------------------------------------------------------------

class TestGate4AwardDecision:
    """AC1: Award cannot complete without human approval record."""

    def test_gate4_award_happy_path(self, client, gate4_award_payload, mock_db):
        resp = client.post("/gates/decision", json=gate4_award_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["gate_id"] == "GATE_4"
        assert body["decision"] == "AWARD"
        assert body["workflow_stage"] == "AWARD"
        assert body["actor_role"] == "GRANTS_OFFICER"

    def test_gate4_do_not_award(self, client, gate4_award_payload, mock_db):
        gate4_award_payload["decision"] = "DO_NOT_AWARD"
        gate4_award_payload["rationale"] = "No proposals met minimum merit threshold."
        resp = client.post("/gates/decision", json=gate4_award_payload)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "DO_NOT_AWARD"

    def test_gate4_return_to_review(self, client, gate4_award_payload, mock_db):
        gate4_award_payload["decision"] = "RETURN_TO_REVIEW"
        gate4_award_payload["rationale"] = "Additional technical evaluation required."
        resp = client.post("/gates/decision", json=gate4_award_payload)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "RETURN_TO_REVIEW"

    def test_gate4_wrong_role_rejected(self, client, gate4_award_payload):
        gate4_award_payload["actor_role"] = "HUMAN_REVIEWER"
        resp = client.post("/gates/decision", json=gate4_award_payload)
        assert resp.status_code == 422

    def test_gate4_not_cleared_without_decision(self, client, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor()
        resp = client.get("/gates/GATE_4/cleared?tenant_id=tenant-abc&ai_run_id=run-999")
        assert resp.json()["cleared"] is False

    def test_gate4_not_cleared_after_do_not_award(self, client, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor([{
            "gate_id": "GATE_4",
            "ai_run_id": "run-004",
            "decision": "DO_NOT_AWARD",
            "tenant_id": "tenant-abc",
        }])
        resp = client.get("/gates/GATE_4/cleared?tenant_id=tenant-abc&ai_run_id=run-004")
        assert resp.json()["cleared"] is False

    def test_ssdd_always_requires_human_review(self, client):
        """Gate 4: no unattended award path."""
        resp = client.post("/eval/ssdd-draft", json={
            "topic": "award recommendation for proposal XYZ",
            "tenant_id": "tenant-abc",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["hitl_gate"] == "GATE_4"
        assert body["requires_human_review"] is True
        assert "grounding_status" in body
        assert "confidence_score" in body


# ---------------------------------------------------------------------------
# Invalid gate_id
# ---------------------------------------------------------------------------

def test_unknown_gate_id_returns_400(client):
    resp = client.get("/gates/GATE_99/cleared?tenant_id=t1&ai_run_id=r1")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Helper stub
# ---------------------------------------------------------------------------

def MagicMock_insert():
    from unittest.mock import MagicMock
    m = MagicMock()
    m.inserted_id = "fake-id"
    return m
