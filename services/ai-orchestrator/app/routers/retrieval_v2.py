"""
Grounded retrieval endpoints — /rag/v2/search, /rag/v2/invalidate.

Enforces hitl-plan.txt §Grounding Policy:
  - Retrieval required before generation for policy-sensitive outputs.
  - Ungrounded / low-confidence output → block + escalate to named gate owner.
  - Every escalation creates a gate decision record; no silent retries.
  - Cache hits revalidated before returning (AC13).
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.hitl import (
    GATE_OWNER_ROLES,
    GateId,
    GroundedResponse,
    GroundingStatus,
    InvalidationTrigger,
)
from app.services.cache_validator import validate_before_generation
from app.services.gate_enforcer import gate_enforcer
from app.services.grounding import compute_grounding_status, is_grounded
from app.services.retrieval import retrieval_service

router = APIRouter(prefix="/rag/v2", tags=["retrieval-v2"])

# Default escalation gate when gate_context not specified — routes to Screening owner.
# Per spec: "No silent retries for blocked grounding cases." All failures must be recorded.
_DEFAULT_ESCALATION_GATE = GateId.GATE_1


class RetrievalRequest(BaseModel):
    query: str
    tenant_id: str
    gate_context: Optional[GateId] = None
    application_data_hash: Optional[str] = None
    nofo_hash: Optional[str] = None
    reviewer_state_hash: Optional[str] = None
    policy_corpus_hash: Optional[str] = None
    coi_state_hash: Optional[str] = None
    award_package_hash: Optional[str] = None
    corpus_version: str = "v1"
    skip_cache: bool = False


class InvalidationRequest(BaseModel):
    tenant_id: str
    trigger: InvalidationTrigger
    resource_id: str


@router.post("/search", response_model=GroundedResponse)
def grounded_search(request: RetrievalRequest) -> GroundedResponse:
    """
    Hybrid retrieval with grounding checks and cache revalidation.
    If output is ungrounded/low-confidence: blocks and escalates to named gate owner.
    Escalation created regardless of whether gate_context is set — no silent retries.
    """
    citations, confidence, faithfulness, retrieved_at, retrieval_strategy, is_cache_hit = retrieval_service.retrieve(
        query=request.query,
        tenant_id=request.tenant_id,
        application_data_hash=request.application_data_hash,
        nofo_hash=request.nofo_hash,
        reviewer_state_hash=request.reviewer_state_hash,
        policy_corpus_hash=request.policy_corpus_hash,
        coi_state_hash=request.coi_state_hash,
        award_package_hash=request.award_package_hash,
        corpus_version=request.corpus_version,
        skip_cache=request.skip_cache,
    )

    grounding_status, human_review_reasons = compute_grounding_status(
        citations, confidence, faithfulness, gate_id=request.gate_context
    )

    # Cache revalidation before returning results (hitl-plan.txt §Cache Revalidation Policy — AC13)
    cache_ok, cache_reasons = validate_before_generation(
        citations=citations,
        confidence_score=confidence,
        faithfulness_score=faithfulness,
        cache_created_at=retrieved_at,
        tenant_id=request.tenant_id,
        gate_id=request.gate_context,
        retrieval_strategy=retrieval_strategy,
    )
    if not cache_ok:
        for r in cache_reasons:
            if r not in human_review_reasons:
                human_review_reasons.append(r)
        if is_grounded(grounding_status):
            grounding_status = GroundingStatus.UNGROUNDED

    # ai_run_id generated once here — same ID used in escalation record AND client response.
    # Callers must be able to locate the escalation by the ai_run_id they receive.
    ai_run_id = str(uuid.uuid4())

    requires_human_review = bool(human_review_reasons)
    hitl_gate: Optional[GateId] = None
    escalation_owner: Optional[str] = None
    escalation_id: Optional[str] = None

    if requires_human_review:
        hitl_gate = request.gate_context or _DEFAULT_ESCALATION_GATE
        owners = GATE_OWNER_ROLES.get(hitl_gate, [])
        escalation_owner = owners[0].value if owners else None
        escalation = gate_enforcer.create_escalation(
            gate_id=hitl_gate,
            tenant_id=request.tenant_id,
            ai_run_id=ai_run_id,
            human_review_reasons=human_review_reasons,
            grounding_status=grounding_status,
            confidence_score=confidence,
        )
        escalation_id = escalation.escalation_id

    retrieved_sources = list({c.source_id for c in citations})
    citation_refs = [
        f"{c.regulation or 'UNKNOWN'}:{c.section or 'N/A'}" for c in citations
    ]

    return GroundedResponse(
        answer=f"Retrieved {len(citations)} citation(s) for: {request.query}",
        citations=citations,
        retrieved_sources=retrieved_sources,
        citation_refs=citation_refs,
        confidence_score=confidence,
        faithfulness_score=faithfulness,
        grounding_status=grounding_status,
        requires_human_review=requires_human_review,
        human_review_reasons=human_review_reasons,
        hitl_gate=hitl_gate,
        escalation_owner=escalation_owner,
        escalation_id=escalation_id,
        ai_run_id=ai_run_id,
        corpus_version=request.corpus_version,
        cache_hit=is_cache_hit,
        retrieval_strategy=retrieval_strategy,
    )


@router.post("/invalidate")
def invalidate_cache(request: InvalidationRequest) -> dict:
    """
    Invalidate retrieval cache after a trigger event.
    Per hitl-plan.txt: re-retrieval is mandatory — prior evidence cannot be reused.
    """
    count = retrieval_service.invalidate(
        tenant_id=request.tenant_id,
        trigger=request.trigger,
        resource_id=request.resource_id,
    )
    return {
        "invalidated_count": count,
        "trigger": request.trigger.value,
        "tenant_id": request.tenant_id,
        "resource_id": request.resource_id,
        "message": "Re-retrieval required before next gate decision. Prior evidence cannot be reused.",
    }
