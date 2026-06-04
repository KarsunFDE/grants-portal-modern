"""
HITL schemas — source of truth: docs/hitl-plan.txt.
All gate IDs, owner roles, allowed decisions, and audit fields live here.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class WorkflowStage(str, Enum):
    INTAKE = "INTAKE"
    SCREENING = "SCREENING"
    PEER_REVIEW = "PEER_REVIEW"
    AWARD = "AWARD"
    POST_AWARD = "POST_AWARD"


class GateId(str, Enum):
    GATE_1 = "GATE_1"   # Eligibility & Risk Review — Screening
    GATE_2 = "GATE_2"   # Conflict of Interest — Peer Review
    GATE_3 = "GATE_3"   # Factor Suggest Acceptance — Peer Review
    GATE_4 = "GATE_4"   # Award Decision — Award


class GateOwnerRole(str, Enum):
    GRANTS_OFFICER = "GRANTS_OFFICER"
    PROGRAM_OFFICER = "PROGRAM_OFFICER"
    REVIEW_LEAD = "REVIEW_LEAD"
    HUMAN_REVIEWER = "HUMAN_REVIEWER"


class GateDecision(str, Enum):
    # Gate 1
    APPROVE = "APPROVE"
    RETURN_FOR_FIXES = "RETURN_FOR_FIXES"
    REJECT = "REJECT"
    # Gate 2
    RESOLVE_AND_CONTINUE = "RESOLVE_AND_CONTINUE"
    REMOVE_REVIEWER = "REMOVE_REVIEWER"
    OVERRIDE = "OVERRIDE"
    # Gate 3
    ACCEPT = "ACCEPT"
    EDIT = "EDIT"
    # Gate 4
    AWARD = "AWARD"
    DO_NOT_AWARD = "DO_NOT_AWARD"
    RETURN_TO_REVIEW = "RETURN_TO_REVIEW"


class GroundingStatus(str, Enum):
    GROUNDED = "GROUNDED"
    UNGROUNDED = "UNGROUNDED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MISSING_CITATIONS = "MISSING_CITATIONS"
    CITATION_CONFLICT = "CITATION_CONFLICT"


class HumanReviewReason(str, Enum):
    CITATION_CONFLICT = "CITATION_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LOW_FAITHFULNESS = "LOW_FAITHFULNESS"
    REGULATORY_CONFLICT = "REGULATORY_CONFLICT"
    MISSING_CITATIONS = "MISSING_CITATIONS"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    CACHE_REVALIDATION_FAILED = "CACHE_REVALIDATION_FAILED"
    UNGROUNDED = "UNGROUNDED"
    FAR_DFARS_CONFLICT = "FAR_DFARS_CONFLICT"
    # ADR 0009 §11 — regulatory contradiction reason codes
    CFR_NOFO_CONFLICT = "CFR_NOFO_CONFLICT"
    AMENDMENT_SUPERSEDES = "AMENDMENT_SUPERSEDES"
    AGENCY_POLICY_CONFLICT = "AGENCY_POLICY_CONFLICT"
    VERSION_MISMATCH = "VERSION_MISMATCH"


class InvalidationTrigger(str, Enum):
    APPLICATION_DATA = "APPLICATION_DATA"
    NOFO_AMENDMENT = "NOFO_AMENDMENT"
    POLICY_CORPUS = "POLICY_CORPUS"
    REVIEWER_ASSIGNMENTS = "REVIEWER_ASSIGNMENTS"
    COI_STATE = "COI_STATE"
    AWARD_PACKAGE = "AWARD_PACKAGE"


# ---------------------------------------------------------------------------
# Routing tables (hitl-plan.txt §Gate 1-4)
# ---------------------------------------------------------------------------

GATE_OWNER_ROLES: Dict[GateId, List[GateOwnerRole]] = {
    GateId.GATE_1: [GateOwnerRole.GRANTS_OFFICER, GateOwnerRole.PROGRAM_OFFICER],
    GateId.GATE_2: [GateOwnerRole.REVIEW_LEAD],
    GateId.GATE_3: [GateOwnerRole.HUMAN_REVIEWER],
    GateId.GATE_4: [GateOwnerRole.GRANTS_OFFICER],
}

GATE_WORKFLOW_STAGE: Dict[GateId, WorkflowStage] = {
    GateId.GATE_1: WorkflowStage.SCREENING,
    GateId.GATE_2: WorkflowStage.PEER_REVIEW,
    GateId.GATE_3: WorkflowStage.PEER_REVIEW,
    GateId.GATE_4: WorkflowStage.AWARD,
}

GATE_ALLOWED_DECISIONS: Dict[GateId, List[GateDecision]] = {
    GateId.GATE_1: [GateDecision.APPROVE, GateDecision.RETURN_FOR_FIXES, GateDecision.REJECT],
    GateId.GATE_2: [GateDecision.RESOLVE_AND_CONTINUE, GateDecision.REMOVE_REVIEWER, GateDecision.OVERRIDE],
    GateId.GATE_3: [GateDecision.ACCEPT, GateDecision.EDIT, GateDecision.REJECT],
    GateId.GATE_4: [GateDecision.AWARD, GateDecision.DO_NOT_AWARD, GateDecision.RETURN_TO_REVIEW],
}

# Decisions that BLOCK the workflow from advancing
GATE_BLOCKING_DECISIONS: Dict[GateId, List[GateDecision]] = {
    GateId.GATE_1: [GateDecision.REJECT, GateDecision.RETURN_FOR_FIXES],
    GateId.GATE_2: [GateDecision.REMOVE_REVIEWER],
    GateId.GATE_3: [GateDecision.REJECT],
    GateId.GATE_4: [GateDecision.DO_NOT_AWARD, GateDecision.RETURN_TO_REVIEW],
}


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    chunk_id: str
    source_id: str
    section: Optional[str] = None
    subsection: Optional[str] = None        # e.g. "b.1" — ADR 0009 §M3 / retrieval-plan §14
    section_title: Optional[str] = None     # human-readable heading
    last_revised: Optional[str] = None
    text_excerpt: Optional[str] = None
    tenant_id: Optional[str] = None
    regulation: Optional[str] = None        # "2 CFR 200", "45 CFR 75", "NOFO", "FAR", "DFARS"
    relevance_score: Optional[float] = None  # 0–1; populated from vectorSearchScore


class EvidenceRef(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_id: str
    source_id: str
    section: Optional[str] = None
    last_revised: Optional[str] = None
    tenant_id: str
    regulation: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class GroundedResponse(BaseModel):
    """Structured JSON contract returned by grounded AI endpoints."""
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    retrieved_sources: List[str] = Field(default_factory=list)
    citation_refs: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    faithfulness_score: float = Field(ge=0.0, le=1.0)
    grounding_status: GroundingStatus
    requires_human_review: bool = False
    human_review_reasons: List[HumanReviewReason] = Field(default_factory=list)
    hitl_gate: Optional[GateId] = None
    escalation_owner: Optional[str] = None
    escalation_id: Optional[str] = None
    ai_run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # ADR 0009 §10 — audit replay fields
    retrieval_strategy: Optional[str] = None   # "hybrid" | "dense" | "sparse" | "static"
    corpus_version: Optional[str] = None
    cache_hit: bool = False


class GateDecisionRecord(BaseModel):
    """Append-only audit record for a human gate decision (hitl-plan.txt §Audit)."""
    gate_decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gate_id: GateId
    workflow_stage: WorkflowStage
    actor_id: str
    actor_role: GateOwnerRole
    tenant_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ai_run_id: str
    decision: GateDecision
    rationale: str = Field(min_length=1, description="Human rationale required by spec.")
    override_flag: bool = False
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    retrieved_sources: List[str] = Field(default_factory=list)
    citation_refs: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    grounding_status: GroundingStatus = GroundingStatus.UNGROUNDED
    # ADR 0009 §10 — audit replay fields; auditor must be able to replay from ai_run_id alone
    retrieval_filter: Optional[Dict] = None
    pre_rerank_candidates: List[str] = Field(default_factory=list)
    post_rerank_candidates: List[str] = Field(default_factory=list)
    reranker_model_id: Optional[str] = None
    prompt_template_version: Optional[str] = None

    @model_validator(mode="after")
    def _validate_decision_allowed(self) -> "GateDecisionRecord":
        allowed = GATE_ALLOWED_DECISIONS.get(self.gate_id, [])
        if self.decision not in allowed:
            raise ValueError(
                f"Decision {self.decision.value!r} not allowed for {self.gate_id.value}. "
                f"Allowed: {[d.value for d in allowed]}"
            )
        return self

    @model_validator(mode="after")
    def _validate_tenant_binding(self) -> "GateDecisionRecord":
        """Every evidence_ref tenant_id must equal the gate decision tenant_id."""
        for ref in self.evidence_refs:
            if ref.tenant_id != self.tenant_id:
                raise ValueError(
                    f"Tenant binding violation: evidence_ref {ref.evidence_id} "
                    f"has tenant_id={ref.tenant_id!r}, gate tenant_id={self.tenant_id!r}"
                )
        return self


class GateDecisionRequest(BaseModel):
    gate_id: GateId
    actor_id: str
    actor_role: GateOwnerRole
    tenant_id: str
    ai_run_id: str
    decision: GateDecision
    rationale: str = Field(min_length=1, description="Human rationale required by spec.")
    override_flag: bool = False
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    retrieved_sources: List[str] = Field(default_factory=list)
    citation_refs: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    grounding_status: GroundingStatus = GroundingStatus.UNGROUNDED
    # ADR 0009 §10 — audit replay fields; must match GateDecisionRecord for write path to work
    retrieval_filter: Optional[Dict] = None
    pre_rerank_candidates: List[str] = Field(default_factory=list)
    post_rerank_candidates: List[str] = Field(default_factory=list)
    reranker_model_id: Optional[str] = None
    prompt_template_version: Optional[str] = None


class EscalationRecord(BaseModel):
    """Created on every grounding failure — no silent retries."""
    escalation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gate_id: GateId
    gate_owner_roles: List[GateOwnerRole]
    tenant_id: str
    ai_run_id: str
    reason: str
    human_review_reasons: List[HumanReviewReason]
    grounding_status: GroundingStatus
    confidence_score: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_decision_id: Optional[str] = None


class RetrievalInvalidationEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    trigger: InvalidationTrigger
    resource_id: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    cache_keys_invalidated: List[str] = Field(default_factory=list)
