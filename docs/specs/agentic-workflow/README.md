# Agentic Workflow — Feature Spec

**Status:** PROPOSED
**ADR:** [docs/adrs/0010-agentic-workflow-orchestration-and-context-design.md](../../adrs/0010-agentic-workflow-orchestration-and-context-design.md)
**Service:** `services/ai-orchestrator`

---

## Entry Points

| Question | Document |
|---|---|
| What are the gate contracts, data models, thresholds, and workflow topology? | [design-reference.md](design-reference.md) |
| How is the orchestration framework, durable state, and idempotency implemented? | [orchestration.md](orchestration.md) |
| What tests are required before merge? | [acceptance-tests.md](acceptance-tests.md) |
| Architecture decisions and rationale | [ADR 0010](../../adrs/0010-agentic-workflow-orchestration-and-context-design.md) |
| Visual diagram | [agentic-workflow-visualization.html](../agentic-workflow-visualization.html) |

---

## Authority Hierarchy

On conflict between documents, precedence is:

1. **`design-reference.md`** — normative for contracts, interfaces, gate decisions, thresholds
2. **ADR 0010** — normative for architectural decisions and rationale
3. **`orchestration.md`** — normative for implementation sequencing and framework choices
4. **`acceptance-tests.md`** — normative for test criteria
5. **`agentic-workflow-visualization.html`** — visual reference only; not normative

The visualization diagram is useful for presentations but is not authoritative when it diverges from `design-reference.md`.

---

## Open Questions

- [x] ~~`REVISION_LOOP_EXCEEDED` enum value not yet added to `HumanReviewReason`~~ — added at `hitl.py:83`
- [ ] `/answer-qa` has no retrieval or grounding at all (`main.py:332`) — spec §6.2 requires both; Item 9 injection gap is the secondary issue
- [ ] `/draft-amendment` has no retrieval, grounding, or gate (`main.py:308`) — spec §6.1 requires all three
- [ ] `idempotency_store` not yet implemented in code (`main.py:234,412,497` mints fresh UUID per call)
- [ ] Tenant auth-principal derivation not yet wired (body-supplied `tenant_id` still trusted in `EligibilityCheckRequest`, `FactorSuggestRequest`, `SSDDDraftRequest`)
- [ ] LangGraph dependency not yet pinned in `requirements.txt`
- [ ] Multi-agent COI panel not yet implemented (`/agent/intake-triage` is a single sequential node)
- [ ] Prior-award PI graph data store not yet provisioned

---

## Lifecycle History

| Date | Change |
|---|---|
| 2026-06-09 | Initial planning doc created |
| 2026-06-11 | Adversarial review — 7 HIGH, 5 MED findings addressed; spec split into this folder; legacy files removed |
