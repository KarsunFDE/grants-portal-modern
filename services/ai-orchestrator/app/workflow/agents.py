"""
Multi-agent peer-review panel (design-reference.md §8).

Three agents — none may self-resolve COI:
  1. reviewer-assignment-agent  — suggests ranked reviewers (Bedrock)
  2. coi-check-agent            — deterministic COI rules (NOT AI judgment)
  3. panel-confirmation-agent   — confirms final composition + audit record (Bedrock)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

log = logging.getLogger("ai-orchestrator.agents")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ReviewerCandidate(BaseModel):
    reviewer_id: str
    name: str
    org: str
    expertise_areas: List[str]
    expertise_score: float
    co_pi_names: List[str] = []     # names co-authored with within 48 months
    competing_nofo_ids: List[str] = []


class COIFlag(BaseModel):
    reviewer_id: str
    rule: str   # "ORG_MATCH" | "CO_AUTHOR" | "COMPETING_APPLICATION" | "RELATIONSHIP"
    detail: str


# ---------------------------------------------------------------------------
# Agent 1: reviewer assignment
# ---------------------------------------------------------------------------

def run_reviewer_assignment(
    program_area: str,
    required_expertise: List[str],
    tenant_id: str,
    grant_application_id: str,
    reviewer_pool: Optional[List[dict]] = None,
) -> List[ReviewerCandidate]:
    """
    Suggests ranked reviewers for a grant application.
    Uses Bedrock to parse program area + expertise requirements.
    Returns deterministically-ranked list (expertise_score desc).
    """
    from app.bedrock_client import invoke_model

    prompt = (
        f"Suggest 5 peer reviewers for a federal grant in program area: {program_area}. "
        f"Required expertise: {', '.join(required_expertise)}. "
        f"Return a JSON array with fields: reviewer_id, name, org, expertise_areas, "
        f"expertise_score (0.0-1.0), co_pi_names, competing_nofo_ids."
    )
    result = invoke_model(
        prompt,
        system="You suggest qualified peer reviewers for federal grant merit review panels.",
    )

    # Parse Bedrock stub or real response into ReviewerCandidate objects.
    # Stub returns plain text; produce deterministic fallback candidates.
    candidates = _parse_reviewer_candidates(result.get("body", ""), grant_application_id)
    candidates.sort(key=lambda c: c.expertise_score, reverse=True)
    log.info(
        "reviewer_assignment grant=%s candidates=%d",
        grant_application_id,
        len(candidates),
    )
    return candidates


def _parse_reviewer_candidates(body: str, application_id: str) -> List[ReviewerCandidate]:
    """Parse Bedrock response into ReviewerCandidate list. Falls back to deterministic stubs."""
    import json
    import re

    json_match = re.search(r'\[.*?\]', body, re.DOTALL)
    if json_match:
        try:
            raw = json.loads(json_match.group())
            return [ReviewerCandidate(**r) for r in raw]
        except Exception:
            pass

    # Deterministic stub — 3 reviewers derived from application_id
    suffix = application_id[-4:] if len(application_id) >= 4 else "0001"
    return [
        ReviewerCandidate(
            reviewer_id=f"rev-{suffix}-A",
            name="Dr. A. Reviewer",
            org="University Research Institute",
            expertise_areas=["grants management", "federal compliance"],
            expertise_score=0.88,
        ),
        ReviewerCandidate(
            reviewer_id=f"rev-{suffix}-B",
            name="Dr. B. Expert",
            org="National Policy Center",
            expertise_areas=["2 CFR 200", "program evaluation"],
            expertise_score=0.82,
        ),
        ReviewerCandidate(
            reviewer_id=f"rev-{suffix}-C",
            name="Dr. C. Scholar",
            org="Federal Advisory Group",
            expertise_areas=["risk assessment", "merit review"],
            expertise_score=0.76,
        ),
    ]


# ---------------------------------------------------------------------------
# Agent 2: COI check (deterministic — NOT AI judgment)
# ---------------------------------------------------------------------------

def run_coi_check(
    candidates: List[ReviewerCandidate],
    applicant_uei: Optional[str],
    applicant_org: Optional[str],
    pi_name: Optional[str],
    nofo_id: Optional[str] = None,
) -> Dict[str, List[COIFlag]]:
    """
    Applies 4 deterministic COI rules (design-reference.md §8):
      1. Reviewer org matches applicant org
      2. Reviewer co-authored with PI within 48 months
      3. Reviewer submitted competing application to same NOFO
      4. Relationship flag (placeholder — requires external HR data)
    Returns {reviewer_id: [COIFlag, ...]}; empty list = no COI.
    """
    result: Dict[str, List[COIFlag]] = {}

    for candidate in candidates:
        flags: List[COIFlag] = []

        # Rule 1: Org match
        if (
            applicant_org
            and candidate.org.lower().strip() == applicant_org.lower().strip()
        ):
            flags.append(COIFlag(
                reviewer_id=candidate.reviewer_id,
                rule="ORG_MATCH",
                detail=f"Reviewer org {candidate.org!r} matches applicant org {applicant_org!r}",
            ))

        # Rule 2: Co-author with PI
        if pi_name and candidate.co_pi_names:
            pi_lower = pi_name.lower().strip()
            for co_name in candidate.co_pi_names:
                if _name_matches(pi_lower, co_name.lower().strip()):
                    flags.append(COIFlag(
                        reviewer_id=candidate.reviewer_id,
                        rule="CO_AUTHOR",
                        detail=f"Reviewer co-authored with PI {pi_name!r} within 48 months",
                    ))
                    break

        # Rule 3: Competing application to same NOFO
        if nofo_id and nofo_id in candidate.competing_nofo_ids:
            flags.append(COIFlag(
                reviewer_id=candidate.reviewer_id,
                rule="COMPETING_APPLICATION",
                detail=f"Reviewer submitted competing application to NOFO {nofo_id!r}",
            ))

        if flags:
            result[candidate.reviewer_id] = flags

    log.info(
        "coi_check candidates=%d flagged=%d",
        len(candidates),
        len(result),
    )
    return result


def _name_matches(a: str, b: str) -> bool:
    """Fuzzy name match: exact or edit-distance ≤ 2."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 3:
        return False
    return _levenshtein(a, b) <= 2


def _levenshtein(s: str, t: str) -> int:
    if len(s) > len(t):
        s, t = t, s
    row = list(range(len(s) + 1))
    for j, c2 in enumerate(t):
        new_row = [j + 1]
        for i, c1 in enumerate(s):
            new_row.append(min(row[i] + (c1 != c2), row[i + 1] + 1, new_row[-1] + 1))
        row = new_row
    return row[-1]


# ---------------------------------------------------------------------------
# Agent 3: panel confirmation
# ---------------------------------------------------------------------------

def run_panel_confirmation(
    final_reviewers: List[ReviewerCandidate],
    gate_decision: str,
    gate_decision_id: str,
    tenant_id: str,
    grant_application_id: str,
) -> dict:
    """
    Confirms final panel composition and creates audit record.
    Uses Bedrock to generate confirmation summary.
    """
    from app.bedrock_client import invoke_model

    reviewer_names = ", ".join(r.name for r in final_reviewers)
    result = invoke_model(
        f"Confirm peer review panel for grant {grant_application_id}. "
        f"Reviewers: {reviewer_names}. Gate decision: {gate_decision}.",
        system="You confirm peer-review panel composition for federal grant merit review.",
    )
    panel_record = {
        "grant_application_id": grant_application_id,
        "tenant_id": tenant_id,
        "reviewers": [r.model_dump() for r in final_reviewers],
        "gate_decision_id": gate_decision_id,
        "gate_decision": gate_decision,
        "confirmation_summary": result.get("body", ""),
        "panel_size": len(final_reviewers),
    }
    log.info(
        "panel_confirmation grant=%s reviewers=%d",
        grant_application_id,
        len(final_reviewers),
    )
    return panel_record
