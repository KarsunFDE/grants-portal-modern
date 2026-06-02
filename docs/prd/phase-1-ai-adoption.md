# grants-portal-modern — Phase 1 PRD: AI Adoption

| | |
|---|---|
| **Product** | `grants-portal-modern` — federal grants-management platform (application → award) |
| **Aspect** | `grants-management` (anchor: Grants.gov) |
| **Phase** | Phase 1 — AI Adoption |
| **Status** | Living draft — refined in planning sessions |
| **Owner** | Pair 1 |
| **Last updated** | 2026-05-28 |

> **This is a PRD, not a plan.** It states the problem, goals, boundaries, and
> what "done" looks like — the *what* and *why*. The *how* (endpoints, schemas,
> retrieval approach, gate primitives, thresholds) is left to the planning
> sessions and captured as ADRs. Requirements will change as we learn; material
> changes land in the [Change log](#13-change-log), and the
> [Open questions](#11-open-questions--to-plan) are the standing handoff to planning.

**Source of truth:** aspect commitment → [`../adrs/0001-grants-management-commitment.md`](../adrs/0001-grants-management-commitment.md) ·
rename trail + entities → [`../../domain-mapping.md`](../../domain-mapping.md) ·
inherited debt → [`../brownfield-debt.md`](../brownfield-debt.md) +
[`../pair-unique-debt.md`](../pair-unique-debt.md) · corpus → 2 CFR 200 (Uniform
Grants Guidance) + 45 CFR 75 (HHS supplement) · scope caps →
`training-resources/instructor-handbook/per-pair-scope-boundaries.md`.

---

## 1. Background / sponsor objective

The sponsor mandate, as received:

> *"Our grants officers and program officers are drowning in applications every
> funding cycle. We want to pilot AI to screen applications faster — flag the
> Section-508 and responsive-language gaps up front, catch duplicate-funding risk
> against past awards, and help run the peer-review panel — without an OIG auditor
> ever being able to say the system made an award decision a human was supposed to
> make, or screened an application against a rule that doesn't exist."*

That is the whole brief. It doesn't say which endpoints, which models, what
"screened" means, or where a human must stay in the loop — that's ours to plan.
Phase 1 disseminates it to a single intent: **introduce AI into the application →
screening → peer-review → award workflow, with every award-affecting or
irreversible decision routed through a human, and every AI output traceable to a
real grants regulation and an accountable actor.**

Phase 1 is **adoption**, not modernization. We add AI on top of the platform as
it stands; fixing the legacy stack is Phase 2 (§12).

## 2. Current state

`grants-portal-modern` was generated from the `acquire-gov` template and carries
the same four-service shape, renamed to the grants domain:

| Service | Stack | Port |
|---------|-------|------|
| `frontend/` | Angular 17 SPA — grants/program-officer UX | 4200 |
| `services/api-gateway/` | Spring Boot 2.7.18 + OAuth2 Resource Server (Java 11) | 8080 |
| `services/grant-application-service/` | Spring Boot 2.7.18 + Postgres + MongoDB (Java 11) | 8081 |
| `services/peer-review-service/` | Spring Boot 2.7.18 (Java 11) | 8082 |
| `services/ai-orchestrator/` | Python 3.11 + FastAPI + LangChain v1.0 (Bedrock) | 8000 |

(A `panel-coordination-service` is anticipated but not yet scaffolded — added in
planning if the multi-agent panel orchestrator needs it.)

The platform runs, but the AI path today returns **raw, ungrounded model output
with no validation** — it will confidently flag an application against a 2 CFR 200
rule that doesn't apply or doesn't exist. That is the OIG-defensibility problem
the sponsor named, and it's the thread Phase 1 pulls.

The platform carries **12 inherited debt items** ([`brownfield-debt.md`](../brownfield-debt.md))
shared with all pairs, plus **5 pair-unique items** ([`pair-unique-debt.md`](../pair-unique-debt.md)).
Adoption work surfaces — and may incidentally close — a few; deliberate
modernization of the rest is Phase 2.

## 3. Goals

| # | Goal | Done = |
|---|------|--------|
| G1 | Speed up application screening | A grants officer gets AI-flagged 508 + responsive-language gaps on an application, on demand. |
| G2 | Ground every AI judgment in real grants regulation | Screening flags and answers cite the actual 2 CFR 200 / 45 CFR 75 source; ungrounded ones are withheld, not shipped. |
| G3 | Make panel + award assistance safe | The peer-review → award flow runs with a human gate on every award-affecting or irreversible step. |
| G4 | Be auditable by default | Every AI-assisted decision is reconstructable: who, what, when, under which authority. |
| G5 | Be measurably correct | AI quality is gated by automated evaluation, and regressions are caught before they ship. |

## 4. Non-goals (Phase 1)

Boundaries are deliberate and sharp. Out of scope (most are Phase 2 or out-of-cohort):

- ❌ Framework/runtime modernization (Spring Boot/Java/`javax`→`jakarta`/AWS SDK hops).
- ❌ AI-security hardening of inherited debt; full multi-tenant isolation; AIOps/observability rollout.
- ❌ **Award-decision authority** code paths — simulated via mock + audit only.
- ❌ Real peer-reviewer authentication or external IdP (Login.gov/HHS) integration.
- ❌ Grant-**payment** processing (HHS PMS / Treasury — Pair 2's neighborhood).
- ❌ Multi-program funding logic (NSF vs NIH vs HHS) — one agency simulator only.
- ❌ Public-applicant portal UX deep-dive — the SPA stays minimal; the screening capability is the centerpiece.
- ❌ Post-award reporting (SF-PPR / FFR).
- ❌ Live PII — synthetic data only. Angular major-version hop. Managed Bedrock products.

## 5. Users

| Persona | Role | What Phase 1 gives them |
|---------|------|--------------------------|
| **Grants Officer** | Owns the award; authority holder | AI-screened applications + grounded answers to review; approval authority on screening outcomes and the award decision. |
| **Program Officer** | Runs the program; convenes the panel | Duplicate-funding signals; panel-orchestration support. |
| **Peer Review Panel** | Scores applications | Agent-assisted reviewer assignment + conflict-of-interest detection; visibility before consensus. |
| **Grantee PI** | Submits the application | Faster, clearer screening feedback (via the officer). |
| **OIG auditor** | After-the-fact accountability | A replayable trail: who decided what, when, under which authority, citing which rule. |

## 6. Capability requirements

Three capabilities in sequence; each one's gap is why the next exists. Stated as
outcomes — **the planning sessions decide how.**

### M1 — LLM-assisted application screening
- **REQ-AID-1** The platform screens a grant application and flags Section-508 + responsive-language gaps from an officer's request. *Done:* an officer gets a reviewable screening result on demand.
- **REQ-AID-2** AI output is safe to consume — no malformed or ungrounded content silently passes downstream. *Done:* bad model output is caught before it reaches another service or the officer.
- **REQ-AID-3** AI usage is cost-controlled and observable. *Done:* cost is attributable per tenant/feature and runaway spend is bounded.
- **REQ-AID-4** No award-affecting screening outcome is finalized without officer approval *(HITL)*. *Done:* finalization is impossible without a recorded human decision.

### M2 — Grounded retrieval
- **REQ-RAG-1** Regulatory judgments come from the actual 2 CFR 200 / 45 CFR 75 corpus, with citations; prior-award abstracts are retrievable to surface duplicate-funding risk. *Done:* every authoritative flag/answer traces to a source rule or prior award.
- **REQ-RAG-2** Low-confidence or ungrounded answers are withheld and escalated to a human, never shipped *(HITL)*. *Done:* below-bar answers route to review instead of returning.
- **REQ-RAG-3** One agency can never retrieve another agency's applications or awards. *Done:* cross-tenant retrieval is impossible and proven by test.
- **REQ-RAG-4** Retrieval quality is measured and protected from regression. *Done:* an evaluation gate blocks changes that degrade grounding.

### M3 — Agentic peer-review + award workflow
- **REQ-AGT-1** The peer-review panel runs as a multi-agent orchestration (reviewer assignment + conflict-of-interest detection) on synthetic applications, feeding an award recommendation. *Done:* the flow runs end to end and produces a recommendation plus a gated award step.
- **REQ-AGT-2** Every award-affecting or irreversible step stops for the responsible human; the agent cannot pass it (award decision; reviewer conflict resolution) *(HITL)*. *Done:* no code path auto-executes an award or overrides a conflict finding.
- **REQ-AGT-3** A paused decision survives a real-world human delay (hours or days) and resumes without loss or regeneration. *Done:* a run pauses for an officer/panel and resumes intact after a restart.
- **REQ-AGT-4** Every gated decision is auditable — who decided, what they saw, under which authority. *Done:* an OIG reviewer can reconstruct each decision from the trail alone.
- **REQ-AGT-5** The data answers the relational questions a program officer asks (e.g. "has this PI been funded for overlapping scope before?"). *Done:* the key cross-record question is answerable at interactive speed.

## 7. Principles (cross-cutting)

Non-negotiable; *how* they're implemented is planned.

- **Authority over accuracy.** Gates exist for accountability, not model quality. Award-affecting and irreversible steps are **hard** gates; confidence never downgrades one.
- **Right-sized HITL.** Classify by reversibility × blast-radius. Gate what must be gated — no skipped award decisions, no gate sprawl.
- **Grounded or withheld.** No authoritative flag/answer ships without a real citation; when grounding is weak, escalate rather than guess.
- **Auditable by default.** Sensitive/AI-assisted decisions write an append-only, OIG-replayable record.
- **Synthetic + FedRAMP-safe.** Synthetic data only; Bedrock is the sole LLM path (ADR `9002`); no direct third-party model API.
- **Eval as the gate.** Quality is proven by automated evaluation in CI, not manual inspection.

## 8. Domain model

Core entities (full inventory in [`domain-mapping.md`](../../domain-mapping.md)):
`GrantApplication` (primary) and `PeerReview` (review), across stages
**intake → screening → peer-review → award-decision**. Program-officer work is
relational ("this PI's prior awards with overlapping scope"), so the model must
support the key cross-record question at interactive speed (REQ-AGT-5). The
repo also inherits ~15 acquire-gov entities as raw material to repurpose or
delete in Phase 2 — not Phase 1 scope.

## 9. Success metrics & Phase 1 exit

Done when the three capabilities work end to end and the following hold (these are
also the gate dimensions):

| Dimension | Exit outcome |
|-----------|--------------|
| Agent-flow architecture | The peer-review → award flow runs end to end on synthetic data and survives a human-delay pause/resume. |
| Federal-authority semantics | Every hard gate names its governing rule (2 CFR 200 award + conflict-of-interest provisions); no award can be auto-executed. |
| HITL appropriateness | Gates are right-sized by reversibility × blast-radius — nothing award-affecting is skipped, nothing trivial over-gated. |
| Relational integration | The program officer's key cross-record question is answerable within an interactive budget. |
| Debt acknowledgement | The team can name which inherited/unique debt their AI work touched, surfaced, or closed — and which is deferred to Phase 2. |

Product signals: screening turnaround → minutes (G1); zero ungrounded
authoritative flags in evaluation (G2); 100% of hard-gate decisions produce an
audit record (G4).

## 10. Constraints & scope caps

- **One core entity, one workflow-stage MVP.** `GrantApplication` + application-intake screening. Other stages are referenced, not built.
- **No real authority.** Award decisions and payments are simulated via mock services + audit logs only.
- **One agency simulator.** No multi-program funding logic.
- **Synthetic data only.** No live PII anywhere.
- **Adopt, don't modernize.** Don't pre-fix inherited debt that Phase 2 owns; surface it, note the blast radius, defer it.

## 11. Open questions / to-plan

The deliberate handoff to planning — decided there and captured as ADRs.

- Screening output schema + the 508 / responsive-language fields an officer actually needs.
- Retrieval approach (chunking, embedding, dense/sparse/hybrid, reranking) over 2 CFR 200 + 45 CFR 75.
- Duplicate-funding signal: how prior-award similarity is computed and surfaced.
- The "withhold / escalate" confidence bar and how it's measured.
- Conflict-of-interest detection: rules-based vs. model-assisted, and its HITL gate.
- Panel-orchestration agent topology + how a paused award decision is persisted across a multi-day delay.
- How far correlation/tracing is threaded in Phase 1 vs. deferred to Phase 2.
- Which inherited/unique debt items are in-bounds to close incidentally vs. strictly deferred.

## 12. Phase 2 outline (refined at Phase 1 close-out)

Sketch only. Phase 2 = **modernization + operationalization**: framework/runtime
modernization; AI-security hardening of inherited + unique debt; AI-SRE for
deadline traffic spikes (auto-scale + queue management); OWASP-LLM hardening on
PI-submitted free-text (prompt injection through grant narratives); multi-tenant
award-isolation tests; reliability + AIOps + observability; client deliverability.
A dedicated Phase 2 PRD supersedes this section.

## 13. Change log

| Date | Change | Driver |
|------|--------|--------|
| 2026-05-28 | Initial Phase 1 PRD disseminated from sponsor objective (brief altitude). | Phase 1 kickoff |
