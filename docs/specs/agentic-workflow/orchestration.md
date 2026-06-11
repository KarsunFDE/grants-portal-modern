# Agentic Workflow — Orchestration & Implementation Decisions

**Scope:** framework choice, durable state design, idempotency, tenant isolation, rollout sequence.

**Not in scope here:** gate contracts, data models, thresholds — see `design-reference.md`.

---

## 1. Framework: LangGraph

**Decision:** Use LangGraph for the multi-gate agentic workflow (REQ-MOD-2).

| Requirement | LangChain LCEL | LangGraph |
|---|---|---|
| HITL pause/resume (up to 10-day SLAs) | Not supported | `interrupt()` + checkpointer |
| Gate state across restarts/redeploys | Not supported | Durable checkpoint |
| Multi-agent panel | Manual | Multi-node subgraph |
| APPROVE/REJECT/RETURN_FOR_FIXES routing | Manual `if/else` | `conditional_edges` |
| Revision loop cap | Manual counter | State field + conditional edge |

**Dependency pins** (`services/ai-orchestrator/requirements.txt`):
```
langgraph>=0.2.0
langchain-aws>=0.2.0
langgraph-checkpoint-mongodb>=0.1.0
```

---

## 2. Durable Workflow State

**Checkpointer:** `MongoDBSaver` keyed by `thread_id = workflow_run_id`.
**Collection:** `workflow_checkpoints`.

```python
from langgraph.checkpoint.mongodb import MongoDBSaver
checkpointer = MongoDBSaver(db["workflow_checkpoints"])
graph = workflow_graph.compile(checkpointer=checkpointer)
```

**`WorkflowState` TypedDict** — every field persisted in checkpoint:

```python
class WorkflowState(TypedDict):
    workflow_run_id: str
    tenant_id: str                          # derived from auth principal — NOT request body
    grant_application_id: str
    corpus_version: str                     # pinned at workflow start, immutable for run
    current_stage: WorkflowStage
    active_gate_id: Optional[GateId]
    gate_states: Dict[str, str]             # gate_id → PENDING|APPROVED|REJECTED|RETURNED_FOR_FIXES|AWARDED|NOT_AWARDED
    gate_decision_ids: List[str]            # ordered GateDecisionRecord ids
    ai_run_ids: Dict[str, str]              # stage → ai_run_id
    revision_loop_counts: Dict[str, int]    # f"{gate_id}:{reviewer_id}" → count
    pending_escalation_ids: List[str]
    sla_timers: Dict[str, str]              # gate_id → ISO assignment timestamp
    triage_result: Optional[dict]           # from /agent/intake-triage
    evidence_snapshot: Optional[dict]       # frozen at gate assignment for audit replay
```

**Resume pattern:**
```python
config = {"configurable": {"thread_id": workflow_run_id}}
graph.invoke(gate_decision_input, config=config)
# No regeneration if checkpoint exists at this thread_id + gate state
```

---

## 3. Programmatic Control Sequence (per AI call)

Order is strict; steps 1 and 2 run in parallel, all others sequential:

1. **[parallel]** Pre-retrieval injection defense: HTML strip → keyword blocklist → system-turn fence check (does not require retrieval outputs)
2. **[parallel with 1]** `retrieval_service.retrieve(query, tenant_id)` — tenant-bound, cache-checked
3. **[after 2]** `validate_before_generation(citations, confidence_score, faithfulness_score, cache_created_at, tenant_id, gate_id)` — requires retrieval outputs; this is NOT parallelizable with step 2
4. Idempotency check — `idempotency_store.check(idempotency_key)` — skip Bedrock if complete
5. `compute_grounding_status(citations, conf, faith, gate_id)` → `GroundingStatus`
6. `should_advance(grounding_status)`:
   - `False` (UNGROUNDED / MISSING_CITATIONS) → create `EscalationRecord`, return blocked response
   - `True` (GROUNDED / LOW_CONFIDENCE) → proceed to Bedrock invocation
7. Bedrock invocation with system-turn fence
8. `GateDecisionRecord` appended on gate resolution
9. SLA timer started on gate assignment; auto-escalation on breach

---

## 4. Idempotency Key

A single `ai_run_id` minted at intake is not a valid idempotency key across stages — a stage-2 cache hit could serve a stage-1 response.

**Per-invocation composite key:**
```python
idempotency_key = sha256(
    f"{workflow_run_id}|{stage}|{gate_id or ''}|{attempt}|"
    f"{prompt_template_version}|{corpus_version}|{input_hash}"
)
# input_hash = sha256(raw_text | query | tenant_id)
```

- `workflow_run_id` — stable across the full workflow run
- `stage` — `WorkflowStage` value at invocation time
- `attempt` — integer; increments on retry; resets on new gate cycle
- `ai_run_id` — UUID v4, display/audit field only (not the dedup key)

---

## 5. revision_loop_count — Durable and Concurrency-Safe

Redis conversation-scope with 24h TTL is not safe: TTL can expire mid-review; concurrent Gate 3 reviewers can race past the cap.

**Storage:** `WorkflowState.revision_loop_counts` (LangGraph checkpoint, MongoDB-backed).

```python
def increment_revision_loop(
    state: WorkflowState, gate_id: str, reviewer_id: str
) -> WorkflowState:
    key = f"{gate_id}:{reviewer_id}"
    current = state["revision_loop_counts"].get(key, 0)
    if current >= 3:
        raise RevisionLoopCapExceeded(gate_id=gate_id, reviewer_id=reviewer_id)
    return {**state, "revision_loop_counts": {**state["revision_loop_counts"], key: current + 1}}
```

LangGraph checkpointer serializes concurrent invocations on the same `thread_id`. No separate locking required.

---

## 6. Tenant Isolation — Auth-Principal Derivation

`tenant_id` MUST be derived from the authenticated principal, not the request body.

```python
# ❌ Current — body-supplied (allows caller to impersonate another tenant)
class EligibilityCheckRequest(BaseModel):
    tenant_id: str

# ✅ Target — auth-derived
def check_eligibility(
    req: EligibilityCheckRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
):
    tenant_id = principal.tenant_id
    if getattr(req, "tenant_id", None) and req.tenant_id != tenant_id:
        raise HTTPException(403, "tenant_id mismatch")
```

`tenant_id` enforced on: every MongoDB read/write, every retrieval call, every cache key, every vector search pre-filter (`{"$in": [tenant_id, "__global__"]}`), every `GateDecisionRecord` and `EscalationRecord`.

---

## 7. Rollout Sequence

1. Pin LangGraph deps in `requirements.txt`
2. Define `WorkflowState` TypedDict; provision `workflow_checkpoints` MongoDB collection
3. Compile `MongoDBSaver` checkpointer; wire `thread_id = workflow_run_id`
4. Replace `invoke_model()` call sites with LangGraph nodes; wire `conditional_edges`
5. Implement composite idempotency key; remove `ai_run_id` as dedup key
6. Move `revision_loop_counts` from Redis to `WorkflowState`
7. Wire intake triage as mandatory pre-Gate-1 LangGraph node
8. Derive `tenant_id` from auth principal; reject body overrides
9. Implement multi-agent COI panel subgraph (`design-reference.md §8`)
10. Implement prior-award PI graph and duplicate-funding check (`design-reference.md §9`)
11. Align `grounding.py` thresholds (done — `CONFIDENCE_PROCEED=0.80`, `FAITHFULNESS_THRESHOLD=0.70`)
12. Fix `/answer-qa` injection gap (Item 9 in `main.py:335`)
13. Add `REVISION_LOOP_EXCEEDED` to `HumanReviewReason` enum (`hitl.py:67`)
14. Run acceptance tests AT-01 through AT-16
15. Remove `legacy_chain.py` post-W2 migration
