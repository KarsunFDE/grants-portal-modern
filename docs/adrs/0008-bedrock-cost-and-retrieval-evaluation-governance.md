# ADR 0008 - Bedrock Cost and Retrieval Evaluation Governance

Date: 2026-06-02
Status: PROPOSED
Deciders: Pair 1 (grants-management)

## Context

Budget constraints require explicit controls for model spend and token usage. Retrieval quality must be measured continuously so grounded decisions remain reliable.

## Decision

Adopt mandatory cost and quality governance for Bedrock-backed retrieval and generation.

1. Cost controls
- Bedrock-only model policy remains mandatory.
- Define per-endpoint token and cost budgets.
- Cap retries for low-confidence outcomes; prefer HITL escalation over repeated model calls.
- Monitor prompt/response token usage and per-request estimated cost.

2. Retrieval evaluation controls
- Track retrieval quality metrics for policy-sensitive flows:
  - citation coverage
  - grounding pass rate
  - faithfulness proxy score
  - escalation rate
- Track latency and cost jointly with quality metrics.
- Run the same retrieval evaluation suite in both MongoDB Atlas Local (mongodb/mongodb-atlas-local) and managed Atlas (shared/staging/production) to detect environment drift.

3. Decision quality gates
- Changes to retrieval/generation logic require evaluation run against benchmark set before promotion.
- If quality or cost regresses beyond threshold, release is blocked.

4. Auditability
- Store ai_run_id, model identifier, prompt template version, retrieval metadata, and decision outcome metadata for each gated workflow decision.

5. Operational policy
- No silent retries for blocked grounding cases.
- Low-confidence regulatory outputs escalate to HITL gate owner with rationale.

## Consequences

Positive:
- Spend visibility and predictable operating envelope
- Early detection of quality regressions
- Better change governance and audit posture

Tradeoffs:
- Additional instrumentation and reporting overhead
- Slower release cadence for retrieval changes due to quality gates

## Rollout

1. Define endpoint-level budgets and regression thresholds.
2. Implement telemetry for token/cost/latency/quality fields.
3. Build evaluation harness and baseline benchmark set.
4. Add release checks tied to governance thresholds.

## Non-goals

- This ADR does not define corpus migration sequencing.
- This ADR does not define gate ownership semantics.

## Related ADRs

- ADR 0005 - HITL Gate and Grounding Decision Contract
- ADR 0006 - Retrieval and Citation Architecture (Bedrock + LangChain v1)
- ADR 0007 - MongoDB to MongoDB Atlas Retrieval Migration and Rollback
