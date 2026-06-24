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
from pymongo import ReturnDocument

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

    if denial_reason:
        # Check denial_reason BEFORE completed: both can be set simultaneously
        # (e.g. REJECT path sets completed=True AND denial_reason). Denial wins.
        status = "DENIED"
    elif completed:
        status = "COMPLETED"
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


def _acquire_resume_lock(workflow_run_id: str, active_gate_id: str) -> bool:
    """
    Atomic CAS via MongoDB upsert. Returns True if lock acquired (new doc).
    Returns False on DuplicateKeyError (concurrent resume) or any Mongo error.
    The resume_locks collection has a unique compound index on (workflow_run_id, active_gate_id).
    """
    try:
        from app.db import get_db
        db = get_db()
        prior = db.resume_locks.find_one_and_update(
            {"workflow_run_id": workflow_run_id, "active_gate_id": active_gate_id},
            {"$setOnInsert": {
                "workflow_run_id": workflow_run_id,
                "active_gate_id": active_gate_id,
            }},
            upsert=True,
            return_document=ReturnDocument.BEFORE,
        )
        return prior is None  # None → new insert → lock acquired; existing doc → already locked
    except Exception as exc:
        log.warning("resume_lock acquisition failed (%s) — rejecting to prevent double-advance", exc)
        return False


def _release_resume_lock(workflow_run_id: str, active_gate_id: str) -> None:
    """Delete the per-(run, gate) resume lock. Called in finally after resume completes or errors."""
    try:
        from app.db import get_db
        db = get_db()
        db.resume_locks.delete_one({
            "workflow_run_id": workflow_run_id,
            "active_gate_id": active_gate_id,
        })
    except Exception as exc:
        log.warning(
            "resume_lock release failed run=%s gate=%s: %s — "
            "lock document may persist; TTL index or manual cleanup required",
            workflow_run_id, active_gate_id, exc,
        )


def _apply_supervisor_override(workflow_run_id: str, denial: str, state: dict) -> None:
    """
    Reset denial state and reposition graph at the capped gate node so that
    resume can apply the supervisor's gate decision.

    Routes via structured terminal_gate_id from state (preferred) with substring
    fallback for legacy denial strings.
    """
    from app.workflow.graph import get_graph

    terminal_gate_id = state.get("terminal_gate_id") or ""
    if terminal_gate_id == "GATE_1" or "Gate 1" in denial:
        gate_id = "GATE_1"
        as_node = "eligibility"
    elif terminal_gate_id == "GATE_3" or "Gate 3" in denial:
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

    if not x_tenant_id:
        raise HTTPException(
            403,
            "X-Tenant-Id header required. In production, the API Gateway derives this from "
            "verified JWT claims. Requests without tenant context are rejected.",
        )
    if x_tenant_id != req.tenant_id:
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
    except ValueError as node_exc:
        # ValueError from a node (e.g. missing ai_run_id) is a real error — not a normal interrupt.
        # Raise 500 so callers are not silently handed a stale PAUSED_AT_GATE response.
        raise HTTPException(500, f"Workflow node error during start: {node_exc}") from node_exc
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
def resume_workflow(
    req: WorkflowResumeRequest,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> WorkflowResponse:
    """
    Resume a paused workflow after a human gate decision.
    Records the gate decision in the audit trail (hard precondition), then continues the graph.
    Requires X-Tenant-Id header matching the workflow's stored tenant.
    """
    from langgraph.types import Command
    from app.workflow.graph import get_graph, get_workflow_state
    from app.schemas.hitl import GateDecisionRequest, GateId, GateOwnerRole
    from app.services.gate_enforcer import gate_enforcer

    # Get current state to validate gate and tenant
    snapshot = get_workflow_state(req.workflow_run_id)
    if snapshot is None:
        raise HTTPException(404, f"Workflow {req.workflow_run_id!r} not found")

    state = snapshot.get("state", {})

    # Tenant check — X-Tenant-Id is required on every resume; absent header → 403.
    # In production the API Gateway sets this from JWT claims; frontend cannot forge it.
    # NOTE: actor_id/actor_role are currently taken from the request body (demo limitation).
    # TODO: derive both from authenticated principal claims once full auth wiring lands.
    stored_tenant = state.get("tenant_id", "")
    if not x_tenant_id:
        raise HTTPException(
            403,
            "X-Tenant-Id header required. In production, the API Gateway derives this from "
            "verified JWT claims. Requests without tenant context are rejected.",
        )
    if x_tenant_id != stored_tenant:
        raise HTTPException(
            403,
            f"X-Tenant-Id {x_tenant_id!r} does not match workflow tenant {stored_tenant!r}.",
        )

    denial = state.get("denial_reason", "") or ""
    is_cap_exceeded = "cap exceeded" in denial

    if (state.get("completed") or denial) and not (req.override_flag and is_cap_exceeded):
        raise HTTPException(422, "Workflow already completed or denied; cannot resume")

    # Supervisor override: cap-exceeded + override_flag=True → reset and re-run the gate
    if req.override_flag and is_cap_exceeded:
        _apply_supervisor_override(req.workflow_run_id, denial, state)
        snapshot = get_workflow_state(req.workflow_run_id)
        if snapshot is None:
            raise HTTPException(500, "Override state update lost; retry")
        state = snapshot.get("state", {})

    # Resolve active_gate_id from state or interrupt payload
    active_gate_id = state.get("active_gate_id")
    if not active_gate_id:
        pending_list = snapshot.get("pending_interrupts") or []
        if pending_list:
            active_gate_id = pending_list[0].get("hitl_gate")
    _validate_gate_decision(req.gate_decision, active_gate_id)

    # Acquire per-(run, gate) resume lock — prevents concurrent double-advance
    if not _acquire_resume_lock(req.workflow_run_id, active_gate_id or ""):
        raise HTTPException(
            409,
            f"Resume for workflow {req.workflow_run_id!r} gate {active_gate_id!r} "
            "already in progress — retry after the current resume completes.",
        )

    try:
        # Resolve ai_run_id — must be traceable to a real AI run; never fabricate
        from app.schemas.hitl import GateDecision, GroundingStatus
        pending = (snapshot.get("pending_interrupts") or [{}])[0]
        ai_run_id = (
            pending.get("ai_run_id")
            or (state.get("ai_run_ids") or {}).get(active_gate_id or "", "")
        )
        if not ai_run_id:
            raise HTTPException(
                422,
                f"Cannot resolve ai_run_id for gate {active_gate_id!r}: interrupt payload missing "
                "ai_run_id and no prior ai_run_ids entry. Resume aborted to preserve audit integrity.",
            )

        try:
            decision_enum = GateDecision(req.gate_decision)
        except ValueError as exc:
            raise HTTPException(422, f"Invalid gate_decision: {exc}")

        # Audit write is a hard precondition — validation errors (role/decision) → 403/422;
        # infrastructure errors → 503. Never advance the graph without a committed record.
        # Citation evidence from the pending interrupt is persisted so approvers' view is
        # reconstructible post-award (2 CFR 200.205 / ADR 0009 §10).
        try:
            gate_record = gate_enforcer.record_decision(GateDecisionRequest(
                gate_id=GateId(active_gate_id),
                actor_id=req.actor_id,
                actor_role=GateOwnerRole(req.actor_role),
                tenant_id=stored_tenant,
                ai_run_id=ai_run_id,
                decision=decision_enum,
                rationale=req.rationale,
                override_flag=req.override_flag,
                retrieved_sources=pending.get("retrieved_sources") or [],
                citation_refs=pending.get("citation_refs") or [],
                confidence_score=float(pending.get("confidence_score", 0.0)),
                grounding_status=GroundingStatus(
                    pending.get("grounding_status", "UNGROUNDED")
                ),
            ))
        except ValueError as exc:
            raise HTTPException(
                403,
                f"Gate decision rejected — role or decision not authorized: {exc}",
            )
        except Exception as audit_exc:
            raise HTTPException(
                503,
                f"Audit write failed; gate decision not recorded and graph not advanced. "
                f"Retry when storage is available. Detail: {audit_exc}",
            )

        config = _run_config(req.workflow_run_id)
        graph = get_graph()

        # Resume LangGraph execution — audit record committed above
        try:
            graph.invoke(Command(resume=req.gate_decision), config=config)
        except ValueError as node_exc:
            raise HTTPException(500, f"Workflow node error during resume: {node_exc}") from node_exc
        except Exception as exc:
            log.info("workflow resume stopped (interrupt or completion): %s", exc)

        # Append gate_decision_id AFTER successful graph advance — avoids orphan IDs
        # accumulating in state when graph.invoke fails and the client retries.
        # Idempotency guard: skip if already appended (retry safety).
        existing_ids = state.get("gate_decision_ids") or []
        if gate_record.gate_decision_id not in existing_ids:
            try:
                graph.update_state(
                    config,
                    {"gate_decision_ids": [*existing_ids, gate_record.gate_decision_id]},
                )
            except Exception as exc:
                log.warning(
                    "gate_decision_ids state update failed run=%s gate=%s: %s — "
                    "audit record committed; panel evidence linkage degraded",
                    req.workflow_run_id, active_gate_id, exc,
                )

    finally:
        _release_resume_lock(req.workflow_run_id, active_gate_id or "")

    snapshot = get_workflow_state(req.workflow_run_id)
    response = _build_response(req.workflow_run_id, snapshot)
    log.info(
        "workflow resumed run=%s decision=%s status=%s next_gate=%s",
        req.workflow_run_id, req.gate_decision, response.status, response.active_gate_id,
    )
    return response


@router.get("/{workflow_run_id}/status", response_model=WorkflowResponse)
def workflow_status(
    workflow_run_id: str,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
) -> WorkflowResponse:
    """Return current workflow status without advancing execution.
    X-Tenant-Id header (set by API Gateway from JWT) must match the workflow's tenant.
    """
    from app.workflow.graph import get_workflow_state
    snapshot = get_workflow_state(workflow_run_id)
    if snapshot is None:
        raise HTTPException(404, f"Workflow {workflow_run_id!r} not found")
    if not x_tenant_id:
        raise HTTPException(
            403,
            "X-Tenant-Id header required. Workflow state (including pending AI output) "
            "is tenant-scoped and must not be returned without verified tenant context.",
        )
    stored_tenant = snapshot.get("state", {}).get("tenant_id", "")
    if stored_tenant and x_tenant_id != stored_tenant:
        raise HTTPException(
            403,
            f"X-Tenant-Id {x_tenant_id!r} does not match workflow tenant.",
        )
    return _build_response(workflow_run_id, snapshot)
