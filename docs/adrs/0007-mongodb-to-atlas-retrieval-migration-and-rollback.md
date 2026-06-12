# ADR 0007 - MongoDB to MongoDB Atlas Retrieval Migration and Rollback

Date: 2026-06-02
Status: PROPOSED
Deciders: Pair 1 (grants-management)

## Context

Application data continuity must be preserved while retrieval capability migrates to Atlas vector search. The migration must avoid data loss, preserve tenant boundaries, and support rollback.

## Decision

Adopt a phased migration where retrieval authority moves to Atlas while operational application continuity is preserved.

Scope note: this ADR defines migration execution, cutover gates, and rollback. Retrieval response contract requirements are defined in ADR 0006.

1. Migration requirement
- We MUST migrate retrieval from local/static corpus behavior to MongoDB Atlas-backed retrieval.
- Atlas retrieval is required for policy-sensitive generation and HITL gate input.
- Static corpus paths may remain for offline diagnostics only, not production retrieval decisions.

2. Environment requirement (local Atlas first)
- Local development MUST use MongoDB Atlas Local via the Docker image mongodb/mongodb-atlas-local for retrieval development and verification.
- Managed MongoDB Atlas is required for shared/staging/production retrieval workloads.
- No environment may treat static corpus as the primary retrieval authority for policy-sensitive paths.

3. Phase plan
- Phase A: Inventory and schema mapping of current corpus, metadata, tenant tags, and regulatory source lineage.
- Phase B: Build and validate retrieval against local Atlas target.
- Phase C: Dual-write/dual-index ingestion into managed Atlas while preserving current application persistence behavior.
- Phase D: Read shadowing and parity verification (managed Atlas results compared to current outputs).
- Phase E: Cutover retrieval reads to Atlas.
- Phase F: Retire static retrieval path from production decision flow.

4. Data continuity and integrity
- Preserve source provenance, last_revised, tenant_id, and document lineage across migration.
- Enforce tenant filters in ingestion and query paths.

5. Rollback strategy
- Feature flag controls retrieval backend selection.
- If cutover fails acceptance criteria, revert read path to previous safe mode while preserving Atlas writes for diagnosis.
- Incident record must capture failure mode, blast radius, and remediation.

6. Acceptance gates for cutover
- Citation completeness threshold met
- Grounding block/escalation behavior validated
- Tenant isolation tests pass
- Cost and latency within budget targets

## Consequences

Positive:
- Controlled, auditable migration with lower operational risk
- Clear rollback guardrails

Tradeoffs:
- Temporary complexity from dual-path operation
- Additional test and observability work before final cutover

## Rollout

1. Define migration feature flags and environment configuration.
2. Stand up MongoDB Atlas Local (mongodb/mongodb-atlas-local) for developer workflows and CI integration tests.
3. Build ingestion pipeline into Atlas with metadata parity checks.
4. Execute shadow reads and compare relevance/citation outcomes.
5. Perform staged cutover by endpoint category.
6. Remove production reliance on static corpus retrieval after acceptance.

## Non-goals

- This ADR does not define exact embedding model selection.
- This ADR does not replace application primary data store architecture in one step.

## Related ADRs

- ADR 0006 - Retrieval and Citation Architecture (Bedrock + LangChain v1)
- ADR 0008 - Bedrock Cost and Retrieval Evaluation Governance
