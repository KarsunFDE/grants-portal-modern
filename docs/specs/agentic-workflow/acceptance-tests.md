# Agentic Workflow — Acceptance Tests

**Scope:** pass/fail criteria for merge readiness. All AT-01 through AT-16 must pass before `feature/agentic-systems` merges to main.

**Not in scope here:** unit test specifics, fixture setup, CI job config — see `orchestration.md §7` for rollout sequence.

---

## Test Matrix

| ID | Area | Gate/Stage | Scenario | Pass Criterion |
|----|------|-----------|----------|----------------|
| AT-01 | Grounding | GATE_1 | `confidence_score = 0.82`, `faithfulness_score = 0.75` | `GroundingStatus.GROUNDED`; no `EscalationRecord`; advance to Gate 1 |
| AT-02 | Grounding | GATE_1 | `confidence_score = 0.70`, `faithfulness_score = 0.75` | `GroundingStatus.LOW_CONFIDENCE`; `EscalationRecord` created; still advance to gate owner |
| AT-03 | Grounding | GATE_1 | `confidence_score = 0.60`, `faithfulness_score = 0.75` | `GroundingStatus.UNGROUNDED`; gate BLOCKED; no Bedrock invocation |
| AT-04 | Grounding | GATE_3/4 | `confidence_score = 0.67`, `faithfulness_score = 0.72` | BLOCKED at GATE_3/4 (`conf_block = 0.70`); GATE_1 would allow same score (0.65 threshold) |
| AT-05 | HITL Gate | GATE_1 | Officer submits `RETURN_FOR_FIXES` | Revision counter increments; AI retries retrieval; loop terminates at count = 3 |
| AT-06 | HITL Gate | GATE_1 | Revision counter reaches 3; officer attempts 4th `RETURN_FOR_FIXES` | Request rejected; escalation to supervisor required (`override_flag = True`) |
| AT-07 | HITL Gate | GATE_2 | `coi_flags` non-empty for one reviewer | LangGraph `interrupt()` fires; workflow pauses at Gate 2; gate owner sees COI report |
| AT-08 | HITL Gate | GATE_2 | All proposed reviewers have COI | `EscalationRecord(reason="reviewer_pool_exhausted")`; escalated to Grants Officer (not Review Lead) |
| AT-09 | HITL Gate | GATE_4 | Officer submits `DO_NOT_AWARD` | Denial record created; workflow terminates; no revision path available |
| AT-10 | HITL Gate | GATE_4 | Officer submits `RETURN_TO_REVIEW` | Workflow state transitions back to GATE_3 stage; new `GateDecisionRecord` cycle begins |
| AT-11 | Idempotency | Any stage | Same composite key submitted twice | Second call returns cached result; Bedrock not re-invoked |
| AT-12 | Tenant isolation | Retrieval | `tenant_id` in request body differs from auth principal `tenant_id` | HTTP 403 returned; no retrieval executed |
| AT-13 | QA Tier 1 | `SCREENING` | `POST /answer-qa` without `grant_application_id`; answer grounded | Answer returned with disclaimer; no gate created |
| AT-14 | QA Tier 2 | `PEER_REVIEW` | `POST /answer-qa` with `grant_application_id`; question references award amount; active gate exists | Answer withheld; `EscalationRecord` created for active gate owner |
| AT-15 | Durability | GATE_3 | Orchestrator process restarts mid-workflow | LangGraph resumes from MongoDB checkpoint; no state loss; gate decisions not replayed |
| AT-16 | SLA breach | GATE_4 | Gate 4 assignment timestamp exceeds 10 business days with no decision | Auto-escalation triggered; supervisor notified; `EscalationRecord` created |

---

## Preconditions for All Tests

- `WorkflowState` checkpointer connected to test MongoDB instance (not shared with prod)
- Bedrock client in stub mode (`AWS_DEFAULT_REGION` unset or `BEDROCK_STUB=true`)
- Auth principal fixture provides `tenant_id = "test-tenant-001"`
- `corpus_version` pinned to `"test-corpus-v1"` at workflow start

---

## AT-04 Elaboration — Gate-Differentiated Thresholds

Gate 1 block threshold = 0.65; Gate 3/4 block threshold = 0.70.

```
Input:  confidence_score = 0.67, faithfulness_score = 0.72
At GATE_1:  0.67 >= 0.65 → LOW_CONFIDENCE → advance (with flag)
At GATE_3:  0.67 < 0.70  → UNGROUNDED    → BLOCK
```

Both branches must be asserted by AT-04. Single test, two invocations with `gate_id` parameter switched.

---

## AT-05/AT-06 Elaboration — Revision Loop Cap

```python
# AT-05: counter increments correctly
for i in range(1, 4):
    state = increment_revision_loop(state, gate_id="GATE_1", reviewer_id="officer-001")
    assert state["revision_loop_counts"]["GATE_1:officer-001"] == i

# AT-06: cap enforced on 4th attempt
with pytest.raises(RevisionLoopCapExceeded):
    increment_revision_loop(state, gate_id="GATE_1", reviewer_id="officer-001")
```

---

## AT-11 Elaboration — Idempotency

```python
key = idempotency_key(
    workflow_run_id="wfr-abc", stage="SCREENING", gate_id="GATE_1",
    attempt=1, prompt_template_version="v2", corpus_version="test-corpus-v1",
    input_hash=sha256("eligibility query|test-tenant-001")
)
result_1 = invoke_with_idempotency(key, prompt)  # hits Bedrock stub
result_2 = invoke_with_idempotency(key, prompt)  # cache hit
assert result_1 == result_2
assert bedrock_stub.call_count == 1              # only one actual invocation
```

---

## AT-15 Elaboration — Durability / Resume

```python
# Simulate restart mid-Gate 3
config = {"configurable": {"thread_id": "wfr-restart-test"}}
graph.invoke({"input": "factor scoring prompt"}, config=config)
# Interrupt after GATE_3 fires — kill process here in test
# Resume
graph.invoke({"gate_decision": GateDecision.ACCEPT}, config=config)
# Assert: no duplicate GateDecisionRecord, state at GATE_4 stage
```

---

## Traceability

| Spec Section | Test IDs |
|---|---|
| `design-reference.md §3` (grounding) | AT-01, AT-02, AT-03, AT-04 |
| `design-reference.md §2` (gate contracts) | AT-05, AT-06, AT-07, AT-08, AT-09, AT-10, AT-16 |
| `orchestration.md §4` (idempotency) | AT-11 |
| `orchestration.md §6` (tenant isolation) | AT-12 |
| `design-reference.md §6.2` (QA tiers) | AT-13, AT-14 |
| `orchestration.md §2` (durable state) | AT-15 |
