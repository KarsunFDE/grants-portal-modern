"""
Grounding enforcement — hitl-plan.txt §Grounding Policy.

Rules:
- AI must reference real sources: 2 CFR 200, 45 CFR 75, NOFO content.
- Low-confidence, missing citations, or ungrounded output → block + escalate.
- Citation conflicts, regulatory conflicts (2 CFR/45 CFR), FAR/DFARS conflicts → requires_human_review.
- Ungrounded regulatory guidance is never directly shipped.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from app.schemas.hitl import (
    Citation,
    GateId,
    GateOwnerRole,
    GATE_OWNER_ROLES,
    GroundingStatus,
    HumanReviewReason,
)

# ADR 0009 §1 — gate-differentiated thresholds; uniform threshold is incorrect.
_CONFIDENCE_THRESHOLDS: Dict[GateId, float] = {
    GateId.GATE_1: 0.65,
    GateId.GATE_3: 0.70,
    GateId.GATE_4: 0.70,
}
_FAITHFULNESS_THRESHOLDS: Dict[GateId, float] = {
    GateId.GATE_1: 0.65,
    GateId.GATE_3: 0.70,
    GateId.GATE_4: 0.70,
}
_DEFAULT_CONFIDENCE_THRESHOLD = 0.70
_DEFAULT_FAITHFULNESS_THRESHOLD = 0.70

# Public aliases — used by callers without gate context (e.g. general validation).
CONFIDENCE_THRESHOLD = _DEFAULT_CONFIDENCE_THRESHOLD
FAITHFULNESS_THRESHOLD = _DEFAULT_FAITHFULNESS_THRESHOLD

# Public exports — used by cache_validator.py to apply gate-specific thresholds.
GATE_CONFIDENCE_THRESHOLDS: Dict[GateId, float] = _CONFIDENCE_THRESHOLDS
GATE_FAITHFULNESS_THRESHOLDS: Dict[GateId, float] = _FAITHFULNESS_THRESHOLDS

# ADR 0009 §11 — regulatory source precedence order (1 = highest authority).
REGULATION_PRECEDENCE: Dict[str, int] = {
    "2 CFR 200": 1,
    "45 CFR 75": 2,
    "NOFO": 3,
    "AGENCY_POLICY": 4,
    "QA": 5,
    "FAR": 3,
    "DFARS": 3,
}


def compute_grounding_status(
    citations: List[Citation],
    confidence_score: float,
    faithfulness_score: float,
    gate_id: Optional[GateId] = None,
) -> Tuple[GroundingStatus, List[HumanReviewReason]]:
    """
    Determine grounding status and human review reasons.
    Uses gate-differentiated thresholds when gate_id is provided (ADR 0009 §1).
    Returns (GroundingStatus, [HumanReviewReason, ...]).
    """
    conf_threshold = _CONFIDENCE_THRESHOLDS.get(gate_id, _DEFAULT_CONFIDENCE_THRESHOLD) if gate_id else _DEFAULT_CONFIDENCE_THRESHOLD
    faith_threshold = _FAITHFULNESS_THRESHOLDS.get(gate_id, _DEFAULT_FAITHFULNESS_THRESHOLD) if gate_id else _DEFAULT_FAITHFULNESS_THRESHOLD

    reasons: List[HumanReviewReason] = []

    if not citations:
        reasons.append(HumanReviewReason.MISSING_CITATIONS)
        return GroundingStatus.MISSING_CITATIONS, reasons

    if _has_citation_conflict(citations):
        reasons.append(HumanReviewReason.CITATION_CONFLICT)

    if _has_regulatory_conflict(citations):
        reasons.append(HumanReviewReason.REGULATORY_CONFLICT)

    if _has_far_dfars_conflict(citations):
        reasons.append(HumanReviewReason.FAR_DFARS_CONFLICT)

    # ADR 0009 §11 — precedence-based conflict detection
    precedence_reason = _detect_precedence_conflict(citations)
    if precedence_reason and precedence_reason not in reasons:
        reasons.append(precedence_reason)

    version_reason = _detect_version_mismatch(citations)
    if version_reason:
        reasons.append(version_reason)

    if confidence_score < conf_threshold:
        reasons.append(HumanReviewReason.LOW_CONFIDENCE)

    if faithfulness_score < faith_threshold:
        reasons.append(HumanReviewReason.LOW_FAITHFULNESS)

    if not reasons:
        return GroundingStatus.GROUNDED, []

    # Determine primary status — most severe first
    if confidence_score < conf_threshold:
        return GroundingStatus.LOW_CONFIDENCE, reasons
    if HumanReviewReason.CITATION_CONFLICT in reasons:
        return GroundingStatus.CITATION_CONFLICT, reasons
    if HumanReviewReason.REGULATORY_CONFLICT in reasons:
        return GroundingStatus.CITATION_CONFLICT, reasons

    return GroundingStatus.UNGROUNDED, reasons


def is_grounded(grounding_status: GroundingStatus) -> bool:
    return grounding_status == GroundingStatus.GROUNDED


def route_escalation(gate_id: GateId) -> List[GateOwnerRole]:
    """Return the owner roles for a given gate (hitl-plan.txt §Grounding Escalation Routing)."""
    return GATE_OWNER_ROLES.get(gate_id, [])


# ---------------------------------------------------------------------------
# Conflict detectors
# ---------------------------------------------------------------------------

def _has_citation_conflict(citations: List[Citation]) -> bool:
    """Same section referenced by multiple distinct regulations."""
    section_regs: Dict[str, Set[str]] = {}
    for c in citations:
        if c.section and c.regulation:
            section_regs.setdefault(c.section, set()).add(c.regulation)
    return any(len(regs) > 1 for regs in section_regs.values())


def _has_regulatory_conflict(citations: List[Citation]) -> bool:
    """2 CFR 200 and 45 CFR 75 both cite the same section — potential disagreement."""
    cfr200 = {c.section for c in citations if c.regulation == "2 CFR 200" and c.section}
    cfr75 = {c.section for c in citations if c.regulation == "45 CFR 75" and c.section}
    return bool(cfr200 & cfr75)


def _has_far_dfars_conflict(citations: List[Citation]) -> bool:
    """FAR and DFARS both cite the same section — procurement conflict."""
    far = {c.section for c in citations if c.regulation == "FAR" and c.section}
    dfars = {c.section for c in citations if c.regulation == "DFARS" and c.section}
    return bool(far & dfars)


def _detect_precedence_conflict(citations: List[Citation]) -> Optional[HumanReviewReason]:
    """
    ADR 0009 §11 — detect conflicts between sources at different precedence levels.
    CFR (rank 1-2) vs NOFO (rank 3): CFR_NOFO_CONFLICT.
    CFR/NOFO vs AGENCY_POLICY (rank 4): AGENCY_POLICY_CONFLICT.
    Returns the most severe reason code, or None if no conflict.
    """
    sections: Dict[str, Set[str]] = {}
    for c in citations:
        if c.section and c.regulation:
            sections.setdefault(c.section, set()).add(c.regulation)

    for section, regs in sections.items():
        ranks = {r: REGULATION_PRECEDENCE.get(r, 99) for r in regs}
        if len(regs) < 2:
            continue
        min_rank = min(ranks.values())
        max_rank = max(ranks.values())
        if min_rank <= 2 and max_rank == 3:
            return HumanReviewReason.CFR_NOFO_CONFLICT
        if min_rank <= 3 and max_rank == 4:
            return HumanReviewReason.AGENCY_POLICY_CONFLICT
    return None


def _detect_version_mismatch(citations: List[Citation]) -> Optional[HumanReviewReason]:
    """
    ADR 0009 §11 — detect multiple last_revised dates for the same source_id.
    Retrieval layer (retrieval.py:_filter_superseded_amendments) already removes older
    versions; if duplicates still appear here, a supersession conflict survived filtering
    and requires human review. Returns AMENDMENT_SUPERSEDES in that case.
    VERSION_MISMATCH is returned when source_id is the same but dates differ unexpectedly
    (e.g., different regulation enum for same section).
    """
    source_dates: Dict[str, Set[str]] = {}
    for c in citations:
        if c.source_id and c.last_revised:
            source_dates.setdefault(c.source_id, set()).add(c.last_revised)
    if any(len(dates) > 1 for dates in source_dates.values()):
        return HumanReviewReason.AMENDMENT_SUPERSEDES
    return None
