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

# Authoritative thresholds — HITL policy table (spec §3, ADR 0009 §1).
# conf >= CONFIDENCE_PROCEED + faith >= FAITHFULNESS_THRESHOLD → GROUNDED (auto-proceed)
# CONFIDENCE_BLOCK <= conf < CONFIDENCE_PROCEED               → LOW_CONFIDENCE (advance with flag)
# conf < CONFIDENCE_BLOCK OR faith < FAITHFULNESS_THRESHOLD   → UNGROUNDED (block)
CONFIDENCE_PROCEED = 0.80       # clean-proceed floor (spec §3, row 1)
CONFIDENCE_THRESHOLD = 0.80     # alias kept for cache_validator.py import compatibility
CONFIDENCE_BLOCK = 0.65         # hard-block ceiling (spec §3, row 3)
FAITHFULNESS_THRESHOLD = 0.70   # faith block threshold (spec §3, row 4) — was 0.80 (swapped)

# Gate-differentiated block thresholds (ADR 0009 §1).
# Values below these trigger UNGROUNDED; values at or above but below CONFIDENCE_PROCEED
# trigger LOW_CONFIDENCE (advance with flag).
GATE_CONFIDENCE_THRESHOLDS: Dict[GateId, float] = {
    GateId.GATE_1: 0.65,   # eligibility/screening — lower bar, human always reviews
    GateId.GATE_2: 0.65,   # COI path is rule-based; threshold is a floor only
    GateId.GATE_3: 0.70,   # factor suggestion — higher bar before human accepts
    GateId.GATE_4: 0.70,   # award decision — higher bar
}
GATE_FAITHFULNESS_THRESHOLDS: Dict[GateId, float] = {
    GateId.GATE_1: 0.65,
    GateId.GATE_2: 0.65,
    GateId.GATE_3: 0.70,
    GateId.GATE_4: 0.70,
}

# GroundingStatus values where workflow ADVANCES (generate + proceed to gate owner).
# LOW_CONFIDENCE advances with EscalationRecord attached; GROUNDED advances clean.
_ADVANCING_STATUSES = {GroundingStatus.GROUNDED, GroundingStatus.LOW_CONFIDENCE}


def compute_grounding_status(
    citations: List[Citation],
    confidence_score: float,
    faithfulness_score: float,
    gate_id: "GateId | None" = None,
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

    conf_block = GATE_CONFIDENCE_THRESHOLDS.get(gate_id, CONFIDENCE_BLOCK) if gate_id else CONFIDENCE_BLOCK
    faith_block = GATE_FAITHFULNESS_THRESHOLDS.get(gate_id, FAITHFULNESS_THRESHOLD) if gate_id else FAITHFULNESS_THRESHOLD

    # Tiered confidence: < block threshold → UNGROUNDED (hard block);
    #                    block <= score < CONFIDENCE_PROCEED → LOW_CONFIDENCE (advance with flag).
    if confidence_score < conf_block:
        reasons.append(HumanReviewReason.UNGROUNDED)
    elif confidence_score < CONFIDENCE_PROCEED:
        reasons.append(HumanReviewReason.LOW_CONFIDENCE)

    if faithfulness_score < faith_block:
        reasons.append(HumanReviewReason.LOW_FAITHFULNESS)

    if not reasons:
        return GroundingStatus.GROUNDED, []

    # Determine primary status — most severe first.
    # UNGROUNDED (hard block) outranks LOW_CONFIDENCE (advance with flag).
    if HumanReviewReason.UNGROUNDED in reasons or faithfulness_score < faith_block:
        return GroundingStatus.UNGROUNDED, reasons
    if HumanReviewReason.CITATION_CONFLICT in reasons:
        return GroundingStatus.CITATION_CONFLICT, reasons
    if HumanReviewReason.REGULATORY_CONFLICT in reasons:
        return GroundingStatus.CITATION_CONFLICT, reasons
    if HumanReviewReason.LOW_CONFIDENCE in reasons:
        return GroundingStatus.LOW_CONFIDENCE, reasons

    return GroundingStatus.UNGROUNDED, reasons


def is_grounded(grounding_status: GroundingStatus) -> bool:
    return grounding_status == GroundingStatus.GROUNDED


def should_advance(grounding_status: GroundingStatus) -> bool:
    """True when workflow should advance (generate + proceed to gate owner).
    GROUNDED → advance clean. LOW_CONFIDENCE → advance with EscalationRecord.
    UNGROUNDED / MISSING_CITATIONS / CITATION_CONFLICT → block.
    Use this (not is_grounded) for the main.py gate-block check.
    """
    return grounding_status in _ADVANCING_STATUSES


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
