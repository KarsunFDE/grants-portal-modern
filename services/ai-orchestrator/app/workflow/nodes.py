"""
LangGraph node functions and routing logic for the agentic grants workflow.

Node execution order (happy path):
  triage → eligibility ─[Gate 1 APPROVE]→ reviewer_assignment → coi_check
    → [Gate 2 RESOLVE]→ panel_confirmation → factor_suggest ─[Gate 3 ACCEPT]→
    ssdd_draft ─[Gate 4 AWARD]→ seal_audit → END

HITL interrupts fire at: eligibility (Gate 1), gate_2 (Gate 2),
  factor_suggest (Gate 3), ssdd_draft (Gate 4).

Each interrupted node is re-executed on resume; idempotency_store prevents
duplicate Bedrock calls (see orchestration.md §3 note on replay behaviour).
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from langgraph.types import interrupt

from app.bedrock_client import invoke_model, BEDROCK_MODEL_ID
from app.schemas.hitl import GateId, GateOwnerRole, GroundingStatus, HumanReviewReason
from app.services.grounding import (
    compute_grounding_status,
    is_grounded,
    should_advance,
)
from app.services.retrieval import retrieval_service
from app.services.cache_validator import validate_before_generation
from app.services.gate_enforcer import gate_enforcer
from app.workflow.agents import (
    ReviewerCandidate,
    run_coi_check,
    run_panel_confirmation,
    run_reviewer_assignment,
)
from app.workflow.idempotency import idempotency_store
from app.workflow.state import (
    WorkflowState,
    RevisionLoopCapExceeded,
    build_idempotency_key,
    increment_revision_loop,
    utc_now_iso,
)

log = logging.getLogger("ai-orchestrator.workflow")

PROMPT_TEMPLATE_VERSION = "v1"
_MAX_RAW_TEXT_LEN = 4000


def _safe_input(text: Optional[str], max_len: int = _MAX_RAW_TEXT_LEN) -> str:
    """Truncate user-supplied text before embedding in model prompts."""
    if not text:
        return "(none)"
    return text[:max_len]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grounded_retrieve(
    query: str,
    state: WorkflowState,
    gate_id: GateId,
    stage_key: str,
) -> tuple:
    """
    Retrieval + grounding for a stage.
    Returns (citations, conf, faith, grounding_status, reasons, should_block).
    """
    citations, conf, faith, retrieved_at = retrieval_service.retrieve(
        query=query,
        tenant_id=state["tenant_id"],
        corpus_version=state.get("corpus_version", "v1"),
    )
    grounding_status, reasons = compute_grounding_status(
        citations, conf, faith, gate_id=gate_id
    )
    cache_ok, cache_reasons = validate_before_generation(
        citations=citations,
        confidence_score=conf,
        faithfulness_score=faith,
        cache_created_at=retrieved_at,
        tenant_id=state["tenant_id"],
    )
    if not cache_ok:
        for r in cache_reasons:
            if r not in reasons:
                reasons.append(r)
        if is_grounded(grounding_status):
            grounding_status = GroundingStatus.UNGROUNDED

    should_block = not should_advance(grounding_status)
    return citations, conf, faith, grounding_status, reasons, should_block


def _create_escalation(
    state: WorkflowState,
    gate_id: GateId,
    reasons,
    grounding_status,
    confidence: float,
    ai_run_id: Optional[str] = None,
) -> str:
    if ai_run_id is None:
        ai_run_id = state.get("ai_run_ids", {}).get(gate_id.value) or str(uuid.uuid4())
    escalation = gate_enforcer.create_escalation(
        gate_id=gate_id,
        tenant_id=state["tenant_id"],
        ai_run_id=ai_run_id,
        human_review_reasons=reasons,
        grounding_status=grounding_status,
        confidence_score=confidence,
    )
    return escalation.escalation_id


def _bedrock_with_idempotency(
    prompt: str,
    system: str,
    state: WorkflowState,
    stage: str,
    gate_id: Optional[str],
    query: str,
) -> dict:
    """Bedrock call protected by idempotency key (prevents duplicate on LangGraph replay)."""
    attempt = (state.get("revision_loop_counts") or {}).get(gate_id or stage, 0)
    idem_key = build_idempotency_key(
        workflow_run_id=state["workflow_run_id"],
        stage=stage,
        gate_id=gate_id,
        attempt=attempt,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        corpus_version=state.get("corpus_version", "v1"),
        raw_text=state.get("raw_text") or "",
        query=query,
        tenant_id=state["tenant_id"],
    )
    cached = idempotency_store.get(idem_key)
    if cached:
        log.info("idempotency hit stage=%s gate=%s", stage, gate_id)
        return cached
    result = invoke_model(prompt, system=system)
    idempotency_store.set(idem_key, result)
    return result


# ---------------------------------------------------------------------------
# Node 1: triage
# ---------------------------------------------------------------------------

def triage_node(state: WorkflowState) -> dict:
    """
    Runs intake triage (multi-step Bedrock classification + routing + anomaly detection).
    No HITL interrupt — triage result feeds Gate 1 context.
    """
    log.info("triage_node workflow=%s", state["workflow_run_id"])
    proposal_id = state.get("proposal_id") or state["grant_application_id"]
    raw_text = _safe_input(state.get("raw_text")) or proposal_id

    classify = _bedrock_with_idempotency(
        prompt=f"Classify program area and complexity: {raw_text}",
        system="You classify federal grant applications for merit-review-panel routing.",
        state=state,
        stage="triage_classify",
        gate_id=None,
        query=raw_text,
    )
    route = _bedrock_with_idempotency(
        prompt=f"Recommend 3 peer reviewers for application_id={proposal_id}.",
        system="You route applications to peer-review-panel members based on subject expertise.",
        state=state,
        stage="triage_route",
        gate_id=None,
        query=proposal_id,
    )
    anomaly = _bedrock_with_idempotency(
        prompt=f"Flag anomalies in application_id={proposal_id} that warrant Program Officer escalation.",
        system="You flag anomalies (completeness, eligibility, conflict of interest).",
        state=state,
        stage="triage_anomaly",
        gate_id=None,
        query=proposal_id,
    )

    triage_result = {
        "proposal_id": proposal_id,
        "risk_tier": "STANDARD",
        "completeness_flag": "anomaly" not in anomaly.get("body", "").lower(),
        "flagged_issues": anomaly.get("body", ""),
        "classification": classify.get("body", ""),
        "routing": route.get("body", ""),
    }
    log.info("triage_node completed workflow=%s risk_tier=%s", state["workflow_run_id"], triage_result["risk_tier"])
    return {
        "triage_result": triage_result,
        "current_stage": "SCREENING",
        # Pre-set GATE_1 so checkpoint is correct before eligibility_node interrupts
        "active_gate_id": GateId.GATE_1.value,
        "sla_timers": {**state.get("sla_timers", {}), "GATE_1": utc_now_iso()},
    }


# ---------------------------------------------------------------------------
# Node 2: eligibility (Gate 1)
# ---------------------------------------------------------------------------

def eligibility_node(state: WorkflowState) -> dict:
    """
    Runs eligibility check, grounds against 2 CFR 200.205/206, then interrupts
    for Gate 1 (GRANTS_OFFICER / PROGRAM_OFFICER review).
    """
    log.info("eligibility_node workflow=%s", state["workflow_run_id"])
    query = (
        f"eligibility risk review applicant_type={state.get('applicant_type') or ''} "
        f"assistance_listing={state.get('assistance_listing_number') or ''}"
    )
    citations, conf, faith, grounding_status, reasons, should_block = _grounded_retrieve(
        query, state, GateId.GATE_1, "SCREENING"
    )

    ai_run_id = str(uuid.uuid4())
    ai_run_ids = {**state.get("ai_run_ids", {}), "SCREENING": ai_run_id}

    if should_block:
        esc_id = _create_escalation(state, GateId.GATE_1, reasons, grounding_status, conf, ai_run_id=ai_run_id)
        log.warning("eligibility_node BLOCKED grounding=%s", grounding_status.value)
        return {
            "active_gate_id": GateId.GATE_1.value,
            "gate_states": {**state.get("gate_states", {}), "GATE_1": "BLOCKED"},
            "pending_escalation_ids": [*state.get("pending_escalation_ids", []), esc_id],
            "ai_run_ids": ai_run_ids,
        }

    bedrock = _bedrock_with_idempotency(
        prompt=(
            f"Screen for eligibility and completeness. "
            f"Applicant type: {state.get('applicant_type') or '(unknown)'}; "
            f"Assistance Listing: {state.get('assistance_listing_number') or '(none)'}; "
            f"Federal request: {state.get('requested_amount_federal') or '(none)'}. "
            f"Context: {_safe_input(state.get('raw_text'))}. "
            f"Regulatory basis: {', '.join(c.source_id for c in citations)}."
        ),
        system=(
            "You screen federal grant applications for eligibility and completeness "
            "under 2 CFR 200.205-206; flag missing SF-424 items and ineligible "
            "applicant types. A Program Officer makes the final call."
        ),
        state=state,
        stage="SCREENING",
        gate_id=GateId.GATE_1.value,
        query=query,
    )

    # HITL interrupt — pauses graph; resumes when gate owner submits decision
    gate_decision: str = interrupt({
        "workflow_run_id": state["workflow_run_id"],
        "hitl_gate": "GATE_1",
        "ai_run_id": ai_run_id,
        "eligibility_output": bedrock.get("body", ""),
        "grounding_status": grounding_status.value,
        "confidence_score": conf,
        "faithfulness_score": faith,
        "human_review_reasons": [r.value for r in reasons],
        "retrieved_sources": [c.source_id for c in citations],
        "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
        "requires_human_review": True,
    })

    # Post-interrupt: process gate decision
    gate_states = {**state.get("gate_states", {}), "GATE_1": gate_decision}
    updated_counts = dict(state.get("revision_loop_counts", {}))
    if gate_decision == "RETURN_FOR_FIXES":
        try:
            updated_counts = increment_revision_loop(state, "GATE_1")
        except RevisionLoopCapExceeded as e:
            log.warning("Gate 1 revision cap exceeded: %s", e)
            esc_id = gate_enforcer.create_escalation(
                gate_id=GateId.GATE_1,
                tenant_id=state["tenant_id"],
                ai_run_id=ai_run_id,
                human_review_reasons=[HumanReviewReason.REVISION_LOOP_EXCEEDED],
                grounding_status=grounding_status,
                confidence_score=conf,
            ).escalation_id
            return {
                "gate_states": gate_states,
                "revision_loop_counts": updated_counts,
                "ai_run_ids": ai_run_ids,
                "pending_escalation_ids": [*state.get("pending_escalation_ids", []), esc_id],
                "active_gate_id": None,
                "completed": True,
                "denial_reason": "Gate 1 revision loop cap exceeded after 3 attempts",
            }

    ineligible = (state.get("applicant_type") or "").upper() in {"INDIVIDUAL", "FOR_PROFIT"}
    return {
        "gate_states": gate_states,
        "revision_loop_counts": updated_counts,
        "ai_run_ids": ai_run_ids,
        "eligibility_output": bedrock.get("body", ""),
        "current_stage": "SCREENING" if gate_decision != "APPROVE" else "PEER_REVIEW",
        "active_gate_id": None,
        "sla_timers": (
            {**state.get("sla_timers", {}), "GATE_2": utc_now_iso()}
            if gate_decision == "APPROVE" else state.get("sla_timers", {})
        ),
    }


# ---------------------------------------------------------------------------
# Node 3: reviewer assignment
# ---------------------------------------------------------------------------

def reviewer_assignment_node(state: WorkflowState) -> dict:
    """Runs reviewer-assignment-agent. No HITL interrupt."""
    log.info("reviewer_assignment_node workflow=%s", state["workflow_run_id"])
    idem_key = build_idempotency_key(
        workflow_run_id=state["workflow_run_id"],
        stage="reviewer_assignment",
        gate_id=None,
        attempt=0,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        corpus_version=state.get("corpus_version", "v1"),
        raw_text=state.get("raw_text") or "",
        query=state.get("topic") or "federal grants",
        tenant_id=state["tenant_id"],
    )
    cached = idempotency_store.get(idem_key)
    if cached:
        return {"reviewer_candidates": cached}
    candidates = run_reviewer_assignment(
        program_area=state.get("topic") or "federal grants",
        required_expertise=["grants management", "federal compliance"],
        tenant_id=state["tenant_id"],
        grant_application_id=state["grant_application_id"],
    )
    result = [c.model_dump() for c in candidates]
    idempotency_store.set(idem_key, result)
    return {"reviewer_candidates": result}


# ---------------------------------------------------------------------------
# Node 4: COI check
# ---------------------------------------------------------------------------

def coi_check_node(state: WorkflowState) -> dict:
    """
    Runs COI-check-agent (deterministic rules — NOT AI judgment).
    If any COI flags exist, the gate_2_node will interrupt for Review Lead.
    If reviewer pool is exhausted (all flagged), escalates to Grants Officer.
    """
    log.info("coi_check_node workflow=%s", state["workflow_run_id"])
    raw_candidates = state.get("reviewer_candidates") or []
    candidates = [ReviewerCandidate(**c) for c in raw_candidates]

    coi_flags = run_coi_check(
        candidates=candidates,
        applicant_uei=state.get("applicant_uei"),
        applicant_org=state.get("applicant_org"),
        pi_name=state.get("pi_name"),
    )

    # Pool exhaustion check: all reviewers have COI
    all_flagged = len(candidates) > 0 and len(coi_flags) == len(candidates)
    if all_flagged:
        ai_run_id = state.get("ai_run_ids", {}).get("PEER_REVIEW", str(uuid.uuid4()))
        esc_id = gate_enforcer.create_escalation(
            gate_id=GateId.GATE_2,
            tenant_id=state["tenant_id"],
            ai_run_id=ai_run_id,
            human_review_reasons=[HumanReviewReason.REGULATORY_CONFLICT],
            grounding_status=GroundingStatus.UNGROUNDED,
            confidence_score=0.0,
        ).escalation_id
        log.warning("reviewer_pool_exhausted workflow=%s", state["workflow_run_id"])
        return {
            "coi_flags": coi_flags,
            "pending_escalation_ids": [*state.get("pending_escalation_ids", []), esc_id],
            "active_gate_id": GateId.GATE_2.value,
            "gate_states": {**state.get("gate_states", {}), "GATE_2": "POOL_EXHAUSTED"},
        }

    return {
        "coi_flags": coi_flags,
        # Pre-set GATE_2 when flags present so checkpoint is correct before gate_2_node interrupts
        "active_gate_id": GateId.GATE_2.value if coi_flags else None,
    }


# ---------------------------------------------------------------------------
# Node 5: Gate 2 (COI resolution)
# ---------------------------------------------------------------------------

def gate_2_node(state: WorkflowState) -> dict:
    """
    Interrupts for Review Lead when COI flags are present.
    If no flags, passes through without interrupting.
    """
    coi_flags = state.get("coi_flags") or {}
    if not coi_flags:
        return {"gate_states": {**state.get("gate_states", {}), "GATE_2": "RESOLVE_AND_CONTINUE"}}

    log.info("gate_2_node INTERRUPT workflow=%s flagged_reviewers=%d", state["workflow_run_id"], len(coi_flags))
    gate_decision: str = interrupt({
        "workflow_run_id": state["workflow_run_id"],
        "hitl_gate": "GATE_2",
        "ai_run_id": (state.get("ai_run_ids") or {}).get("SCREENING") or str(uuid.uuid4()),
        "coi_flags": coi_flags,
        "reviewer_candidates": state.get("reviewer_candidates"),
        "grant_application_id": state["grant_application_id"],
    })

    return {
        "gate_states": {**state.get("gate_states", {}), "GATE_2": gate_decision},
        "active_gate_id": None,
        "sla_timers": {**state.get("sla_timers", {}), "GATE_3": utc_now_iso()},
    }


# ---------------------------------------------------------------------------
# Node 6: panel confirmation
# ---------------------------------------------------------------------------

def panel_confirmation_node(state: WorkflowState) -> dict:
    """Confirms final panel composition after Gate 2 resolution."""
    log.info("panel_confirmation_node workflow=%s", state["workflow_run_id"])
    raw_candidates = state.get("reviewer_candidates") or []
    candidates = [ReviewerCandidate(**c) for c in raw_candidates]
    coi_flags = state.get("coi_flags") or {}
    gate_decision = (state.get("gate_states") or {}).get("GATE_2", "RESOLVE_AND_CONTINUE")
    gate_decision_ids = state.get("gate_decision_ids") or []

    if gate_decision == "REMOVE_REVIEWER":
        final_reviewers = [c for c in candidates if c.reviewer_id not in coi_flags]
    else:
        final_reviewers = candidates

    idem_key = build_idempotency_key(
        workflow_run_id=state["workflow_run_id"],
        stage="panel_confirmation",
        gate_id=GateId.GATE_2.value,
        attempt=0,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        corpus_version=state.get("corpus_version", "v1"),
        raw_text=state.get("raw_text") or "",
        query=gate_decision,
        tenant_id=state["tenant_id"],
    )
    cached = idempotency_store.get(idem_key)
    if cached is None:
        panel_record = run_panel_confirmation(
            final_reviewers=final_reviewers,
            gate_decision=gate_decision,
            gate_decision_id=gate_decision_ids[-1] if gate_decision_ids else "",
            tenant_id=state["tenant_id"],
            grant_application_id=state["grant_application_id"],
        )
        idempotency_store.set(idem_key, panel_record)
    else:
        panel_record = cached

    return {
        "final_panel": [r.model_dump() for r in final_reviewers],
        "evidence_snapshot": panel_record,
        # Pre-set GATE_3 so checkpoint is correct before factor_suggest_node interrupts
        "active_gate_id": GateId.GATE_3.value,
    }


# ---------------------------------------------------------------------------
# Node 7: factor suggest (Gate 3)
# ---------------------------------------------------------------------------

def factor_suggest_node(state: WorkflowState) -> dict:
    """
    Runs factor-scoring narrative generation (2 CFR 200.204/205), then interrupts
    for Gate 3 (HUMAN_REVIEWER review).
    """
    log.info("factor_suggest_node workflow=%s", state["workflow_run_id"])
    topic = state.get("topic") or "merit criteria evaluation"
    query = f"evaluation factor merit criterion {topic}"
    citations, conf, faith, grounding_status, reasons, should_block = _grounded_retrieve(
        query, state, GateId.GATE_3, "PEER_REVIEW"
    )

    ai_run_id = str(uuid.uuid4())
    ai_run_ids = {**state.get("ai_run_ids", {}), "PEER_REVIEW": ai_run_id}

    if should_block:
        esc_id = _create_escalation(state, GateId.GATE_3, reasons, grounding_status, conf, ai_run_id=ai_run_id)
        return {
            "active_gate_id": GateId.GATE_3.value,
            "gate_states": {**state.get("gate_states", {}), "GATE_3": "BLOCKED"},
            "pending_escalation_ids": [*state.get("pending_escalation_ids", []), esc_id],
            "ai_run_ids": ai_run_ids,
        }

    bedrock = _bedrock_with_idempotency(
        prompt=(
            f"Suggest a merit-criterion review narrative for: {topic}. "
            f"Application context: {state.get('constraints') or '(none)'}. "
            f"Cite: {', '.join(c.source_id for c in citations)}."
        ),
        system="You suggest peer-reviewer narrative; HITL approves before publish.",
        state=state,
        stage="PEER_REVIEW",
        gate_id=GateId.GATE_3.value,
        query=query,
    )

    gate_decision: str = interrupt({
        "workflow_run_id": state["workflow_run_id"],
        "hitl_gate": "GATE_3",
        "ai_run_id": ai_run_id,
        "factor_suggestion": bedrock.get("body", ""),
        "grounding_status": grounding_status.value,
        "confidence_score": conf,
        "human_review_reasons": [r.value for r in reasons],
        "retrieved_sources": [c.source_id for c in citations],
        "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
        "requires_human_review": True,
    })

    gate_states = {**state.get("gate_states", {}), "GATE_3": gate_decision}
    updated_counts = dict(state.get("revision_loop_counts", {}))
    if gate_decision == "EDIT":
        try:
            updated_counts = increment_revision_loop(state, "GATE_3")
        except RevisionLoopCapExceeded as e:
            log.warning("Gate 3 revision cap exceeded: %s", e)
            esc_id = gate_enforcer.create_escalation(
                gate_id=GateId.GATE_3,
                tenant_id=state["tenant_id"],
                ai_run_id=ai_run_id,
                human_review_reasons=[HumanReviewReason.REVISION_LOOP_EXCEEDED],
                grounding_status=grounding_status,
                confidence_score=conf,
            ).escalation_id
            return {
                "gate_states": gate_states,
                "revision_loop_counts": updated_counts,
                "ai_run_ids": ai_run_ids,
                "pending_escalation_ids": [*state.get("pending_escalation_ids", []), esc_id],
                "active_gate_id": None,
                "completed": True,
                "denial_reason": "Gate 3 revision loop cap exceeded after 3 attempts",
            }

    return {
        "gate_states": gate_states,
        "revision_loop_counts": updated_counts,
        "ai_run_ids": ai_run_ids,
        "factor_suggestion": bedrock.get("body", ""),
        "current_stage": "PEER_REVIEW" if gate_decision != "ACCEPT" else "AWARD",
        # Pre-set GATE_4 on ACCEPT so checkpoint is correct before ssdd_draft_node interrupts
        "active_gate_id": GateId.GATE_4.value if gate_decision == "ACCEPT" else None,
        "sla_timers": (
            {**state.get("sla_timers", {}), "GATE_4": utc_now_iso()}
            if gate_decision == "ACCEPT" else state.get("sla_timers", {})
        ),
    }


# ---------------------------------------------------------------------------
# Node 8: SSDD draft (Gate 4)
# ---------------------------------------------------------------------------

def ssdd_draft_node(state: WorkflowState) -> dict:
    """
    Runs award package / SSDD draft generation (2 CFR 200.205/212), then interrupts
    for Gate 4 (GRANTS_OFFICER award decision — non-delegable).
    """
    log.info("ssdd_draft_node workflow=%s", state["workflow_run_id"])
    topic = state.get("topic") or "award decision funding recommendation"
    query = f"award decision funding recommendation {topic}"
    citations, conf, faith, grounding_status, reasons, should_block = _grounded_retrieve(
        query, state, GateId.GATE_4, "AWARD"
    )

    ai_run_id = str(uuid.uuid4())
    ai_run_ids = {**state.get("ai_run_ids", {}), "AWARD": ai_run_id}

    if should_block:
        esc_id = _create_escalation(state, GateId.GATE_4, reasons, grounding_status, conf, ai_run_id=ai_run_id)
        return {
            "active_gate_id": GateId.GATE_4.value,
            "gate_states": {**state.get("gate_states", {}), "GATE_4": "BLOCKED"},
            "pending_escalation_ids": [*state.get("pending_escalation_ids", []), esc_id],
            "ai_run_ids": ai_run_ids,
        }

    bedrock = _bedrock_with_idempotency(
        prompt=(
            f"Draft a panel funding-recommendation narrative for: {topic}. "
            f"Constraints: {state.get('constraints') or 'merit-based selection per 2 CFR 200.205'}. "
            f"Regulatory basis: {', '.join(c.source_id for c in citations)}."
        ),
        system="You draft funding-recommendation memos; the Selecting Official reviews + approves.",
        state=state,
        stage="AWARD",
        gate_id=GateId.GATE_4.value,
        query=query,
    )

    gate_decision: str = interrupt({
        "workflow_run_id": state["workflow_run_id"],
        "hitl_gate": "GATE_4",
        "ai_run_id": ai_run_id,
        "ssdd_narrative": bedrock.get("body", ""),
        "grounding_status": grounding_status.value,
        "confidence_score": conf,
        "human_review_reasons": [r.value for r in reasons],
        "retrieved_sources": [c.source_id for c in citations],
        "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
        "requires_human_review": True,
    })

    return {
        "gate_states": {**state.get("gate_states", {}), "GATE_4": gate_decision},
        "ai_run_ids": ai_run_ids,
        "ssdd_narrative": bedrock.get("body", ""),
        "current_stage": "AWARD",
        "active_gate_id": None,
        "denial_reason": (
            "DO_NOT_AWARD decision by Grants Officer"
            if gate_decision == "DO_NOT_AWARD"
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Node 9: seal audit (terminal — AWARD)
# ---------------------------------------------------------------------------

def seal_audit_node(state: WorkflowState) -> dict:
    """Seals the audit trail. Called only when Gate 4 decision is AWARD."""
    log.info("seal_audit_node workflow=%s AWARD", state["workflow_run_id"])
    return {
        "completed": True,
        "current_stage": "POST_AWARD",
        "active_gate_id": None,
    }


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------

def route_gate_1(state: WorkflowState) -> str:
    if state.get("denial_reason") or state.get("completed"):
        return "__end__"
    decision = (state.get("gate_states") or {}).get("GATE_1", "PENDING")
    if decision == "APPROVE":
        return "reviewer_assignment"
    if decision in ("RETURN_FOR_FIXES", "BLOCKED"):
        return "eligibility"
    return "__end__"


def route_gate_2(state: WorkflowState) -> str:
    decision = (state.get("gate_states") or {}).get("GATE_2", "PENDING")
    if decision in ("RESOLVE_AND_CONTINUE", "OVERRIDE"):
        return "panel_confirmation"
    if decision == "REMOVE_REVIEWER":
        return "reviewer_assignment"  # full re-panel: reassign from remaining pool
    if decision == "POOL_EXHAUSTED":
        return "__end__"   # escalated to Grants Officer; manual path
    return "panel_confirmation"


def route_gate_3(state: WorkflowState) -> str:
    if state.get("denial_reason") or state.get("completed"):
        return "__end__"
    decision = (state.get("gate_states") or {}).get("GATE_3", "PENDING")
    if decision == "ACCEPT":
        return "ssdd_draft"
    if decision == "EDIT":
        return "factor_suggest"
    return "__end__"


def route_gate_4(state: WorkflowState) -> str:
    decision = (state.get("gate_states") or {}).get("GATE_4", "PENDING")
    if decision == "AWARD":
        return "seal_audit"
    if decision == "RETURN_TO_REVIEW":
        return "factor_suggest"
    # DO_NOT_AWARD → terminal
    return "__end__"
