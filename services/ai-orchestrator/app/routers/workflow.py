"""
Workflow HTTP endpoints.

POST /workflow/start   — start a new workflow run (triage → Gate 1)
POST /workflow/resume  — resume after a gate decision
GET  /workflow/{id}/status — current state + next interrupt info
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

log = logging.getLogger("ai-orchestrator.workflow.router")

router = APIRouter(prefix="/workflow", tags=["agentic-workflow"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class WorkflowStartRequest(BaseModel):
    """
    Start a new workflow run.
    tenant_id must match the authenticated principal (enforced here for now;
    full auth-principal wiring is an open item in agentic-workflow/README.md).
    """
    tenant_id: str
    grant_application_id: str
    raw_text: Optional[str] = None
    proposal_id: Optional[str] = None
    applicant_type: Optional[str] = None
    applicant_uei: Optional[str] = None
    applicant_org: Optional[str] = None
    pi_name: Optional[str] = None
    assistance_listing_number: Optional[str] = None
    requested_amount_federal: Optional[float] = None
    topic: Optional[str] = None
    constraints: Optional[str] = None
    corpus_version: str = "v1"


class WorkflowResumeRequest(BaseModel):
    """
    Resume a paused workflow by providing the gate decision.
    gate_decision must be a valid GateDecision enum value for the active gate.
    actor_id and actor_role are recorded in the audit trail.
    """
    workflow_run_id: str
    gate_decision: str      # GateDecision value e.g. "APPROVE", "AWARD"
    actor_id: str
    actor_role: str         # GateOwnerRole value
    rationale: str
    override_flag: bool = False


class WorkflowResponse(BaseModel):
    workflow_run_id: str
    status: str             # "RUNNING" | "PAUSED_AT_GATE" | "COMPLETED" | "DENIED" | "ERROR"
    current_stage: Optional[str] = None
    active_gate_id: Optional[str] = None
    pending_interrupt: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_config(workflow_run_id: str) -> dict:
    return {"configurable": {"thread_id": workflow_run_id}}


def _build_response(workflow_run_id: str, snapshot_info: Optional[dict]) -> WorkflowResponse:
    if snapshot_info is None:
        return WorkflowResponse(
            workflow_run_id=workflow_run_id,
            status="ERROR",
            message="Workflow state not found",
        )

    state = snapshot_info.get("state", {})
    is_paused = snapshot_info.get("is_paused", False)
    pending_interrupts = snapshot_info.get("pending_interrupts", [])
    completed = state.get("completed", False)
    denial_reason = state.get("denial_reason")

    if completed:
        status = "COMPLETED"
    elif denial_reason:
        status = "DENIED"
    elif is_paused:
        status = "PAUSED_AT_GATE"
    else:
        status = "RUNNING"

    active_gate_id = state.get("active_gate_id")
    if not active_gate_id and pending_interrupts:
        active_gate_id = pending_interrupts[0].get("hitl_gate")

    return WorkflowResponse(
        workflow_run_id=workflow_run_id,
        status=status,
        current_stage=state.get("current_stage"),
        active_gate_id=active_gate_id,
        pending_interrupt=pending_interrupts[0] if pending_interrupts else None,
        message=denial_reason,
    )


def _validate_gate_decision(gate_decision: str, active_gate_id: Optional[str]) -> None:
    from app.schemas.hitl import GateId, GATE_ALLOWED_DECISIONS, GateDecision
    if not active_gate_id:
        raise HTTPException(422, "No active gate to resume")
    try:
        gate = GateId(active_gate_id)
        decision = GateDecision(gate_decision)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    allowed = GATE_ALLOWED_DECISIONS.get(gate, [])
    if decision not in allowed:
        raise HTTPException(
            422,
            f"Decision {gate_decision!r} not allowed for {active_gate_id}. "
            f"Allowed: {[d.value for d in allowed]}",
        )


def _apply_supervisor_override(workflow_run_id: str, denial: str, state: dict) -> None:
    """
    Reset denial state and reposition graph at the capped gate node so that
    resume can apply the supervisor's gate decision.

    Requires LangGraph graph.update_state() which writes to the checkpoint
    as if a specific node just executed — route_gate_N then re-evaluates.
    """
    from app.workflow.graph import get_graph

    if "Gate 1" in denial:
        gate_id = "GATE_1"
        as_node = "eligibility"
    elif "Gate 3" in denial:
        gate_id = "GATE_3"
        as_node = "factor_suggest"
    else:
        raise HTTPException(422, f"Cannot determine override target gate from denial: {denial!r}")

    config = _run_config(workflow_run_id)
    graph = get_graph()
    try:
        graph.update_state(
            config,
            {
                "denial_reason": None,
                "completed": False,
                "revision_loop_counts": {},
                "active_gate_id": gate_id,
            },
            as_node=as_node,
        )
        log.info(
            "supervisor_override applied run=%s gate=%s reset_node=%s",
            workflow_run_id, gate_id, as_node,
        )
    except Exception as exc:
        raise HTTPException(500, f"Supervisor override state update failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=WorkflowResponse)
def start_workflow(
    req: WorkflowStartRequest,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> WorkflowResponse:
    """
    Start a new agentic workflow: triage → eligibility check → Gate 1 interrupt.
    Returns immediately with PAUSED_AT_GATE when Gate 1 is reached.

    X-Tenant-Id header (set by API Gateway from JWT claims): when present,
    must match req.tenant_id. Full auth-principal wiring is a tracked open item
    (agentic-workflow/README.md); this is the enforcement shim until then.
    """
    from langgraph.types import Command
    from app.workflow.graph import get_graph, get_workflow_state
    from app.workflow.state import make_initial_state

    if x_tenant_id and x_tenant_id != req.tenant_id:
        raise HTTPException(
            403,
            f"tenant_id body mismatch with X-Tenant-Id header "
            f"({req.tenant_id!r} vs {x_tenant_id!r}). "
            "Use the tenant from the authenticated session.",
        )

    initial_state = make_initial_state(
        tenant_id=req.tenant_id,
        grant_application_id=req.grant_application_id,
        raw_text=req.raw_text,
        proposal_id=req.proposal_id,
        applicant_type=req.applicant_type,
        applicant_uei=req.applicant_uei,
        applicant_org=req.applicant_org,
        pi_name=req.pi_name,
        assistance_listing_number=req.assistance_listing_number,
        requested_amount_federal=req.requested_amount_federal,
        topic=req.topic,
        constraints=req.constraints,
        corpus_version=req.corpus_version,
    )

    workflow_run_id = initial_state["workflow_run_id"]
    config = _run_config(workflow_run_id)
    graph = get_graph()

    try:
        graph.invoke(initial_state, config=config)
    except Exception as exc:
        # Graph may raise on interrupt in some LangGraph versions; state is checkpointed
        log.info("workflow invoke stopped (interrupt or completion): %s", exc)

    snapshot = get_workflow_state(workflow_run_id)
    response = _build_response(workflow_run_id, snapshot)
    log.info(
        "workflow started run=%s status=%s gate=%s",
        workflow_run_id, response.status, response.active_gate_id,
    )
    return response


@router.post("/resume", response_model=WorkflowResponse)
def resume_workflow(req: WorkflowResumeRequest) -> WorkflowResponse:
    """
    Resume a paused workflow after a human gate decision.
    Records the gate decision in the audit trail, then continues the graph.
    """
    from langgraph.types import Command
    from app.workflow.graph import get_graph, get_workflow_state
    from app.schemas.hitl import GateDecisionRequest, GateId, GateOwnerRole
    from app.services.gate_enforcer import gate_enforcer

    # Get current state to validate gate
    snapshot = get_workflow_state(req.workflow_run_id)
    if snapshot is None:
        raise HTTPException(404, f"Workflow {req.workflow_run_id!r} not found")

    state = snapshot.get("state", {})
    denial = state.get("denial_reason", "") or ""
    is_cap_exceeded = "cap exceeded" in denial

    if (state.get("completed") or denial) and not (req.override_flag and is_cap_exceeded):
        raise HTTPException(422, "Workflow already completed or denied; cannot resume")

    # Supervisor override: cap-exceeded + override_flag=True → reset and re-run the gate
    if req.override_flag and is_cap_exceeded:
        _apply_supervisor_override(req.workflow_run_id, denial, state)
        # Re-fetch state after override update
        snapshot = get_workflow_state(req.workflow_run_id)
        if snapshot is None:
            raise HTTPException(500, "Override state update lost; retry")
        state = snapshot.get("state", {})
        active_gate_id = state.get("active_gate_id")
        if not active_gate_id:
            pending_list = snapshot.get("pending_interrupts") or []
            if pending_list:
                active_gate_id = pending_list[0].get("hitl_gate")

    # active_gate_id may not be in state (set by preceding node, not interrupting node)
    # Fall back to the hitl_gate field in the interrupt payload
    active_gate_id = state.get("active_gate_id")
    if not active_gate_id:
        pending_list = snapshot.get("pending_interrupts") or []
        if pending_list:
            active_gate_id = pending_list[0].get("hitl_gate")
    _validate_gate_decision(req.gate_decision, active_gate_id)

    # Record gate decision in audit trail
    # Prefer ai_run_id from interrupt payload (most recent AI run for this gate)
    from app.schemas.hitl import GateDecision, GroundingStatus
    pending = (snapshot.get("pending_interrupts") or [{}])[0]
    ai_run_id = (
        pending.get("ai_run_id")
        or (state.get("ai_run_ids") or {}).get(active_gate_id or "", "")
        or str(__import__("uuid").uuid4())
    )
    try:
        decision_enum = GateDecision(req.gate_decision)
    except ValueError as exc:
        raise HTTPException(422, f"Invalid gate_decision: {exc}")
    try:
        gate_enforcer.record_decision(GateDecisionRequest(
            gate_id=GateId(active_gate_id),
            actor_id=req.actor_id,
            actor_role=GateOwnerRole(req.actor_role),
            tenant_id=state["tenant_id"],
            ai_run_id=ai_run_id,
            decision=decision_enum,
            rationale=req.rationale,
            override_flag=req.override_flag,
            confidence_score=float(pending.get("confidence_score", 0.0)),
            grounding_status=GroundingStatus(
                pending.get("grounding_status", "UNGROUNDED")
            ),
        ))
    except Exception as audit_exc:
        # Audit write failed (e.g. Mongo outage) — log for replay but do NOT block workflow.
        # Gate decision is still applied via LangGraph state; human operator must replay audit.
        log.error(
            "audit_write_failed run=%s gate=%s decision=%s ai_run=%s error=%s "
            "— workflow will continue; audit record requires manual replay",
            req.workflow_run_id, active_gate_id, req.gate_decision, ai_run_id, audit_exc,
        )

    # Resume LangGraph execution
    config = _run_config(req.workflow_run_id)
    graph = get_graph()
    try:
        graph.invoke(Command(resume=req.gate_decision), config=config)
    except Exception as exc:
        log.info("workflow resume stopped (interrupt or completion): %s", exc)

    snapshot = get_workflow_state(req.workflow_run_id)
    response = _build_response(req.workflow_run_id, snapshot)
    log.info(
        "workflow resumed run=%s decision=%s status=%s next_gate=%s",
        req.workflow_run_id, req.gate_decision, response.status, response.active_gate_id,
    )
    return response


@router.get("/{workflow_run_id}/status", response_model=WorkflowResponse)
def workflow_status(workflow_run_id: str) -> WorkflowResponse:
    """Return current workflow status without advancing execution."""
    from app.workflow.graph import get_workflow_state
    snapshot = get_workflow_state(workflow_run_id)
    if snapshot is None:
        raise HTTPException(404, f"Workflow {workflow_run_id!r} not found")
    return _build_response(workflow_run_id, snapshot)
