# ADR 0005 - HITL Gate and Grounding Decision Contract

Date: 2026-06-02
Status: PROPOSED
Deciders: Pair 1 (grants-management)

## Context

Policy-sensitive outputs require human oversight. The workflow defines four gates where human decisions are mandatory and where grounded evidence must be present before progression.

## Decision

Adopt a strict gate contract for Screening, Peer Review, and Award stages.

1. Gate 1 - Eligibility and Risk Review
- Stage: Screening
- Owner: Grants Officer or Program Officer
- Allowed decisions: approve forward, return for fixes, reject
- Rule: No progression beyond Screening without human decision plus rationale

2. Gate 2 - Conflict of Interest (COI)
- Stage: Peer Review
- Owner: Review Lead
- Allowed decisions: resolve and continue, remove and reassign, override with rationale
- Rule: No scoring starts until COI resolution is recorded by a human

3. Gate 3 - Factor Suggest Acceptance
- Stage: Peer Review
- Owner: Human reviewer
- Allowed decisions: accept, edit, reject
- Rule: AI suggestions are assistive and cannot be used in scoring narrative without human acceptance

4. Gate 4 - Award Decision
- Stage: Award
- Owner: Grants Officer
- Allowed decisions: award, do not award, return to review
- Rule: No unattended award path; persisted human decision and rationale required

5. Grounding policy
- Regulatory/policy outputs must reference authoritative sources: 2 CFR 200, 45 CFR 75, NOFO/amendments.
- If low-confidence, missing citations, ungrounded, or contradictory:
  - block output
  - escalate to named gate owner
- Ungrounded regulatory guidance is never directly shipped.

6. Escalation routing
- Screening grounding failures -> Gate 1 owner
- COI retrieval failures -> Gate 2 owner
- Factor suggestion grounding failures -> Gate 3 owner
- Award package grounding failures -> Gate 4 owner

7. Required decision record fields
- actor_id, actor_role, tenant_id, timestamp, workflow_stage, gate_id, ai_run_id
- decision, rationale, override_flag
- evidence_refs, retrieved_sources, citation_refs
- confidence_score, grounding_status

8. ADR ownership boundary
- This ADR defines gate actors, allowed decisions, stage transitions, and escalation routing.
- Tenant derivation and evidence-tenant matching invariants are defined in ADR 0004.
- Retrieval citation metadata, cache revalidation, and invalidation triggers are defined in ADR 0006.

## Consequences

Positive:
- Deterministic governance for AI-assisted decisions
- Clear accountability and auditability per gate

Tradeoffs:
- Additional operational steps for human reviewers
- More complex API contracts and validation logic

## Rollout

1. Define gate decision schemas in service contracts.
2. Implement hard gate checks prior to workflow stage transition.
3. Add escalation workflow for blocked grounding outcomes.
4. Add tests for all gate block/allow rules and required fields.

## Non-goals

- This ADR does not specify retrieval index internals.
- This ADR does not define model cost optimization settings.

## Related ADRs

- ADR 0004 - Tenant Boundary and HITL Evidence Integrity
- ADR 0006 - Retrieval and Citation Architecture (Bedrock + LangChain v1)
