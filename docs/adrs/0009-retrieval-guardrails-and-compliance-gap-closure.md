# ADR 0009 - Retrieval Guardrails and Compliance Gap Closure

Date: 2026-06-04
Status: PROPOSED
Deciders: Pair 1 (grants-management)

## Context

ADRs 0004–0008 establish the retrieval architecture, citation contract, tenant isolation,
HITL gate policy, migration plan, and cost/evaluation governance. A gap review against the
retrieval technical spec (`docs/retrieval-plan.txt`) identified decisions not covered by
any prior ADR. These gaps fall into three categories:

1. **Operational guardrails** — implementation constraints that prevent silent failures:
   gate-differentiated thresholds, embedding failure behavior, index configuration,
   numCandidates floor, static corpus handling, cache key normalization.

2. **Audit and governance completeness** — decisions required for full replay fidelity,
   reranking accountability, regulatory contradiction handling, and source provenance.

3. **Federal compliance** — requirements from 2 CFR 200, 32 CFR Part 2002, FISMA,
   and NIST 800-53 not captured in prior ADRs.

This ADR fills those gaps only. It does not re-state decisions already made in 0004–0008.

## Decision

### 1. Gate-differentiated grounding thresholds

- Gate 1 (Eligibility/Screening): confidence ≥ 0.65, faithfulness ≥ 0.65
- Gate 3 (Factor Suggest): confidence ≥ 0.70, faithfulness ≥ 0.70
- Gate 4 (Award Decision): confidence ≥ 0.70, faithfulness ≥ 0.70
- Gate 2 (COI): no confidence scoring; rule-based path; thresholds do not apply
- `gate_id` MUST be passed to grounding checks; a uniform threshold across all gates is incorrect and will over-escalate Gate 1

### 2. Atlas index required filter fields

- The Atlas vector search index MUST include filter fields: `tenant_id`, `regulation`, `source_id`, and `last_revised`
- `source_id` enables pre-filtering to a specific NOFO or regulatory source without a full index scan
- `last_revised` enables date-range exclusion of superseded amendments inside `$vectorSearch`
- An index missing these fields cannot support the filtering requirements in ADR 0006

### 3. numCandidates floor

- `numCandidates` in every `$vectorSearch` call MUST be `max(150, limit × 15)`
- Deriving `numCandidates` as `limit × 4` is prohibited: at the default limit of 5, this yields 20 candidates, far below the 10× floor required for Recall@5 ≥ 0.80

### 4. Embedding failure behavior

- If the Bedrock embedding API fails, vector search MUST be skipped entirely and the fallback chain drops immediately to Layer 2 (MongoDB text search)
- Returning a zero vector `[0.0 × 1024]` and proceeding with `$vectorSearch` is prohibited; a zero vector yields cosine similarity of 0 against all corpus vectors and produces meaningless rankings that bypass grounding enforcement
- Failure must be logged with `log.error("bedrock_embedding_failed", ...)` before fallback

### 5. Corpus chunk integrity and embedding drift

- `embedding_model_version` MUST be stored in every `corpus_chunks` document at ingest time
- At service startup, the current model ID MUST be compared against the stored value in the index; a mismatch requires full re-ingestion of affected chunks before retrieval is enabled
- If the embedding model version changes, the entire corpus embedding space is incompatible; no partial re-use is permitted

### 6. Global tenant identifier

- The tenant identifier for shared regulatory content (2 CFR 200, 45 CFR 75) MUST be the exact string `"__global__"` in both stored documents and query filters
- No alternate forms (`"global"`, `"GLOBAL"`, `"shared"`) are permitted anywhere in code, ingestion scripts, or seed data
- The `$vectorSearch` OR filter for global content is: `{ "$in": [request_tenant_id, "__global__"] }`

### 7. Cache key normalization

- The retrieval cache key MUST be computed as `SHA256(normalize(query) | tenant_id | corpus_version)` where `normalize = lower().strip()`
- Hashing the raw, un-normalized query string is prohibited; identical queries with differing case or whitespace must resolve to the same cache key

### 8. Static corpus confidence cap

- Retrieval results sourced from the static corpus MUST be capped at `confidence_score = 0.50` and MUST always set `grounding_status = LOW_CONFIDENCE`
- The static corpus is a stale, diagnostic-only path; representing its results with the same confidence formula as Atlas results is prohibited
- This cap triggers HITL escalation and prevents static corpus results from silently passing gate thresholds

### 9. Reranking governance

- Reranking is applied at Gate 3 and Gate 4 only (defined in ADR 0006); this ADR adds the governance constraints
- Max candidates forwarded to the LLM reranker: 30 (dense top-20 + sparse top-10 merged via RRF)
- Max token budget per rerank request: 500 tokens per candidate × 30 candidates; implemented as a hard ceiling, not a suggestion
- Reranker timeout: 2,500 ms hard limit; if exceeded, use the pre-rerank ranked order as the fallback; do not block the request
- Pre-rerank and post-rerank candidate ID lists and scores MUST be persisted for audit replay (see Decision 10)

### 10. Audit replay completeness

- The following fields MUST be persisted for every gated retrieval decision, in addition to the fields required by ADR 0008:
  - retrieval filter object (exact pre-filter passed to `$vectorSearch`)
  - candidate IDs and scores before reranking
  - candidate IDs and scores after reranking
  - reranker model ID and version
  - generation model ID and version
  - prompt template name and version
- An auditor MUST be able to replay any gate decision using `ai_run_id` and decision timestamp as the only inputs, without requiring additional context

### 11. Regulatory contradiction and precedence

- When retrieved citations conflict, the system MUST apply the following precedence order:
  1. 2 CFR Part 200 (authoritative federal standard)
  2. 45 CFR Part 75 (HHS supplement; defers to 2 CFR 200 on shared provisions)
  3. NOFO and amendments (grant-specific; may not contradict CFR)
  4. Agency policy (agency-scoped; may narrow but not override CFR or NOFO)
  5. Approved Q&A (tenant-scoped; lowest precedence)
- Contradictions between sources at different precedence levels MUST trigger `grounding_status = CITATION_CONFLICT` and escalate to the gate owner with an explicit reason code
- The following reason codes are required: `CFR_NOFO_CONFLICT`, `AMENDMENT_SUPERSEDES`, `AGENCY_POLICY_CONFLICT`, `VERSION_MISMATCH`
- If two amendments of the same NOFO are retrieved, the later `last_revised` date wins; the older version MUST be excluded from the citation set

### 12. Source provenance for corpus documents

- Every corpus source file indexed into `corpus_chunks` MUST be accompanied by provenance metadata:
  - `source_uri` — canonical location of the source document (URL or S3 path)
  - `source_checksum` — SHA256 of the source file at ingestion time
  - `approver_id` — identity of the actor who authorized the content for indexing
  - `ingestion_actor` — identity or role that ran the ingest script
- Provenance is stored at the source document level, not per chunk; chunk metadata carries `source_id` as the link
- Content without provenance MUST NOT be indexed; the ingest script must reject unprovenance inputs and log the rejection

### 13. Federal compliance requirements

- **FedRAMP boundary**: all retrieval infrastructure (Atlas, Bedrock) MUST remain within FedRAMP Moderate authorized services; any new infrastructure component requires compliance verification before addition
- **ATO**: the AI retrieval subsystem MUST be within the agency FISMA ATO boundary before production deployment; coordinate with the agency ISSO; the retrieval audit trail satisfies NIST 800-53 AU-3, AU-9, and AU-12 controls
- **Records retention**: `hitl_audit_trail`, `retrieval_invalidation_events`, and `hitl_escalations` are federal grant records subject to 2 CFR 200.334; minimum retention is 3 years from final action on the grant; extend to 7 years when litigation, audit, or claim is pending; legal-hold flag MUST block DELETE on affected records
- **CUI**: NOFO content and applicant Q&A may be Controlled Unclassified Information under 32 CFR Part 2002; corpus content MUST be classified before ingestion; CUI content requires CUI-compliant access controls in place before indexing; public regulatory text (2 CFR 200, 45 CFR 75) is not CUI
- **AWS BAA**: required before ingesting NOFO content from health grant contexts where PHI may enter the query stream

## Consequences

Positive:
- Gate 1 escalation rate reduced by correcting over-strict uniform threshold
- Silent zero-vector failures and static corpus over-confidence eliminated
- Full audit replay becomes possible without external context
- Federal records retention and CUI obligations explicitly assigned to code-level controls

Tradeoffs:
- Additional metadata fields required in corpus ingestion pipeline
- Provenance check adds a pre-ingestion step and rejects content without an approver
- Full rerank audit logging increases storage per gate decision
- Legal-hold logic adds collection-level write control complexity

## Rollout

1. Fix all 8 confirmed code defects (B1–B8 in `docs/retrieval-plan.txt` §Blockers) before enabling `ATLAS_RETRIEVAL_ENABLED=true`
2. Add `embedding_model_version`, `source_uri`, `source_checksum`, `approver_id`, and `ingestion_actor` to `build_document()` in `ingest_corpus.py`
3. Update `ensure_vector_index()` to include `source_id` and `last_revised` filter fields
4. Pass `gate_id` to `compute_grounding_status()`; apply gate-differentiated thresholds
5. Implement reranker governance: candidate cap, token ceiling, timeout, pre/post rank list persistence
6. Add regulatory contradiction reason codes and precedence logic to `grounding.py`
7. Implement legal-hold flag and DELETE guard on audit collections
8. Confirm FedRAMP status of all infrastructure with agency ISSO before production deployment

## Non-goals

- This ADR does not redefine gate actors, allowed decisions, or escalation routing (ADR 0005)
- This ADR does not redefine the migration phase plan or rollback procedure (ADR 0007)
- This ADR does not define the evaluation benchmark harness or cost reporting pipeline (ADR 0008)
- This ADR does not expand post-award retrieval scope

## Related ADRs

- ADR 0004 - Tenant Boundary and HITL Evidence Integrity
- ADR 0005 - HITL Gate and Grounding Decision Contract
- ADR 0006 - Retrieval and Citation Architecture (Bedrock + LangChain v1)
- ADR 0007 - MongoDB to MongoDB Atlas Retrieval Migration and Rollback
- ADR 0008 - Bedrock Cost and Retrieval Evaluation Governance
