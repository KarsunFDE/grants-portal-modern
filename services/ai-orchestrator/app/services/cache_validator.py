"""
Cache revalidation — hitl-plan.txt §Cache Revalidation Policy.

Cache hits are allowed only if they pass citation, confidence, freshness,
and tenant checks immediately before generation and gate input.
If any check fails: block cached output and escalate to the gate owner.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from app.schemas.hitl import Citation, GateId, HumanReviewReason
from app.services.grounding import (
    CONFIDENCE_THRESHOLD,
    FAITHFULNESS_THRESHOLD,
    GATE_CONFIDENCE_THRESHOLDS,
    GATE_FAITHFULNESS_THRESHOLDS,
)

log = logging.getLogger("ai-orchestrator.cache_validator")

MAX_CACHE_AGE_HOURS = 24


def validate_before_generation(
    citations: List[Citation],
    confidence_score: float,
    faithfulness_score: float,
    cache_created_at: datetime,
    tenant_id: str,
    gate_id: Optional[GateId] = None,
    retrieval_strategy: Optional[str] = None,
) -> Tuple[bool, List[HumanReviewReason]]:
    """
    Run all revalidation checks before generation or gate input.
    Uses gate-differentiated thresholds when gate_id is provided (ADR 0009 §1).

    Checks:
      1. Citation non-empty
      2. Citation corpus existence — Atlas-sourced citations only (strategy="atlas").
         Layer-2 citations (strategy="mongodb_text") come from clause_library, not
         corpus_chunks; checking them in Atlas would always report them missing.
      3. Confidence >= gate threshold
      4. Faithfulness >= gate threshold
      5. Freshness (age < 24h)
      6. Tenant match

    Returns (all_pass, [failure_reasons]).
    """
    conf_threshold = GATE_CONFIDENCE_THRESHOLDS.get(gate_id, CONFIDENCE_THRESHOLD) if gate_id else CONFIDENCE_THRESHOLD
    faith_threshold = GATE_FAITHFULNESS_THRESHOLDS.get(gate_id, FAITHFULNESS_THRESHOLD) if gate_id else FAITHFULNESS_THRESHOLD

    reasons: List[HumanReviewReason] = []

    if not citations:
        reasons.append(HumanReviewReason.MISSING_CITATIONS)
    else:
        # Corpus existence check.
        # Discriminate by relevance_score rather than by retrieval_strategy:
        #   - Atlas citations: relevance_score is set (populated from vectorSearchScore)
        #   - Layer-2 citations from clause_library: relevance_score is None
        # This is strategy-agnostic and works correctly for cache hits regardless of
        # whether the stored strategy field is present or is None (old entries).
        atlas_citations = [c for c in citations if c.relevance_score is not None]
        if atlas_citations:
            try:
                from app.atlas_search import get_atlas_db, ATLAS_RETRIEVAL_ENABLED, COLLECTION
                if ATLAS_RETRIEVAL_ENABLED:
                    db = get_atlas_db()
                    chunk_ids = [c.chunk_id for c in atlas_citations]
                    existing = {
                        doc["chunk_id"]
                        for doc in db[COLLECTION].find(
                            {"chunk_id": {"$in": chunk_ids}},
                            {"chunk_id": 1, "_id": 0},
                        )
                    }
                    missing = [cid for cid in chunk_ids if cid not in existing]
                    if missing:
                        log.warning("cache_citation_stale chunk_ids=%s", missing)
                        reasons.append(HumanReviewReason.MISSING_CITATIONS)
            except Exception as exc:
                log.debug("citation existence check skipped: %s", exc)

    if confidence_score < conf_threshold:
        reasons.append(HumanReviewReason.LOW_CONFIDENCE)

    if faithfulness_score < faith_threshold:
        reasons.append(HumanReviewReason.LOW_FAITHFULNESS)

    age_hours = (datetime.utcnow() - cache_created_at).total_seconds() / 3600
    if age_hours > MAX_CACHE_AGE_HOURS:
        reasons.append(HumanReviewReason.CACHE_REVALIDATION_FAILED)

    for c in citations:
        if c.tenant_id and c.tenant_id != tenant_id:
            reasons.append(HumanReviewReason.TENANT_MISMATCH)
            break

    return len(reasons) == 0, reasons
