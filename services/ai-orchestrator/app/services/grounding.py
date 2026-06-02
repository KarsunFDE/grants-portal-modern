"""
Grounding enforcement — hitl-plan.txt §Grounding Policy.

Rules:
- AI must reference real sources: 2 CFR 200, 45 CFR 75, NOFO content.
- Low-confidence, missing citations, or ungrounded output → block + escalate.
- Citation conflicts, regulatory conflicts (2 CFR/45 CFR), FAR/DFARS conflicts → requires_human_review.
- Ungrounded regulatory guidance is never directly shipped.
"""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from app.schemas.hitl import (
    Citation,
    GateId,
    GateOwnerRole,
    GATE_OWNER_ROLES,
    GroundingStatus,
    HumanReviewReason,
)

CONFIDENCE_THRESHOLD = 0.70
FAITHFULNESS_THRESHOLD = 0.80


def compute_grounding_status(
    citations: List[Citation],
    confidence_score: float,
    faithfulness_score: float,
) -> Tuple[GroundingStatus, List[HumanReviewReason]]:
    """
    Determine grounding status and human review reasons.
    Returns (GroundingStatus, [HumanReviewReason, ...]).
    """
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

    if confidence_score < CONFIDENCE_THRESHOLD:
        reasons.append(HumanReviewReason.LOW_CONFIDENCE)

    if faithfulness_score < FAITHFULNESS_THRESHOLD:
        reasons.append(HumanReviewReason.LOW_FAITHFULNESS)

    if not reasons:
        return GroundingStatus.GROUNDED, []

    # Determine primary status — most severe first
    if confidence_score < CONFIDENCE_THRESHOLD:
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
