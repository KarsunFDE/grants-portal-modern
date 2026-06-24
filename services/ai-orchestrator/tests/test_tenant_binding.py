"""
Tenant binding tests — hitl-plan.txt §Tenant Binding Invariant + AC8 + AC12.

AC8:  Tenant boundaries enforced in logs and gate evidence.
AC12: evidence_ref tenant_id must equal gate decision tenant_id.
"""
from __future__ import annotations

import pytest

from app.schemas.hitl import (
    EvidenceRef,
    GateDecision,
    GateDecisionRecord,
    GateDecisionRequest,
    GateId,
    GateOwnerRole,
    GroundingStatus,
)
from app.services.gate_enforcer import gate_enforcer


class TestTenantBindingInvariant:
    """AC12: every evidence_ref.tenant_id must equal gate decision tenant_id."""

    def test_matching_tenant_ids_allowed(self, mock_db):
        req = GateDecisionRequest(
            gate_id=GateId.GATE_1,
            actor_id="officer-001",
            actor_role=GateOwnerRole.GRANTS_OFFICER,
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            decision=GateDecision.APPROVE,
            rationale="Approved.",
            evidence_refs=[
                EvidenceRef(chunk_id="c1", source_id="s1", tenant_id="tenant-abc"),
            ],
        )
        record = gate_enforcer.record_decision(req)
        assert record.gate_decision_id is not None
        assert record.tenant_id == "tenant-abc"

    def test_mismatched_tenant_id_raises(self):
        """GateDecisionRecord model_validator catches mismatched tenant_id."""
        with pytest.raises(ValueError, match="Tenant binding violation"):
            GateDecisionRecord(
                gate_id=GateId.GATE_1,
                workflow_stage="SCREENING",
                actor_id="officer-001",
                actor_role=GateOwnerRole.GRANTS_OFFICER,
                tenant_id="tenant-abc",
                ai_run_id="run-001",
                decision=GateDecision.APPROVE,
                rationale="Approved.",
                evidence_refs=[
                    EvidenceRef(chunk_id="c1", source_id="s1", tenant_id="tenant-DIFFERENT"),
                ],
            )

    def test_mismatched_evidence_ref_rejected_by_gate_enforcer(self, mock_db):
        req = GateDecisionRequest(
            gate_id=GateId.GATE_1,
            actor_id="officer-001",
            actor_role=GateOwnerRole.GRANTS_OFFICER,
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            decision=GateDecision.APPROVE,
            rationale="Approved.",
            evidence_refs=[
                EvidenceRef(chunk_id="c1", source_id="s1", tenant_id="tenant-WRONG"),
            ],
        )
        with pytest.raises(ValueError, match="Tenant binding violation"):
            gate_enforcer.record_decision(req)

    def test_multiple_evidence_refs_all_must_match(self, mock_db):
        """If any evidence_ref has a different tenant_id, the decision is rejected."""
        req = GateDecisionRequest(
            gate_id=GateId.GATE_1,
            actor_id="officer-001",
            actor_role=GateOwnerRole.GRANTS_OFFICER,
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            decision=GateDecision.APPROVE,
            rationale="Approved.",
            evidence_refs=[
                EvidenceRef(chunk_id="c1", source_id="s1", tenant_id="tenant-abc"),
                EvidenceRef(chunk_id="c2", source_id="s2", tenant_id="tenant-OTHER"),  # mismatch
            ],
        )
        with pytest.raises(ValueError, match="Tenant binding violation"):
            gate_enforcer.record_decision(req)

    def test_no_evidence_refs_allowed(self, mock_db):
        """No evidence_refs = no tenant binding to check — should succeed."""
        req = GateDecisionRequest(
            gate_id=GateId.GATE_1,
            actor_id="officer-001",
            actor_role=GateOwnerRole.GRANTS_OFFICER,
            tenant_id="tenant-abc",
            ai_run_id="run-001",
            decision=GateDecision.APPROVE,
            rationale="No evidence refs provided.",
            evidence_refs=[],
        )
        record = gate_enforcer.record_decision(req)
        assert record is not None

    def test_gate_decision_record_validator_catches_mismatch(self):
        with pytest.raises(ValueError, match="Tenant binding violation"):
            GateDecisionRecord(
                gate_id=GateId.GATE_4,
                workflow_stage="AWARD",
                actor_id="officer-001",
                actor_role=GateOwnerRole.GRANTS_OFFICER,
                tenant_id="tenant-good",
                ai_run_id="run-001",
                decision=GateDecision.AWARD,
                rationale="Award granted.",
                evidence_refs=[
                    EvidenceRef(chunk_id="c1", source_id="s1", tenant_id="tenant-bad"),
                ],
            )


class TestTenantIsolationViaAPI:
    """AC8: Tenant boundaries enforced via API — no cross-tenant leakage."""

    def test_gate_decisions_list_filters_by_tenant(self, client, mock_db):
        mock_db.hitl_audit_trail.find.return_value = iter([
            {
                "gate_decision_id": "gd-001",
                "gate_id": "GATE_1",
                "tenant_id": "tenant-abc",
                "decision": "APPROVE",
                "actor_id": "officer-001",
            }
        ])
        mock_db.hitl_audit_trail.find.return_value = mock_db._chainable_cursor([
            {
                "gate_decision_id": "gd-001",
                "gate_id": "GATE_1",
                "tenant_id": "tenant-abc",
                "decision": "APPROVE",
                "actor_id": "officer-001",
            }
        ])
        resp = client.get("/gates/decisions?tenant_id=tenant-abc")
        assert resp.status_code == 200
        # The find call must include tenant_id filter
        call_args = mock_db.hitl_audit_trail.find.call_args
        query = call_args[0][0]
        assert query.get("tenant_id") == "tenant-abc"

    def test_pending_escalations_filter_by_tenant(self, client, mock_db):
        mock_db.hitl_escalations.find.return_value = mock_db._chainable_cursor()
        resp = client.get("/gates/GATE_1/pending-escalations?tenant_id=tenant-abc")
        assert resp.status_code == 200
        call_args = mock_db.hitl_escalations.find.call_args
        query = call_args[0][0]
        assert query.get("tenant_id") == "tenant-abc"
