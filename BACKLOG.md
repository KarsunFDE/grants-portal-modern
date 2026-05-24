# Stretch Backlog — grants-portal-modern

> Aspirational work items. Pair may pursue any of these for differentiation
> credit in W3+W6 retro. **Not assessed** — rubric does NOT penalize pairs
> who skip the backlog. Items are defendable on the merits (architecture +
> reasoning) even if unbuilt.
>
> Authored by `pair-brownfield-generator` on 2026-05-24 per D-059. Selected
> from `fde-10-week/skills/pair-brownfield-generator/references/stretch-backlog-pool.yml`
> recipe `cohort_1_pair_1_grants` (5 items in recipe — 4 selected for this
> pair, spanning all 4 categories).

## Items (4 total)

### cap-aspect-public-api — Public read-only API for grant-applications (rate limits + API keys)

**Category:** capability
**Difficulty:** substantial
**Aspect fit:** grants-management — grants.gov publishes opportunity-search APIs

Expose a public read-only API for grant_application opportunities (grants.gov-style search
+ award status lookup). Adds API-key auth, rate limiting, OpenAPI spec.

**Why this would be defendable in W3+W6 retro:**

Real federal grants systems publish this — grants.gov has Search API + Opportunity
Detail API. Defendable as "Karsun-customer ask in 2026 — external journalists,
researchers, GAO need programmatic access to award outcomes." Pairs who build it
get to demo external integration; even an ADR + OpenAPI spec is W6-defendable.

---

### arch-saga-multi-step-aspect — Saga pattern for multi-step grant_application workflow

**Category:** architecture
**Difficulty:** substantial
**Aspect fit:** grants-management — application → review → award → disbursement is
a multi-stage workflow with side effects per stage

Implement the multi-stage grant_application workflow (intake → screening → peer-review →
award-decision → disbursement) as a saga with explicit compensation steps. Handles
partial-failure across services. Compensation examples: rollback award if Treasury
disbursement fails; un-publish if OIG flags conflict-of-interest post-decision.

**Why this would be defendable in W3+W6 retro:**

Defends "what happens when step 3 of 5 fails after side effects?" Pairs who build sagas
have rollback semantics to discuss in W3. Grants workflow naturally surfaces compensation
needs (real systems eat this complexity — see SmartGrants / GrantSolutions). Even an
ADR + sequence diagram demonstrates distributed-systems thinking.

---

### gov-aspect-pii-tokenization — PII tokenization for grant_application sensitive fields

**Category:** governance
**Difficulty:** substantial
**Aspect fit:** grants-management — PI SSN/EIN are first-class PII

Replace SSN/EIN/PI-name fields with tokens; lookup-service mediates de-tokenization
with audit trail. Reduces blast-radius of any downstream leak (relevant given
pair-unique debt `obs-pii-in-info-logs` — modernizing both items together gives
defense-in-depth).

**Why this would be defendable in W3+W6 retro:**

Karsun-customer ask in any aspect that handles personal data; grants PIs submit SSN
on the application. Even partial build is W4-Security-day-defendable. Pairs who pair
this with `obs-pii-in-info-logs` get a security-design-thinking retro angle —
defense-in-depth across log + storage layers.

---

### perf-vector-cache-hot-queries — Vector-search result caching for hot grant queries

**Category:** performance
**Difficulty:** modest
**Aspect fit:** grants-management — recurring queries against a precedent corpus
(e.g., "show me Section 8 grants in CA" or "duplicate-funding risk for NIH R01")
hit a stable corpus surface

Cache top-N RAG retrieval results in Redis with TTL + invalidation hooks. Hot queries
hit cache; cold queries flow through to Atlas Vector Search.

**Why this would be defendable in W3+W6 retro:**

Real cost optimization — Bedrock embedding calls have $$$ shape (relevant to W5
AIOps cost discipline). Even unbuilt, the cache-hit-rate projection + TTL/invalidation
design is W5-defendable. Modest build effort makes this a high-ROI stretch item.

---

## Cross-pair note

Other pairs in this cohort have different stretch backlogs — overlap is allowed
(stretch items are aspirational), but each pair's set is curated to their aspect's
fit. See `contract-payment-flow/BACKLOG.md` and `foia-response-pipeline/BACKLOG.md`
for comparison.

## Why this set was chosen

- **Category spread:** all 4 categories represented (capability, architecture,
  governance, performance)
- **Difficulty mix:** 3 substantial + 1 modest — pair has bite-sized entry point
  (`perf-vector-cache-hot-queries`) if substantial items feel out of reach
- **Aspect-affinity weighting:** every item has grants-management in its
  `aspect_affinity` field (or `any`)
- **D-059 pairing with unique debt:** `gov-aspect-pii-tokenization` complements the
  `obs-pii-in-info-logs` pair-unique debt — defense-in-depth conversation natural
  for W6 retro
