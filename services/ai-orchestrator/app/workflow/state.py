"""
WorkflowState — durable LangGraph checkpoint state.

Persisted in MongoDB via MongoDBSaver (collection: workflow_checkpoints).
All enum values stored as strings for JSON serialisation.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore


class WorkflowState(TypedDict, total=False):
    # Identity (required — always set at start)
    workflow_run_id: str
    tenant_id: str
    grant_application_id: str
    corpus_version: str

    # Workflow position
    current_stage: str              # WorkflowStage value; default "INTAKE"
    active_gate_id: Optional[str]   # GateId value or None
    completed: bool                 # True when workflow reaches a terminal node

    # Gate tracking
    gate_states: Dict[str, str]     # gate_id → GateDecision value | "PENDING" | "BLOCKED"
    gate_decision_ids: List[str]    # ordered GateDecisionRecord ids
    ai_run_ids: Dict[str, str]      # stage_key → ai_run_id (display/audit only)
    revision_loop_counts: Dict[str, int]  # "GATE_N:actor_token" → count
    pending_escalation_ids: List[str]
    sla_timers: Dict[str, str]      # gate_id → ISO assignment timestamp

    # Application data
    raw_text: Optional[str]
    proposal_id: Optional[str]
    applicant_type: Optional[str]
    applicant_uei: Optional[str]
    applicant_org: Optional[str]
    pi_name: Optional[str]
    assistance_listing_number: Optional[str]
    requested_amount_federal: Optional[float]
    topic: Optional[str]
    constraints: Optional[str]

    # Stage outputs (accumulated)
    triage_result: Optional[dict]
    eligibility_output: Optional[str]
    reviewer_candidates: Optional[list]
    coi_flags: Optional[dict]       # reviewer_id → List[str] flag names
    final_panel: Optional[list]
    factor_suggestion: Optional[str]
    ssdd_narrative: Optional[str]
    denial_reason: Optional[str]


class RevisionLoopCapExceeded(Exception):
    def __init__(self, gate_id: str, loop_key: str, count: int):
        super().__init__(
            f"Revision loop cap (3) exceeded for {gate_id} key={loop_key!r} count={count}"
        )
        self.gate_id = gate_id
        self.loop_key = loop_key
        self.count = count


def make_initial_state(
    tenant_id: str,
    grant_application_id: str,
    *,
    raw_text: Optional[str] = None,
    proposal_id: Optional[str] = None,
    applicant_type: Optional[str] = None,
    applicant_uei: Optional[str] = None,
    applicant_org: Optional[str] = None,
    pi_name: Optional[str] = None,
    assistance_listing_number: Optional[str] = None,
    requested_amount_federal: Optional[float] = None,
    topic: Optional[str] = None,
    constraints: Optional[str] = None,
    corpus_version: str = "v1",
) -> WorkflowState:
    return WorkflowState(
        workflow_run_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        grant_application_id=grant_application_id,
        corpus_version=corpus_version,
        current_stage="INTAKE",
        active_gate_id=None,
        completed=False,
        gate_states={},
        gate_decision_ids=[],
        ai_run_ids={},
        revision_loop_counts={},
        pending_escalation_ids=[],
        sla_timers={},
        raw_text=raw_text,
        proposal_id=proposal_id or grant_application_id,
        applicant_type=applicant_type,
        applicant_uei=applicant_uei,
        applicant_org=applicant_org,
        pi_name=pi_name,
        assistance_listing_number=assistance_listing_number,
        requested_amount_federal=requested_amount_federal,
        topic=topic,
        constraints=constraints,
        triage_result=None,
        eligibility_output=None,
        reviewer_candidates=None,
        coi_flags=None,
        final_panel=None,
        factor_suggestion=None,
        ssdd_narrative=None,
        denial_reason=None,
    )


def increment_revision_loop(state: WorkflowState, gate_id: str) -> Dict[str, int]:
    """
    Increment revision loop counter for gate_id. Raises RevisionLoopCapExceeded at 3.
    Returns updated revision_loop_counts dict (caller merges into state).
    """
    counts = dict(state.get("revision_loop_counts") or {})
    key = gate_id
    current = counts.get(key, 0)
    if current >= 3:
        raise RevisionLoopCapExceeded(gate_id=gate_id, loop_key=key, count=current)
    counts[key] = current + 1
    return counts


def build_idempotency_key(
    workflow_run_id: str,
    stage: str,
    gate_id: Optional[str],
    attempt: int,
    prompt_template_version: str,
    corpus_version: str,
    raw_text: str,
    query: str,
    tenant_id: str,
) -> str:
    input_hash = hashlib.sha256(
        f"{raw_text}|{query}|{tenant_id}".encode()
    ).hexdigest()
    key_src = (
        f"{workflow_run_id}|{stage}|{gate_id or ''}|{attempt}|"
        f"{prompt_template_version}|{corpus_version}|{input_hash}"
    )
    return hashlib.sha256(key_src.encode()).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
