"""
Grounding policy tests — hitl-plan.txt §Grounding Policy.

AC5: Ungrounded regulatory output is blocked and escalated.
AC9: Ungrounded items cannot be Gate 1, 3, or 4 input.
AC10: Every grounding escalation records gate_id, owner decision, and rationale.
"""
from __future__ import annotations

import pytest

from app.schemas.hitl import Citation, GroundingStatus, HumanReviewReason
from app.services.grounding import (
    CONFIDENCE_THRESHOLD,
    FAITHFULNESS_THRESHOLD,
    _has_citation_conflict,
    _has_far_dfars_conflict,
    _has_regulatory_conflict,
    compute_grounding_status,
    is_grounded,
)


# ---------------------------------------------------------------------------
# compute_grounding_status
# ---------------------------------------------------------------------------

class TestComputeGroundingStatus:
    def test_no_citations_returns_missing(self):
        status, reasons = compute_grounding_status([], 0.9, 0.9)
        assert status == GroundingStatus.MISSING_CITATIONS
        assert HumanReviewReason.MISSING_CITATIONS in reasons

    def test_good_citations_high_scores_grounded(self):
        citations = [
            Citation(chunk_id="c1", source_id="2-CFR-200.205", section="200.205",
                     regulation="2 CFR 200", tenant_id="t1"),
        ]
        status, reasons = compute_grounding_status(citations, 0.85, 0.90)
        assert status == GroundingStatus.GROUNDED
        assert reasons == []

    def test_low_confidence_low_confidence_status(self):
        citations = [Citation(chunk_id="c1", source_id="src", regulation="2 CFR 200", tenant_id="t1")]
        status, reasons = compute_grounding_status(citations, 0.50, 0.90)
        assert status == GroundingStatus.LOW_CONFIDENCE
        assert HumanReviewReason.LOW_CONFIDENCE in reasons

    def test_low_faithfulness_adds_reason(self):
        citations = [Citation(chunk_id="c1", source_id="src", regulation="2 CFR 200", tenant_id="t1")]
        status, reasons = compute_grounding_status(citations, 0.85, 0.60)
        assert HumanReviewReason.LOW_FAITHFULNESS in reasons

    def test_citation_conflict_triggers_review(self):
        # Same section, different regulation = conflict
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="200.205",
                     regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="200.205",
                     regulation="45 CFR 75", tenant_id="t1"),
        ]
        status, reasons = compute_grounding_status(citations, 0.85, 0.90)
        assert HumanReviewReason.CITATION_CONFLICT in reasons or HumanReviewReason.REGULATORY_CONFLICT in reasons

    def test_far_dfars_conflict_triggers_review(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="52.215-1",
                     regulation="FAR", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="52.215-1",
                     regulation="DFARS", tenant_id="t1"),
        ]
        status, reasons = compute_grounding_status(citations, 0.85, 0.90)
        assert HumanReviewReason.FAR_DFARS_CONFLICT in reasons

    def test_threshold_boundary_exact_confidence(self):
        """Exactly at CONFIDENCE_THRESHOLD — should NOT trigger LOW_CONFIDENCE."""
        citations = [Citation(chunk_id="c1", source_id="s1", regulation="2 CFR 200", tenant_id="t1")]
        status, reasons = compute_grounding_status(citations, CONFIDENCE_THRESHOLD, 0.90)
        assert HumanReviewReason.LOW_CONFIDENCE not in reasons

    def test_below_threshold_triggers_low_confidence(self):
        citations = [Citation(chunk_id="c1", source_id="s1", regulation="2 CFR 200", tenant_id="t1")]
        status, reasons = compute_grounding_status(citations, CONFIDENCE_THRESHOLD - 0.01, 0.90)
        assert HumanReviewReason.LOW_CONFIDENCE in reasons


# ---------------------------------------------------------------------------
# is_grounded
# ---------------------------------------------------------------------------

class TestIsGrounded:
    def test_grounded_status(self):
        assert is_grounded(GroundingStatus.GROUNDED) is True

    def test_ungrounded_status(self):
        assert is_grounded(GroundingStatus.UNGROUNDED) is False

    def test_low_confidence_not_grounded(self):
        assert is_grounded(GroundingStatus.LOW_CONFIDENCE) is False

    def test_missing_citations_not_grounded(self):
        assert is_grounded(GroundingStatus.MISSING_CITATIONS) is False

    def test_citation_conflict_not_grounded(self):
        assert is_grounded(GroundingStatus.CITATION_CONFLICT) is False


# ---------------------------------------------------------------------------
# Conflict detectors
# ---------------------------------------------------------------------------

class TestConflictDetectors:
    def test_no_conflict_same_regulation(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="200.205", regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="200.206", regulation="2 CFR 200", tenant_id="t1"),
        ]
        assert _has_citation_conflict(citations) is False

    def test_citation_conflict_same_section_different_reg(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="200.205", regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="200.205", regulation="45 CFR 75", tenant_id="t1"),
        ]
        assert _has_citation_conflict(citations) is True

    def test_regulatory_conflict_cfr200_cfr75_same_section(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="75.206", regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="75.206", regulation="45 CFR 75", tenant_id="t1"),
        ]
        assert _has_regulatory_conflict(citations) is True

    def test_no_regulatory_conflict_different_sections(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="200.205", regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="75.100", regulation="45 CFR 75", tenant_id="t1"),
        ]
        assert _has_regulatory_conflict(citations) is False

    def test_far_dfars_conflict_detected(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="52.215-1", regulation="FAR", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="52.215-1", regulation="DFARS", tenant_id="t1"),
        ]
        assert _has_far_dfars_conflict(citations) is True

    def test_far_only_no_conflict(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="52.215-1", regulation="FAR", tenant_id="t1"),
        ]
        assert _has_far_dfars_conflict(citations) is False


# ---------------------------------------------------------------------------
# Grounding enforcement via /check-eligibility (AC9 — Gate 1 ungrounded blocked)
# ---------------------------------------------------------------------------

class TestGroundingEnforcementEndpoints:
    def test_check_eligibility_returns_grounding_fields(self, client):
        resp = client.post("/check-eligibility", json={
            "tenant_id": "tenant-abc",
            "grant_application_id": "app-001",
            "applicant_type": "UNIVERSITY",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "grounding_status" in body
        assert "confidence_score" in body
        assert "faithfulness_score" in body
        assert "requires_human_review" in body
        assert "human_review_reasons" in body
        assert isinstance(body["retrieved_sources"], list)
        assert isinstance(body["citation_refs"], list)
        assert isinstance(body.get("citations"), list) or body.get("escalation_id") is not None

    def test_factor_suggest_returns_grounding_fields(self, client):
        resp = client.post("/eval/factor-suggest", json={"topic": "technical approach"})
        assert resp.status_code == 200
        body = resp.json()
        assert "grounding_status" in body
        assert body["hitl_gate"] == "GATE_3"

    def test_ssdd_draft_returns_grounding_fields(self, client):
        resp = client.post("/eval/ssdd-draft", json={"topic": "funding recommendation"})
        assert resp.status_code == 200
        body = resp.json()
        assert "grounding_status" in body
        assert body["hitl_gate"] == "GATE_4"
