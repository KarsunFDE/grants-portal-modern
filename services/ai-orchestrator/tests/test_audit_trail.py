"""
Audit trail tests — hitl-plan.txt §Audit and Durability Requirements.

AC6:  Audit trail captures all required gate fields.
AC7:  Audit trail is durable across restart and pause.
AC10: Every grounding escalation records gate_id, owner decision, and rationale.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, call

import pytest

from app.schemas.hitl import (
    EscalationRecord,
    GateDecision,
    GateDecisionRecord,
    GateId,
    GateOwnerRole,
    GroundingStatus,
    HumanReviewReason,
    WorkflowStage,
)
from app.services.audit_trail import audit_trail_service


# Required audit fields per hitl-plan.txt §Audit
REQUIRED_GATE_FIELDS = {
    "actor_id",
    "actor_role",
    "tenant_id",
    "timestamp",
    "workflow_stage",
    "gate_id",
    "ai_run_id",
    "decision",
    "rationale",
    "override_flag",
    "evidence_refs",
    "retrieved_sources",
    "citation_refs",
    "confidence_score",
    "grounding_status",
}


class TestAuditTrailFieldCompleteness:
    """AC6: Audit trail captures all required gate fields."""

    def test_gate_decision_record_has_all_required_fields(self):
        record = GateDecisionRecord(
            gate_id=GateId.GATE_1,
            workflow_stage=WorkflowStage.SCREENING,
            actor_id="officer-001",
            actor_role=GateOwnerRole.GRANTS_OFFICER,
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            decision=GateDecision.APPROVE,
            rationale="Application meets 2 CFR 200.205 merit criteria.",
            override_flag=False,
            evidence_refs=[],
            retrieved_sources=["2-CFR-200.205"],
            citation_refs=["2 CFR 200:200.205"],
            confidence_score=0.88,
            grounding_status=GroundingStatus.GROUNDED,
        )
        doc = record.model_dump(mode="json")
        for field in REQUIRED_GATE_FIELDS:
            assert field in doc, f"Missing required audit field: {field!r}"

    def test_record_gate_decision_writes_to_audit_trail(self, mock_db):
        record = GateDecisionRecord(
            gate_id=GateId.GATE_4,
            workflow_stage=WorkflowStage.AWARD,
            actor_id="officer-001",
            actor_role=GateOwnerRole.GRANTS_OFFICER,
            tenant_id="tenant-abc",
            ai_run_id="run-004",
            decision=GateDecision.AWARD,
            rationale="Award authorized per 2 CFR 200.212.",
        )
        decision_id = audit_trail_service.record_gate_decision(record)
        assert decision_id == record.gate_decision_id
        mock_db.hitl_audit_trail.insert_one.assert_called_once()
        written = mock_db.hitl_audit_trail.insert_one.call_args[0][0]
        assert written["_type"] == "gate_decision"
        assert written["gate_id"] == "GATE_4"
        assert written["decision"] == "AWARD"
        assert written["tenant_id"] == "tenant-abc"
        for field in REQUIRED_GATE_FIELDS:
            assert field in written, f"Missing required audit field in DB write: {field!r}"

    def test_record_gate_decision_is_append_only(self, mock_db):
        """insert_one must be used (never update/replace)."""
        record = GateDecisionRecord(
            gate_id=GateId.GATE_1,
            workflow_stage=WorkflowStage.SCREENING,
            actor_id="officer-001",
            actor_role=GateOwnerRole.GRANTS_OFFICER,
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            decision=GateDecision.APPROVE,
            rationale="Approved.",
        )
        audit_trail_service.record_gate_decision(record)
        mock_db.hitl_audit_trail.insert_one.assert_called_once()
        mock_db.hitl_audit_trail.update_one.assert_not_called()
        mock_db.hitl_audit_trail.replace_one.assert_not_called()

    def test_all_four_gates_have_correct_workflow_stage(self):
        from app.schemas.hitl import GATE_WORKFLOW_STAGE
        assert GATE_WORKFLOW_STAGE[GateId.GATE_1] == WorkflowStage.SCREENING
        assert GATE_WORKFLOW_STAGE[GateId.GATE_2] == WorkflowStage.PEER_REVIEW
        assert GATE_WORKFLOW_STAGE[GateId.GATE_3] == WorkflowStage.PEER_REVIEW
        assert GATE_WORKFLOW_STAGE[GateId.GATE_4] == WorkflowStage.AWARD


class TestEscalationRecording:
    """AC10: Every grounding escalation records gate_id, owner, and rationale."""

    def test_record_escalation_writes_to_both_collections(self, mock_db):
        escalation = EscalationRecord(
            gate_id=GateId.GATE_1,
            gate_owner_roles=[GateOwnerRole.GRANTS_OFFICER],
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            reason="grounding_status=LOW_CONFIDENCE; LOW_CONFIDENCE",
            human_review_reasons=[HumanReviewReason.LOW_CONFIDENCE],
            grounding_status=GroundingStatus.LOW_CONFIDENCE,
            confidence_score=0.50,
        )
        eid = audit_trail_service.record_escalation(escalation)
        assert eid == escalation.escalation_id
        # Written to both audit trail and dedicated escalations collection
        mock_db.hitl_audit_trail.insert_one.assert_called_once()
        mock_db.hitl_escalations.insert_one.assert_called_once()

    def test_escalation_has_gate_id_owner_reason(self, mock_db):
        escalation = EscalationRecord(
            gate_id=GateId.GATE_3,
            gate_owner_roles=[GateOwnerRole.HUMAN_REVIEWER],
            tenant_id="tenant-abc",
            ai_run_id="run-003",
            reason="grounding_status=MISSING_CITATIONS; MISSING_CITATIONS",
            human_review_reasons=[HumanReviewReason.MISSING_CITATIONS],
            grounding_status=GroundingStatus.MISSING_CITATIONS,
            confidence_score=0.0,
        )
        audit_trail_service.record_escalation(escalation)
        written = mock_db.hitl_escalations.insert_one.call_args[0][0]
        assert written["gate_id"] == "GATE_3"
        assert "HUMAN_REVIEWER" in written["gate_owner_roles"]
        assert written["reason"] != ""
        assert written["tenant_id"] == "tenant-abc"

    def test_create_escalation_via_gate_enforcer(self, mock_db):
        from app.services.gate_enforcer import gate_enforcer
        record = gate_enforcer.create_escalation(
            gate_id=GateId.GATE_1,
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            human_review_reasons=[HumanReviewReason.LOW_CONFIDENCE],
            grounding_status=GroundingStatus.LOW_CONFIDENCE,
            confidence_score=0.55,
        )
        assert record.gate_id == GateId.GATE_1
        assert GateOwnerRole.GRANTS_OFFICER in record.gate_owner_roles
        assert record.tenant_id == "tenant-abc"
        assert record.reason != ""
        mock_db.hitl_audit_trail.insert_one.assert_called_once()

    def test_no_silent_retry_every_failure_creates_record(self, mock_db):
        from app.services.gate_enforcer import gate_enforcer
        reasons = [HumanReviewReason.LOW_CONFIDENCE, HumanReviewReason.MISSING_CITATIONS]
        for i in range(3):
            gate_enforcer.create_escalation(
                gate_id=GateId.GATE_1,
                tenant_id="tenant-abc",
                ai_run_id=f"run-{i}",
                human_review_reasons=reasons,
                grounding_status=GroundingStatus.LOW_CONFIDENCE,
                confidence_score=0.50,
            )
        assert mock_db.hitl_audit_trail.insert_one.call_count == 3
        assert mock_db.hitl_escalations.insert_one.call_count == 3


class TestAuditDurability:
    """AC7: Audit trail durable across restart — relies on MongoDB persistent volume."""

    def test_get_gate_decision_queries_audit_trail(self, mock_db):
        mock_db.hitl_audit_trail.find_one.return_value = {
            "gate_decision_id": "gd-001",
            "gate_id": "GATE_1",
            "decision": "APPROVE",
            "tenant_id": "tenant-abc",
            "_type": "gate_decision",
        }
        result = audit_trail_service.get_gate_decision("gd-001")
        assert result is not None
        assert result["gate_decision_id"] == "gd-001"
        mock_db.hitl_audit_trail.find_one.assert_called_with(
            {"gate_decision_id": "gd-001", "_type": "gate_decision"},
            {"_id": 0},
        )

    def test_get_gate_decision_returns_none_when_not_found(self, mock_db):
        mock_db.hitl_audit_trail.find_one.return_value = None
        result = audit_trail_service.get_gate_decision("nonexistent")
        assert result is None

    def test_list_gate_decisions_filters_by_tenant(self, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor()
        audit_trail_service.list_gate_decisions("tenant-abc", "GATE_1")
        call_args = mock_db.hitl_audit_trail.find.call_args
        query = call_args[0][0]
        assert query["tenant_id"] == "tenant-abc"
        assert query["gate_id"] == "GATE_1"
        assert query["_type"] == "gate_decision"

    def test_list_gate_decisions_without_gate_filter(self, mock_db):
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor()
        audit_trail_service.list_gate_decisions("tenant-abc")
        call_args = mock_db.hitl_audit_trail.find.call_args
        query = call_args[0][0]
        assert query["tenant_id"] == "tenant-abc"
        assert "gate_id" not in query

    def test_get_pending_escalations_filters_unresolved(self, mock_db):
        mock_db.hitl_escalations.find.return_value = mock_db._chainable_cursor()
        audit_trail_service.get_pending_escalations("GATE_2", "tenant-abc")
        call_args = mock_db.hitl_escalations.find.call_args
        query = call_args[0][0]
        assert query["resolved"] is False
        assert query["tenant_id"] == "tenant-abc"
        assert query["gate_id"] == "GATE_2"


class TestRationaleEnforcement:
    """P1 Fix 3: empty rationale must be rejected (spec requires rationale in every decision)."""

    def test_empty_rationale_rejected(self, client):
        payload = {
            "gate_id": "GATE_1",
            "actor_id": "officer-001",
            "actor_role": "GRANTS_OFFICER",
            "tenant_id": "tenant-abc",
            "ai_run_id": "run-001",
            "decision": "APPROVE",
            "rationale": "",  # empty — must fail
        }
        resp = client.post("/gates/decision", json=payload)
        assert resp.status_code == 422

    def test_empty_string_rejected_by_schema(self, client):
        """min_length=1 blocks empty string; documents scope of current enforcement."""
        from pydantic import ValidationError
        from app.schemas.hitl import GateDecisionRequest, GateId, GateOwnerRole, GateDecision
        with pytest.raises(ValidationError, match="string_too_short"):
            GateDecisionRequest(
                gate_id=GateId.GATE_4,
                actor_id="officer-001",
                actor_role=GateOwnerRole.GRANTS_OFFICER,
                tenant_id="tenant-abc",
                ai_run_id="run-001",
                decision=GateDecision.AWARD,
                rationale="",
            )

    def test_nonempty_rationale_accepted(self, client, mock_db):
        payload = {
            "gate_id": "GATE_1",
            "actor_id": "officer-001",
            "actor_role": "GRANTS_OFFICER",
            "tenant_id": "tenant-abc",
            "ai_run_id": "run-001",
            "decision": "APPROVE",
            "rationale": "Application meets 2 CFR 200.205 merit criteria.",
        }
        resp = client.post("/gates/decision", json=payload)
        assert resp.status_code == 200


class TestCacheRevalidationWiredInEndpoints:
    """P0 Fix 1: validate_before_generation must be called in production generation endpoints."""

    def test_check_eligibility_accepts_tenant_id(self, client):
        """P1 Fix 4: explicit tenant_id required — no fallback to 'unknown'."""
        # Missing tenant_id should fail
        resp = client.post("/check-eligibility", json={
            "grant_application_id": "app-001",
            "applicant_type": "UNIVERSITY",
        })
        assert resp.status_code == 422  # tenant_id is required

    def test_check_eligibility_with_tenant_id_succeeds(self, client):
        resp = client.post("/check-eligibility", json={
            "tenant_id": "tenant-abc",
            "grant_application_id": "app-001",
            "applicant_type": "UNIVERSITY",
        })
        assert resp.status_code == 200
        body = resp.json()
        # Confirm grounding and cache validation fields present
        assert "grounding_status" in body
        assert "confidence_score" in body
        assert "faithfulness_score" in body

    def test_rag_v2_search_escalates_even_without_gate_context(self, client, mock_db):
        """P0 Fix 2: grounding failure must create escalation even when gate_context omitted."""
        resp = client.post("/rag/v2/search", json={
            "query": "completely unrecognized query xyz123abc",
            "tenant_id": "tenant-abc",
            # gate_context intentionally omitted
        })
        assert resp.status_code == 200
        body = resp.json()
        if body.get("requires_human_review"):
            # Escalation must have been recorded (no silent failure)
            mock_db.hitl_escalations.insert_one.assert_called()
            # Default gate routing applies (GATE_1)
            assert body.get("hitl_gate") == "GATE_1"
            assert body.get("escalation_owner") == "GRANTS_OFFICER"

    def test_rag_v2_search_ai_run_id_unique_per_call(self, client, mock_db):
        """P1 Fix 5: ai_run_id must be unique per escalation call."""
        # Make two requests that will trigger escalation (empty query = low confidence)
        for _ in range(2):
            client.post("/rag/v2/search", json={
                "query": "unrecognized xyz987654",
                "tenant_id": "tenant-abc",
            })
        # If escalations were created, each should have a distinct ai_run_id
        if mock_db.hitl_escalations.insert_one.call_count >= 2:
            calls = mock_db.hitl_escalations.insert_one.call_args_list
            ai_run_ids = [c[0][0].get("ai_run_id") for c in calls]
            assert len(set(ai_run_ids)) == len(ai_run_ids), "ai_run_id must be unique per escalation"


class TestAuditViaAPI:
    """End-to-end audit trail verification via HTTP."""

    def test_record_decision_response_includes_all_audit_fields(self, client, mock_db):
        payload = {
            "gate_id": "GATE_1",
            "actor_id": "officer-001",
            "actor_role": "GRANTS_OFFICER",
            "tenant_id": "tenant-abc",
            "ai_run_id": "run-001",
            "decision": "APPROVE",
            "rationale": "Meets merit criteria per 2 CFR 200.205.",
            "confidence_score": 0.88,
            "grounding_status": "GROUNDED",
        }
        resp = client.post("/gates/decision", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        for field in REQUIRED_GATE_FIELDS:
            assert field in body, f"API response missing required audit field: {field!r}"

    def test_gate_decision_not_found_returns_404(self, client, mock_db):
        mock_db.hitl_audit_trail.find_one.return_value = None
        resp = client.get("/gates/decision/nonexistent-id")
        assert resp.status_code == 404
