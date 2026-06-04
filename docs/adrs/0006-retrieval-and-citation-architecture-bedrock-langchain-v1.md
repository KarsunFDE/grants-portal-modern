# ADR 0006 - Retrieval and Citation Architecture (Bedrock + LangChain v1)

Date: 2026-06-02
Status: PROPOSED
Deciders: Pair 1 (grants-management)

## Context

Policy-sensitive outputs currently depend on stub/static behavior in parts of the AI flow. The target state requires grounded retrieval with citations, confidence controls, and HITL escalation. Constraints require Bedrock-only model usage and LangChain v1 implementation guidance.

## Decision

Adopt a production retrieval architecture with MongoDB Atlas-backed vector retrieval and citation-first responses.

1. Mandatory data source migration
- Retrieval MUST migrate from local/static corpus patterns to MongoDB Atlas-backed retrieval.
- Static corpus responses are not acceptable as the authoritative retrieval path for policy-sensitive generation.
- Atlas is the system of record for retrieval chunks, metadata, and vector index access.
- Migration sequencing, rollback controls, and cutover phases are defined in ADR 0007.

2. Atlas environment model (local + managed)
- Local development MUST run against MongoDB Atlas Local using the Docker image mongodb/mongodb-atlas-local for retrieval integration, schema validation, and index behavior checks.
- Shared/staging/production environments MUST run against managed MongoDB Atlas.
- Local and managed Atlas environments MUST use the same collection schema, index definitions, and tenant metadata contract.

3. Retrieval pattern
- Hybrid retrieval (semantic + lexical/keyword) is required for policy-sensitive queries.
- Reranking is applied on top-k candidates before generation.

4. Citation and metadata contract
- Every generated policy answer must include citation_refs with at least:
  - chunk_id
  - source_id
  - section
  - last_revised
  - tenant_id
- Responses include confidence_score and grounding_status.
- If citations are missing, stale, cross-tenant, or contradictory, block and escalate.

5. Invalidation and cache revalidation
- Re-retrieval is mandatory after invalidation events:
  - application data change
  - NOFO/amendment change
  - policy corpus version change
  - reviewer assignment/COI change
  - award package change
- Cache use is allowed only if citation, confidence, freshness, and tenant checks pass immediately before gate input.

6. Compliance and framework constraints
- Bedrock-only model policy is mandatory.
- LangChain v1 patterns are mandatory for retrieval/generation pipeline components.

## Consequences

Positive:
- Grounded, explainable regulatory answers
- Reduced hallucination risk through mandatory citations and escalation
- Better traceability and compliance posture

Tradeoffs:
- Atlas index and pipeline operational overhead
- Additional latency for hybrid retrieval and reranking

## Rollout

1. Build Atlas-backed ingestion and indexing for corpus sources.
2. Wire retrieval service to Atlas hybrid retrieval path.
3. Enforce citation/confidence/grounding response schema.
4. Remove static corpus as runtime retrieval authority for policy-sensitive flows (allowed only for offline diagnostics/tests).
5. Add integration and acceptance tests for grounding block/escalation rules.

## Non-goals

- This ADR does not define exact per-model token quotas.
- This ADR does not define post-award retrieval expansion scope.

## Related ADRs

- ADR 0005 - HITL Gate and Grounding Decision Contract
- ADR 0007 - MongoDB to MongoDB Atlas Retrieval Migration and Rollback
- ADR 0008 - Bedrock Cost and Retrieval Evaluation Governance
