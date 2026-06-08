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
    _detect_precedence_conflict,
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
# ADR 0009 §11 — precedence conflict → CITATION_CONFLICT status (not UNGROUNDED)
# ---------------------------------------------------------------------------

class TestPrecedenceConflictStatus:
    """
    REQ: all §11 precedence reason codes must produce GroundingStatus.CITATION_CONFLICT,
    not UNGROUNDED. Prior bug: only legacy CITATION_CONFLICT / REGULATORY_CONFLICT were
    mapped; CFR_NOFO_CONFLICT / AGENCY_POLICY_CONFLICT / AMENDMENT_SUPERSEDES fell through
    to UNGROUNDED, corrupting the audit record.
    """

    def test_cfr_nofo_conflict_yields_citation_conflict_status(self):
        # 2 CFR 200 (rank 1) and NOFO (rank 3) cite the same section → CFR_NOFO_CONFLICT
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="200.205",
                     regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="200.205",
                     regulation="NOFO", tenant_id="t1"),
        ]
        status, reasons = compute_grounding_status(citations, 0.85, 0.90)
        assert HumanReviewReason.CFR_NOFO_CONFLICT in reasons
        assert status == GroundingStatus.CITATION_CONFLICT, (
            f"Expected CITATION_CONFLICT for CFR/NOFO precedence conflict, got {status}"
        )

    def test_agency_policy_conflict_yields_citation_conflict_status(self):
        # NOFO (rank 3) and AGENCY_POLICY (rank 4) cite the same section
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="200.205",
                     regulation="NOFO", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="200.205",
                     regulation="AGENCY_POLICY", tenant_id="t1"),
        ]
        status, reasons = compute_grounding_status(citations, 0.85, 0.90)
        assert HumanReviewReason.AGENCY_POLICY_CONFLICT in reasons
        assert status == GroundingStatus.CITATION_CONFLICT, (
            f"Expected CITATION_CONFLICT for NOFO/AGENCY_POLICY conflict, got {status}"
        )

    def test_far_dfars_conflict_yields_citation_conflict_status(self):
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="52.215-1",
                     regulation="FAR", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="52.215-1",
                     regulation="DFARS", tenant_id="t1"),
        ]
        status, reasons = compute_grounding_status(citations, 0.85, 0.90)
        assert HumanReviewReason.FAR_DFARS_CONFLICT in reasons
        assert status == GroundingStatus.CITATION_CONFLICT, (
            f"Expected CITATION_CONFLICT for FAR/DFARS conflict, got {status}"
        )

    def test_amendment_supersedes_yields_citation_conflict_status(self):
        # Same source_id, two different last_revised dates — supersession conflict
        citations = [
            Citation(chunk_id="c1", source_id="2-CFR-200.205", section="200.205",
                     regulation="2 CFR 200", last_revised="2023-01-01", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="2-CFR-200.205", section="200.205",
                     regulation="2 CFR 200", last_revised="2024-04-22", tenant_id="t1"),
        ]
        status, reasons = compute_grounding_status(citations, 0.85, 0.90)
        assert HumanReviewReason.AMENDMENT_SUPERSEDES in reasons
        assert status == GroundingStatus.CITATION_CONFLICT, (
            f"Expected CITATION_CONFLICT for amendment supersession, got {status}"
        )

    def test_cfr_vs_45cfr_different_sections_no_conflict(self):
        # Different sections — no precedence conflict, no citation conflict
        citations = [
            Citation(chunk_id="c1", source_id="s1", section="200.205",
                     regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", section="75.100",
                     regulation="45 CFR 75", tenant_id="t1"),
        ]
        reason = _detect_precedence_conflict(citations)
        assert reason is None

    def test_far_not_in_grants_precedence_table(self):
        # FAR removed from REGULATION_PRECEDENCE — precedence detector should not fire
        # for a FAR-only citation set (no grants-domain cross-precedence conflict).
        from app.services.grounding import REGULATION_PRECEDENCE
        assert "FAR" not in REGULATION_PRECEDENCE
        assert "DFARS" not in REGULATION_PRECEDENCE


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
        resp = client.post("/eval/factor-suggest", json={"topic": "technical approach", "tenant_id": "tenant-abc"})
        assert resp.status_code == 200
        body = resp.json()
        assert "grounding_status" in body
        assert body["hitl_gate"] == "GATE_3"

    def test_ssdd_draft_returns_grounding_fields(self, client):
        resp = client.post("/eval/ssdd-draft", json={"topic": "funding recommendation", "tenant_id": "tenant-abc"})
        assert resp.status_code == 200
        body = resp.json()
        assert "grounding_status" in body
        assert body["hitl_gate"] == "GATE_4"
