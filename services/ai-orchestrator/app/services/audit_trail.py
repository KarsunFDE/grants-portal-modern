"""
Append-only audit trail — hitl-plan.txt §Audit and Durability Requirements.

Required fields per gate decision: actor_id, actor_role, tenant_id, timestamp,
workflow_stage, gate_id, ai_run_id, decision, rationale, override_flag,
evidence_refs, retrieved_sources, citation_refs, confidence_score, grounding_status.

Durability: logs survive restart (MongoDB persisted volume), support multi-day
pause/resume, OIG reconstructible from logs alone, no cross-tenant leakage.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.db import get_db
from app.schemas.hitl import EscalationRecord, GateDecisionRecord

log = logging.getLogger("ai-orchestrator.audit")


class AuditTrailService:
    def record_gate_decision(self, record: GateDecisionRecord) -> str:
        """
        Write gate decision to append-only hitl_audit_trail collection.
        Never updates — always inserts a new document.
        Returns gate_decision_id.
        """
        db = get_db()
        doc = record.model_dump(mode="json")
        doc["_type"] = "gate_decision"
        db.hitl_audit_trail.insert_one(doc)
        log.info(
            "gate_decision recorded gate=%s decision=%s actor=%s tenant=%s id=%s",
            record.gate_id.value,
            record.decision.value,
            record.actor_id,
            record.tenant_id,
            record.gate_decision_id,
        )
        return record.gate_decision_id

    def record_escalation(self, record: EscalationRecord) -> str:
        """
        Write escalation to audit trail AND dedicated hitl_escalations collection.
        Returns escalation_id. No silent retries — every failure creates a record.
        """
        db = get_db()
        doc = record.model_dump(mode="json")
        doc["_type"] = "escalation"
        db.hitl_audit_trail.insert_one(dict(doc))
        db.hitl_escalations.insert_one(dict(doc))
        log.info(
            "escalation recorded gate=%s tenant=%s reasons=%s id=%s",
            record.gate_id.value,
            record.tenant_id,
            [r.value for r in record.human_review_reasons],
            record.escalation_id,
        )
        return record.escalation_id

    def get_gate_decision(self, gate_decision_id: str) -> Optional[dict]:
        db = get_db()
        return db.hitl_audit_trail.find_one(
            {"gate_decision_id": gate_decision_id, "_type": "gate_decision"},
            {"_id": 0},
        )

    def list_gate_decisions(
        self,
        tenant_id: str,
        gate_id: Optional[str] = None,
    ) -> List[dict]:
        db = get_db()
        query: dict = {"_type": "gate_decision", "tenant_id": tenant_id}
        if gate_id:
            query["gate_id"] = gate_id
        return list(
            db.hitl_audit_trail.find(query, {"_id": 0}).sort("timestamp", -1).limit(100)
        )

    def get_pending_escalations(self, gate_id: str, tenant_id: str) -> List[dict]:
        db = get_db()
        return list(
            db.hitl_escalations.find(
                {"gate_id": gate_id, "tenant_id": tenant_id, "resolved": False},
                {"_id": 0},
            )
        )


audit_trail_service = AuditTrailService()
