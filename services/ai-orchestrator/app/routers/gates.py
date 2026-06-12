"""
Gate decision endpoints — POST /gates/decision, GET /gates/{gate_id}/cleared, etc.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.hitl import GateDecisionRecord, GateDecisionRequest, GateId
from app.services.audit_trail import audit_trail_service
from app.services.gate_enforcer import gate_enforcer

router = APIRouter(prefix="/gates", tags=["hitl-gates"])


@router.post("/decision", response_model=GateDecisionRecord)
def record_gate_decision(request: GateDecisionRequest) -> GateDecisionRecord:
    """
    Record a human gate decision.
    Validates: actor role authorized for gate, decision allowed for gate,
    tenant binding on all evidence_refs, rationale present.
    Persists to append-only audit trail.
    """
    try:
        return gate_enforcer.record_decision(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/decision/{gate_decision_id}")
def get_gate_decision(gate_decision_id: str) -> dict:
    """Fetch a single gate decision record from the audit trail."""
    record = audit_trail_service.get_gate_decision(gate_decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Gate decision not found")
    return record


@router.get("/decisions")
def list_gate_decisions(
    tenant_id: str = Query(..., description="Tenant to query"),
    gate_id: Optional[str] = Query(None, description="Filter by gate ID"),
) -> list:
    """List gate decisions for a tenant, most recent first."""
    return audit_trail_service.list_gate_decisions(tenant_id, gate_id)


@router.get("/{gate_id}/cleared")
def check_gate_cleared(
    gate_id: str,
    tenant_id: str = Query(...),
    ai_run_id: str = Query(...),
) -> dict:
    """
    Check if a gate has been cleared by a human decision for this ai_run_id.
    Returns {cleared: bool, reason: str|null}.
    """
    try:
        gate = GateId(gate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown gate_id: {gate_id!r}")
    cleared, reason = gate_enforcer.check_gate_cleared(gate, tenant_id, ai_run_id)
    return {"gate_id": gate_id, "cleared": cleared, "reason": reason}


@router.get("/{gate_id}/pending-escalations")
def get_pending_escalations(
    gate_id: str,
    tenant_id: str = Query(...),
) -> list:
    """Return unresolved escalations for a gate + tenant."""
    return audit_trail_service.get_pending_escalations(gate_id, tenant_id)
