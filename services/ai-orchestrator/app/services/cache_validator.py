"""
Cache revalidation — hitl-plan.txt §Cache Revalidation Policy.

Cache hits are allowed only if they pass citation, confidence, freshness,
and tenant checks immediately before generation and gate input.
If any check fails: block cached output and escalate to the gate owner.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from app.schemas.hitl import Citation, GroundingStatus, HumanReviewReason
from app.services.grounding import CONFIDENCE_THRESHOLD, FAITHFULNESS_THRESHOLD

MAX_CACHE_AGE_HOURS = 24


def validate_before_generation(
    citations: List[Citation],
    confidence_score: float,
    faithfulness_score: float,
    cache_created_at: datetime,
    tenant_id: str,
) -> Tuple[bool, List[HumanReviewReason]]:
    """
    Run all four revalidation checks before generation or gate input:
      1. Citation check
      2. Confidence check
      3. Faithfulness check
      4. Freshness check
      5. Tenant check

    Returns (all_pass, [failure_reasons]).
    """
    reasons: List[HumanReviewReason] = []

    if not citations:
        reasons.append(HumanReviewReason.MISSING_CITATIONS)

    if confidence_score < CONFIDENCE_THRESHOLD:
        reasons.append(HumanReviewReason.LOW_CONFIDENCE)

    if faithfulness_score < FAITHFULNESS_THRESHOLD:
        reasons.append(HumanReviewReason.LOW_FAITHFULNESS)

    age_hours = (datetime.utcnow() - cache_created_at).total_seconds() / 3600
    if age_hours > MAX_CACHE_AGE_HOURS:
        reasons.append(HumanReviewReason.CACHE_REVALIDATION_FAILED)

    for c in citations:
        if c.tenant_id and c.tenant_id != tenant_id:
            reasons.append(HumanReviewReason.TENANT_MISMATCH)
            break

    return len(reasons) == 0, reasons
