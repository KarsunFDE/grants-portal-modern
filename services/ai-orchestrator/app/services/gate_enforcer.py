"""
Gate enforcer — hitl-plan.txt §HITL Gates.

Rules enforced:
  Gate 1: No application past Screening without human decision + rationale.
  Gate 2: No scoring starts until COI is resolved by a human.
  Gate 3: AI suggestions require human acceptance before use in scoring narrative.
  Gate 4: No unattended award path; award must have persisted human approval + rationale.

Escalation routing: named gate owner required; no silent retries.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.schemas.hitl import (
    EscalationRecord,
    GateDecision,
    GateDecisionRecord,
    GateDecisionRequest,
    GateId,
    GateOwnerRole,
    GATE_ALLOWED_DECISIONS,
    GATE_BLOCKING_DECISIONS,
    GATE_OWNER_ROLES,
    GATE_WORKFLOW_STAGE,
    GroundingStatus,
    HumanReviewReason,
)
from app.services.audit_trail import audit_trail_service

log = logging.getLogger("ai-orchestrator.gate")


class GateEnforcer:
    # ------------------------------------------------------------------
    # Decision recording
    # ------------------------------------------------------------------

    def record_decision(self, request: GateDecisionRequest) -> GateDecisionRecord:
        """
        Validate and persist a human gate decision.
        Raises ValueError on: wrong role, wrong decision, tenant binding violation.
        """
        self._validate_or_raise(request)

        record = GateDecisionRecord(
            gate_id=request.gate_id,
            workflow_stage=GATE_WORKFLOW_STAGE[request.gate_id],
            actor_id=request.actor_id,
            actor_role=request.actor_role,
            tenant_id=request.tenant_id,
            ai_run_id=request.ai_run_id,
            decision=request.decision,
            rationale=request.rationale,
            override_flag=request.override_flag,
            evidence_refs=request.evidence_refs,
            retrieved_sources=request.retrieved_sources,
            citation_refs=request.citation_refs,
            confidence_score=request.confidence_score,
            grounding_status=request.grounding_status,
        )

        audit_trail_service.record_gate_decision(record)
        log.info("Gate %s cleared by %s (%s)", request.gate_id.value, request.actor_id, request.decision.value)
        return record

    # ------------------------------------------------------------------
    # Gate cleared check
    # ------------------------------------------------------------------

    def check_gate_cleared(
        self,
        gate_id: GateId,
        tenant_id: str,
        ai_run_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check whether a gate has a passing human decision for this ai_run_id.
        Returns (cleared, reason_if_not_cleared).
        """
        decisions = audit_trail_service.list_gate_decisions(tenant_id, gate_id.value)
        matching = [d for d in decisions if d.get("ai_run_id") == ai_run_id]

        if not matching:
            owners = GATE_OWNER_ROLES.get(gate_id, [])
            owner_str = ", ".join(r.value for r in owners)
            return False, (
                f"{gate_id.value} requires a human decision from {owner_str}. "
                f"No decision recorded for ai_run_id={ai_run_id!r}."
            )

        latest_decision = matching[0].get("decision")
        blocking = [d.value for d in GATE_BLOCKING_DECISIONS.get(gate_id, [])]
        if latest_decision in blocking:
            return False, f"{gate_id.value} decision {latest_decision!r} blocks workflow from advancing."

        return True, None

    # ------------------------------------------------------------------
    # Escalation (no silent retries)
    # ------------------------------------------------------------------

    def create_escalation(
        self,
        gate_id: GateId,
        tenant_id: str,
        ai_run_id: str,
        human_review_reasons: List[HumanReviewReason],
        grounding_status: GroundingStatus,
        confidence_score: float,
    ) -> EscalationRecord:
        owners = GATE_OWNER_ROLES.get(gate_id, [])
        reason = _build_escalation_reason(human_review_reasons, grounding_status)
        record = EscalationRecord(
            gate_id=gate_id,
            gate_owner_roles=owners,
            tenant_id=tenant_id,
            ai_run_id=ai_run_id,
            reason=reason,
            human_review_reasons=human_review_reasons,
            grounding_status=grounding_status,
            confidence_score=confidence_score,
        )
        audit_trail_service.record_escalation(record)
        return record

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_or_raise(self, request: GateDecisionRequest) -> None:
        # Allowed decision for this gate
        allowed = GATE_ALLOWED_DECISIONS.get(request.gate_id, [])
        if request.decision not in allowed:
            raise ValueError(
                f"Decision {request.decision.value!r} not allowed for {request.gate_id.value}. "
                f"Allowed: {[d.value for d in allowed]}"
            )

        # Authorized actor role
        authorized = GATE_OWNER_ROLES.get(request.gate_id, [])
        if request.actor_role not in authorized:
            raise ValueError(
                f"Role {request.actor_role.value!r} not authorized for {request.gate_id.value}. "
                f"Authorized roles: {[r.value for r in authorized]}"
            )

        # Tenant binding (hitl-plan.txt §Tenant Binding Invariant)
        for ref in request.evidence_refs:
            if ref.tenant_id != request.tenant_id:
                raise ValueError(
                    f"Tenant binding violation: evidence_ref {ref.evidence_id!r} "
                    f"tenant_id={ref.tenant_id!r} != gate tenant_id={request.tenant_id!r}"
                )


def _build_escalation_reason(
    reasons: List[HumanReviewReason],
    grounding_status: GroundingStatus,
) -> str:
    parts = [f"grounding_status={grounding_status.value}"]
    parts.extend(r.value for r in reasons)
    return "; ".join(parts)


gate_enforcer = GateEnforcer()
