# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Critical: Brownfield Debt System

**Do not fix the 17 deliberate brownfield-debt items** unless the cohort week explicitly schedules it.

- Baseline items (12): `docs/brownfield-debt.md` — shared with sibling pair-projects, scheduled W2–W6
- Pair-unique items (5): `docs/pair-unique-debt.md` — distinct to this pair, each has a scheduled unlock week

Items are locked by failing tests tagged `brownfield_debt`. The debt-enforcement CI workflow (`debt-enforcement.yml`) asserts these tests still fail. Fixing a locked item before its unlock week breaks enforcement CI.

Quick reference — pair-unique items and their unlock weeks:

| ID | Location | Week |
|----|----------|------|
| `sec-cors-wildcard-credentials` | `SecurityConfig.java` | W4 |
| `rel-db-pool-size-one` | `application.yml` (grant-application-service) | W5 |
| `obs-pii-in-info-logs` | `GrantApplicationService.java` | W5 |
| `ai-bedrock-streaming-unhandled` | `bedrock_client.py` | W3 |
| `rel-file-upload-local-filesystem` | `AttachmentService.java` | W5 |

## Commands

### Full stack
```bash
cd infra/docker && docker-compose up --build
```

Health checks: `:8080/actuator/health`, `:8081/actuator/health`, `:8082/actuator/health`, `:8000/health`, `:4200`

### Java services (api-gateway, grant-application-service, peer-review-service)
```bash
cd services/<service-name>
mvn -B -DskipTests package        # build
mvn -B test                        # all tests
mvn -B test -Dtest=<TestClass>    # single test class
```

### Python AI orchestrator
```bash
cd services/ai-orchestrator
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest tests/                     # default (excludes locked debt tests)
pytest tests/ -m brownfield_debt  # run locked-failing tests (expect failures)
```

### Angular frontend
```bash
cd frontend
npm ci && npm start    # dev server :4200
npm run build          # production build
npm test               # unit tests
```

### Debt enforcement (mirrors CI)
```bash
make verify-debt-locks    # schema-validate + assert locked tests still fail
make run-locked-tests     # assert brownfield_debt tests still fail
```

## Architecture

```
Angular SPA (:4200)
    └─ HTTPS/REST/SSE
API Gateway (:8080) — auth edge, Spring Security 5, OAuth2 resource server
    ├─ Grant Application Service (:8081) — GrantApplication lifecycle, MongoDB + PostgreSQL
    ├─ Peer Review Service (:8082)       — peer-review-panel coordination
    └─ AI Orchestrator (:8000)           — FastAPI, LangChain v1.0, AWS Bedrock (Claude)
```

**Java services**: Spring Boot 2.7.18, Java 11, `javax.*` (not `jakarta.*` — legacy era, intentional).

**AI Orchestrator** (`services/ai-orchestrator/app/`):
- `main.py` — FastAPI endpoints: `/draft-grant-application`, `/check-eligibility`, `/draft-amendment`, `/answer-qa`, `/rag/clause-search`, `/eval/factor-suggest`, `/eval/ssdd-draft`, `/agent/intake-triage`
- `bedrock_client.py` — `invoke_model()` wraps boto3 `InvokeModel`; auto-stubs when no AWS creds present
- `legacy_chain.py` — pre-v1.0 LangChain `LLMChain(...).run(...)` (Item 5, cohort migrates W2)
- Default model: `anthropic.claude-3-7-sonnet-20250219-v1:0` (override via `BEDROCK_MODEL_ID` env var)

**Primary entities**: `GrantApplication`, `PeerReview`. Domain corpus: 2 CFR 200 (Uniform Grants Guidance), 45 CFR 75 (HHS supplement).

**HITL gates**: AI endpoints return a `hitl_gate` field indicating human-in-the-loop approval required before advancing grant application status.

## Key conventions

- `pinecone-client` in `requirements.txt` is intentionally unused (Item 7 — do not remove until W2)
- Lint is commented out in `ci.yml` with `# TODO: re-enable` (Item 12 — load-bearing brownfield, do not fix until W4)
- `rag/clause-search` returns a shaped stub; Atlas Vector Search wires in during W2
- Correlation IDs are inconsistent across services by design (Item 6 — fixed W5 OTel work)
- `docs/debt-lockfile.yml` is validated by `.github/scripts/verify-debt-lockfile.py`; never remove `brownfield_debt` markers without the corresponding debt-fix PR
