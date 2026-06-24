# ADR 0004 - Tenant Boundary and HITL Evidence Integrity

Date: 2026-06-02
Status: PROPOSED
Deciders: Pair 1 (grants-management)

## Context

The system has explicit multi-tenant requirements and human-in-the-loop (HITL) gate requirements. Tenant isolation and evidence integrity must be enforced consistently across workflow transitions and audit logs.

## Decision

Adopt mandatory tenant-bound validation for all gate decisions and supporting evidence.

1. Tenant derivation
- Tenant identity is authority-derived and cannot be overridden by request payload.

2. Data access enforcement
- All request-scoped reads and writes must apply tenant filters.
- Unscoped query methods are disallowed in runtime request paths.

3. Evidence binding invariant
- Every evidence_ref included in gate input or decision must carry tenant_id.
- A gate decision is invalid if any evidence_ref tenant_id differs from decision tenant_id.

4. Gate integrity
- No workflow stage may bypass required gate approval.
- Gate decision must include actor, role, rationale, and timestamp.

5. Audit durability
- Gate decisions are append-only and durable across restart and pause/resume.
- Logs must be sufficient for OIG reconstruction without external context.

6. ADR ownership boundary
- This ADR defines tenant derivation, tenant enforcement, and evidence-to-decision integrity invariants.
- Gate definitions and escalation routing are defined in ADR 0005.
- Retrieval citation and cache revalidation rules are defined in ADR 0006.

## Consequences

Positive:
- Enforced tenant isolation across decision and evidence lifecycle
- Stronger legal and compliance posture for review and award decisions

Tradeoffs:
- Additional validation and storage overhead
- Broader integration testing matrix for cross-tenant and stale evidence cases

## Rollout

1. Add tenant_id requirements in service/repository request paths.
2. Enforce evidence_ref tenant matching in gate validation.
3. Add blocking and escalation hooks for failed grounding checks.
4. Add cross-tenant isolation and evidence-integrity test coverage.

## Non-goals

- This ADR does not define model/provider strategy.
- This ADR does not define retrieval ranking algorithm details.

## Related ADRs

- ADR 0005 - HITL Gate and Grounding Decision Contract
- ADR 0006 - Retrieval and Citation Architecture (Bedrock + LangChain v1)
