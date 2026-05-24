# `grants-portal-modern` — Federal Grants Management (Pair Project, Cohort #1 Pair 1)

> **Karsun-FDE 6-week intensive — Cohort #1 Pair 1 brownfield Pair Project.**
> Derived from [`acquire-gov`](https://github.com/KarsunFDE/acquire-gov) on
> 2026-05-24 via the `pair-brownfield-generator` skill (D-059) and reshaped
> for the `grants-management` aspect (D-045). Anchor real-system:
> **Grants.gov / SmartGrants / GrantSolutions**.
>
> Inherits **all 12 baseline brownfield-debt items** from acquire-gov
> (shared assessment baseline across all 3 pair-projects) PLUS **5
> pair-unique debt items** distinct from Pair 2/3 (per D-059). See
> `docs/brownfield-debt.md` (baseline) + `docs/pair-unique-debt.md`
> (pair-unique) for the full inventory.

## Pair-Project identity

| Field | Value |
|-------|-------|
| Pair number | 1 |
| Cohort | Cohort #1 |
| Aspect | `grants-management` (Federal Grants Management) |
| ADR | `docs/adrs/0001-grants-management-commitment.md` |
| Domain mapping | `domain-mapping.md` |
| Primary entity | `GrantApplication` |
| Review entity | `PeerReview` |
| Corpus | 2 CFR 200 (Uniform Grants Guidance), 45 CFR 75 (HHS supplement) |
| Agent shape | multi-agent (peer-review-panel orchestrator) |
| Sibling pair-projects | [`contract-payment-flow`](https://github.com/KarsunFDE/contract-payment-flow) (Pair 2 — post-award contract administration), [`foia-response-pipeline`](https://github.com/KarsunFDE/foia-response-pipeline) (Pair 3 — FOIA processing) |

## 🔗 Companion repos (KarsunFDE org)

| Repo | What |
|------|------|
| [`acquire-gov`](https://github.com/KarsunFDE/acquire-gov) | The trainer brownfield this repo was derived from. Same 12 baseline debt items + same architecture. |
| [`content`](https://github.com/KarsunFDE/content) | Cohort-facing async content (pre-session, war-room, scenarios) — public |
| [`domain-knowledge`](https://github.com/KarsunFDE/domain-knowledge) | Federal-acquisitions references (FAR/DFARS, OIG/OMB, grants regs) — public |
| `assessment-ec` | Checkpoint exams + audit rubrics — **private, not associate-visible** |
| `training-resources` | Instructor-facing daily walkthroughs + EOD task specs — **private, not associate-visible** |

## Architecture

```
                  ┌──────────────────────┐
                  │  Angular SPA         │   ← grants-officer / PI / reviewer UX
                  │  (frontend/)         │      :4200
                  └──────────┬───────────┘
                             │ HTTPS (REST + SSE)
                  ┌──────────▼───────────┐
                  │  API Gateway         │   ← routes + auth-edge
                  │  (api-gateway/)      │      :8080
                  └──┬───────────┬──┬────┘
                     │           │  │ traceparent
        ┌────────────▼──┐  ┌─────▼──▼─────────┐
        │ GrantApp       │  │ PeerReview       │   ← Spring Boot 2.7.18 (legacy era)
        │ Service        │  │ Service          │      Java 11, javax.*
        │ (Java) :8081   │  │ (Java) :8082     │
        └────┬───────┬───┘  └────┬─────┬───────┘
             │       │           │     │
             │       └─sync REST─┤     │
             │                   │     │
             │   ┌───────────────▼─────▼───┐
             │   │ AI Orchestrator         │   ← Python 3.11 / FastAPI
             │   │ (ai-orchestrator/) :8000│      LangChain v1.0 + Pydantic v2
             │   └────┬────────────────┬───┘
             │        │                │
   ┌─────────▼─────┐  │     ┌──────────▼─────┐
   │ PostgreSQL    │  │     │ AWS Bedrock    │   ← LLM provider (Claude)
   │ :5432         │  │     │ (InvokeModel)  │
   └───────────────┘  │     └────────────────┘
                      │
                ┌─────▼──────────────────┐
                │ MongoDB                │   ← documents +
                │ :27017                 │      Atlas Vector Search (W2)
                └────────────────────────┘
```

## Service inventory

| Path | Service | Tech | Port |
|------|---------|------|------|
| `frontend/` | Angular SPA | Angular 17+ | 4200 |
| `services/api-gateway/` | Auth edge + routing | Spring Boot 2.7.18 + Spring Security 5 + OAuth2 Resource Server | 8080 |
| `services/grant-application-service/` | GrantApplication lifecycle (renamed from solicitation-service) | Spring Boot 2.7.18 + MongoDB | 8081 |
| `services/peer-review-service/` | Peer-review panel coordination (renamed from evaluation-service) | Spring Boot 2.7.18 | 8082 |
| `services/ai-orchestrator/` | LLM/RAG/agent orchestration | Python 3.11 + FastAPI + LangChain v1.0 + Pydantic v2 + boto3 | 8000 |
| `infra/docker/` | Local dev compose stack | Docker Compose | — |
| `infra/github-actions/` | CI/CD workflows | GHA | — |

## Quick start (pair on W1 Thu morning)

```bash
# 1. Clone (pair pulls AFTER instructor confirms the generated repo is on origin/main)
git clone https://github.com/KarsunFDE/grants-portal-modern.git
cd grants-portal-modern

# 2. Copy env template
cp .env.example .env

# 3. Start the stack
cd infra/docker
docker-compose up --build

# 4. Verify
curl http://localhost:8080/actuator/health        # api-gateway
curl http://localhost:8081/actuator/health        # grant-application-service
curl http://localhost:8082/actuator/health        # peer-review-service
curl http://localhost:8000/health                  # ai-orchestrator
open  http://localhost:4200                       # Angular SPA
```

## Brownfield debt — read this before "fixing" anything

This repo has **17 total deliberate brownfield-debt items**: 12 shared with
acquire-gov (assessment-rubric parity baseline) + 5 pair-unique (per D-059
B1 design — distinct from Pair 2/3).

**Do not "fix" these before the cohort inventories them.**

- Baseline items: `docs/brownfield-debt.md` (12 items — also present in
  acquire-gov + sibling pair-projects)
- Pair-unique items: `docs/pair-unique-debt.md` (5 items — distinct from
  Pair 2/3 — see also `domain-mapping.md` §"Pair-unique items")
- Stretch backlog (aspirational, NOT assessed): `BACKLOG.md`

Quick baseline summary (the original 12):

1. JWT signature-skip on `/api/public/*` in api-gateway
2. Audit-log written *after* response in grant-application-service (race on crash)
3. No circuit breaker in peer-review-service → grant-application-service client
4. No structured-output validation in ai-orchestrator (Bedrock raw passthrough)
5. Pre-v1.0 LangChain `LLMChain(...).run(...)` pattern alongside v1.0 patterns
6. Inconsistent correlation-IDs across services (`X-Request-ID` / `correlationId` / `traceId` / absent)
7. `pinecone-client` listed in `requirements.txt` but never imported
8. Frontend `GrantApplicationListComponent` hardcodes `http://localhost:8081/api/grant-applications` (bypasses gateway)
9. No OWASP input sanitization on grant_application `description` (accepts raw HTML)
10. No multi-tenant boundary — `agency_id` in schema but no query filter
11. Dockerfiles use `:latest` base-image tags
12. GHA `ci.yml` has `# TODO: re-enable lint when we have time` (linting commented out)

Pair-unique summary (5 items distinct from Pair 2 + Pair 3):

13. `sec-cors-wildcard-credentials` — CORS bean combines `addAllowedOriginPattern("*")` with `setAllowCredentials(true)` (W4)
14. `rel-db-pool-size-one` — HikariCP `maximum-pool-size: 1` (W5)
15. `obs-pii-in-info-logs` — PI name + SSN-suffix logged at INFO (W5)
16. `ai-bedrock-streaming-unhandled` — only blocking InvokeModel; no streaming surface (W3)
17. `rel-file-upload-local-filesystem` — AttachmentService writes to local /tmp (W5)

## How the pair uses this repo

| Week | Activity |
|------|----------|
| W1 Thu | Pair joins; clones; verifies smoke-test boots. Reads `domain-mapping.md` + `docs/pair-unique-debt.md`. |
| W1 Fri | First LLM PRs land in `services/ai-orchestrator/` against `/draft-grant-application`. |
| W2 | Hybrid RAG over grants-uniform-guidance corpus via Atlas Vector Search. Pre-v1.0 LangChain (Item 5) migrated. |
| W3 | Multi-agent peer-review-panel orchestrator. HITL interrupts. Pair-unique `ai-bedrock-streaming-unhandled` fix lands here. |
| W4 | Brownfield modernization: items 1, 9, 10, 11 + pair-unique `sec-cors-wildcard-credentials`. |
| W5 | AIOps + OTel: items 6 + pair-unique `rel-db-pool-size-one`, `obs-pii-in-info-logs`, `rel-file-upload-local-filesystem`. |
| W6 | Client deliverability: handoff doc, ATO evidence, runbooks. Cross-pair retro vs Pair 2 + Pair 3. |

## Subdirectories

- `services/` — Spring Boot microservices + Python AI orchestrator (each with its own README, Dockerfile, dependency manifest).
- `frontend/` — Angular SPA.
- `infra/docker/` — `docker-compose.yml` + per-service Dockerfiles.
- `infra/github-actions/` — CI/CD workflows.
- `scripts/` — local-dev helpers (seed data, Atlas index bootstrap).
- `docs/` — architecture docs, ADRs, brownfield-debt inventory.
- `docs/adrs/0001-grants-management-commitment.md` — aspect-commitment ADR.
- `domain-mapping.md` — rename trail from acquire-gov → grants-portal-modern.
- `BACKLOG.md` — stretch backlog (aspirational, not assessed).
- `smoke-test-report.md` — generator-produced smoke-test record.

---

Programme spec lives in the team's `fde-10-week/` workspace (private to instructors
during the cohort). This repo is the **code home** the pair clones + builds against.
