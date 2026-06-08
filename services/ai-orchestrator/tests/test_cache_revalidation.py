"""
Cache revalidation tests — hitl-plan.txt §Cache Revalidation Policy.

AC13: Cache hits must pass citation, confidence, freshness, and tenant
      revalidation checks before generation or gate input.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.schemas.hitl import Citation, HumanReviewReason
from app.services.cache_validator import MAX_CACHE_AGE_HOURS, validate_before_generation
from app.services.grounding import CONFIDENCE_THRESHOLD, FAITHFULNESS_THRESHOLD


def _citation(tenant_id="tenant-abc"):
    return Citation(
        chunk_id="c1",
        source_id="2-CFR-200.205",
        section="200.205",
        regulation="2 CFR 200",
        tenant_id=tenant_id,
    )


class TestCacheRevalidation:
    def test_all_checks_pass_returns_valid(self):
        citations = [_citation()]
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=0.85,
            faithfulness_score=0.90,
            cache_created_at=datetime.utcnow() - timedelta(hours=1),
            tenant_id="tenant-abc",
            retrieval_strategy="static",  # known strategy — skips Atlas existence check
        )
        assert valid is True
        assert reasons == []

    # ------- Citation check -------

    def test_missing_citations_fails(self):
        valid, reasons = validate_before_generation(
            citations=[],
            confidence_score=0.85,
            faithfulness_score=0.90,
            cache_created_at=datetime.utcnow(),
            tenant_id="tenant-abc",
        )
        assert valid is False
        assert HumanReviewReason.MISSING_CITATIONS in reasons

    # ------- Confidence check -------

    def test_low_confidence_fails(self):
        citations = [_citation()]
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=CONFIDENCE_THRESHOLD - 0.01,
            faithfulness_score=0.90,
            cache_created_at=datetime.utcnow(),
            tenant_id="tenant-abc",
        )
        assert valid is False
        assert HumanReviewReason.LOW_CONFIDENCE in reasons

    def test_exact_confidence_threshold_passes(self):
        citations = [_citation()]
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=CONFIDENCE_THRESHOLD,
            faithfulness_score=0.90,
            cache_created_at=datetime.utcnow(),
            tenant_id="tenant-abc",
        )
        assert HumanReviewReason.LOW_CONFIDENCE not in reasons

    # ------- Faithfulness check -------

    def test_low_faithfulness_fails(self):
        citations = [_citation()]
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=0.85,
            faithfulness_score=FAITHFULNESS_THRESHOLD - 0.01,
            cache_created_at=datetime.utcnow(),
            tenant_id="tenant-abc",
        )
        assert valid is False
        assert HumanReviewReason.LOW_FAITHFULNESS in reasons

    # ------- Freshness check -------

    def test_stale_cache_fails(self):
        citations = [_citation()]
        stale_time = datetime.utcnow() - timedelta(hours=MAX_CACHE_AGE_HOURS + 1)
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=0.85,
            faithfulness_score=0.90,
            cache_created_at=stale_time,
            tenant_id="tenant-abc",
        )
        assert valid is False
        assert HumanReviewReason.CACHE_REVALIDATION_FAILED in reasons

    def test_fresh_cache_passes(self):
        citations = [_citation()]
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=0.85,
            faithfulness_score=0.90,
            cache_created_at=datetime.utcnow() - timedelta(hours=MAX_CACHE_AGE_HOURS - 1),
            tenant_id="tenant-abc",
            retrieval_strategy="static",  # known strategy — skips Atlas existence check
        )
        assert HumanReviewReason.CACHE_REVALIDATION_FAILED not in reasons

    # ------- Tenant check -------

    def test_tenant_mismatch_in_citations_fails(self):
        citations = [_citation(tenant_id="tenant-WRONG")]
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=0.85,
            faithfulness_score=0.90,
            cache_created_at=datetime.utcnow(),
            tenant_id="tenant-abc",
        )
        assert valid is False
        assert HumanReviewReason.TENANT_MISMATCH in reasons

    def test_citation_without_tenant_id_skips_check(self):
        """Citations with no tenant_id don't trigger the tenant check."""
        citations = [Citation(chunk_id="c1", source_id="s1", tenant_id=None)]
        valid, reasons = validate_before_generation(
            citations=citations,
            confidence_score=0.85,
            faithfulness_score=0.90,
            cache_created_at=datetime.utcnow(),
            tenant_id="tenant-abc",
        )
        assert HumanReviewReason.TENANT_MISMATCH not in reasons

    # ------- Multiple failures -------

    def test_multiple_failures_all_reported(self):
        valid, reasons = validate_before_generation(
            citations=[],  # missing citations
            confidence_score=0.50,  # low confidence
            faithfulness_score=0.50,  # low faithfulness
            cache_created_at=datetime.utcnow() - timedelta(hours=MAX_CACHE_AGE_HOURS + 5),
            tenant_id="tenant-abc",
        )
        assert valid is False
        assert HumanReviewReason.MISSING_CITATIONS in reasons
        assert HumanReviewReason.LOW_CONFIDENCE in reasons
        assert HumanReviewReason.LOW_FAITHFULNESS in reasons
        assert HumanReviewReason.CACHE_REVALIDATION_FAILED in reasons
