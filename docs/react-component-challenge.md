# React Component Challenge — `grants-portal-modern` (Cohort #1 Pair 1)

> **Phase 2 React-competency verification.** Federal Grants Management aspect
> (Grants.gov / SmartGrants / GrantSolutions). Primary entity `GrantApplication`,
> review entity `PeerReview`, multi-agent peer-review-panel shape.
>
> This is the per-pair React deliverable that proves you can build **and defend**
> a React component while transitioning from Angular. You pick the component;
> you own every decision.

---

## Goal + the FDE bar

A mock-interview review surfaced the gap this challenge closes: candidates can
*build* but can't *defend*. You will build one small React component **from
scratch** and be able to explain — out loud, under questioning — what it does,
how it talks to the user **and** the backend, how state flows through it, and
which tradeoffs you accepted.

The bar is **FDE-grade**, which means three things:

1. **Scope-first.** A small, sharp component that does one job well beats a
   sprawling half-built feature. Cut scope until you can defend every line.
2. **Defend-every-decision.** Every choice — state location, fetch strategy,
   error handling, prop shape — must have a reason you can say in one sentence.
   "It's how the tutorial did it" is a failing answer.
3. **Hand-written.** See the rule below. This is non-negotiable.

This is a **brownfield** repo: the frontend is Angular 17+ today. This challenge
is the React beachhead — you are demonstrating the React fluency the
Angular→React modernization arc depends on.

---

## 🛑 HAND-WRITTEN RULE — read this first, it is the whole point

> ## This component is built BY HAND. No code generation. None.
>
> - **No Claude Code. No GitHub Copilot. No Cursor autocomplete. No ChatGPT/
>   Claude/Gemini "write me a component". No code-gen of any kind** for the
>   component source, the ADR, or the diagram.
> - You may **read** the React readings in
>   [`KarsunFDE/content/topics/react/readings/`](https://github.com/KarsunFDE/content/tree/main/topics/react/readings)
>   and the official React docs. You may use a plain editor, a linter, and the
>   TypeScript compiler. That's it.
> - You sign the attestation in
>   [`docs/react-component-challenge-attestation.md`](./react-component-challenge-attestation.md).
>   Both partners sign.

**Why this rule exists.** The program needs to *verify real React fluency* for
engineers transitioning from Angular — not the ability to prompt a tool into
producing React. In the field you will defend a design in a room with a federal
client. If a generator wrote your `useState` and you can't say why the state
lives there, you will not survive that room. The hand-written constraint is the
only way to measure the thing we actually care about. It is loud, it is
mandatory, and it is attested.

The instructor and Codex review will probe for tells (idiomatic-but-unexplained
patterns, scaffolding you can't account for). The defense, not the diff, is
graded.

---

## Requirements

Your component MUST satisfy all of the following:

1. **React, built from scratch.** A new component (function component + hooks),
   written by hand in this repo. TypeScript preferred; matches the codebase you
   are modernizing toward.
2. **Talks to the backend — not a pure-frontend widget.** It must read and/or
   write real data through the platform's backend. This is the load-bearing
   requirement: a self-contained counter or to-do list does **not** pass.
3. **Real user interaction on the frontend.** A user does something — submits,
   assigns, filters, approves, flags — and sees the result.
4. **Visible state flow.** Loading / success / empty / error states are all
   reachable and visibly distinct. State changes are observable in the React
   DevTools Components + Profiler tabs.

### Backend contract you consume/extend

This repo's backend is a Spring Boot + FastAPI microservice stack behind an API
gateway. Route everything through the **gateway on `:8080`** — do **not**
hardcode a service port (debt item #8 in `docs/brownfield-debt.md` is exactly
the anti-pattern of bypassing the gateway; don't reproduce it).

| Service | Port (direct) | Via gateway | Owns |
|---------|---------------|-------------|------|
| `api-gateway` | `:8080` | — | auth edge + routing; **your component calls here** |
| `grant-application-service` | `:8081` | `/api/grant-applications` | `GrantApplication` lifecycle |
| `peer-review-service` | `:8082` | `/api/peer-reviews` (panel coordination) | `PeerReview` |
| `ai-orchestrator` (FastAPI) | `:8000` | `/api/ai/*` | LLM / RAG / multi-agent peer-review-panel orchestrator |

Define the exact endpoint contract you consume in your ADR: method, path
(gateway-relative), request shape, response shape, and the JWT/auth assumption.
If the endpoint you need doesn't exist yet, you may **extend** the backend with
a minimal endpoint (documented in the ADR) **or** consume an existing one — your
call, but justify it. Either way, the contract is written down before you build
the UI against it.

---

## Own your decisions — required deliverables

Building the component is half the work. The other half is the paper trail that
proves it was a decision, not an accident.

### 1. An ADR (matches THIS repo's `docs/adrs/` style)

Write an Architecture Decision Record using the stub provided at
[`docs/adrs/0002-react-component-challenge.md`](./adrs/0002-react-component-challenge.md).

- **Number: `0002`.** This repo's `docs/adrs/` currently holds
  `0001-grants-management-commitment.md` plus the `9001`/`9002` architecture
  ADRs. `0002` is the next sequential application ADR. Keep the
  `# ADR-0002 — Title` heading style, `Status:` / `Date:` / `Decider:` header
  lines, and `## Context / ## Decision / ## Alternatives Considered /
  ## Consequences` section shape used by `0001`.
- The ADR records **which component you chose and why**, the backend contract,
  the state design, and the alternative you rejected.

### 2. A component diagram (mermaid)

In the ADR (or linked from it), include a **mermaid** diagram showing both:

- **State flow** — which component owns which state, what derives from what,
  what triggers re-renders.
- **Frontend ↔ backend data flow** — user action → component → API client →
  gateway `:8080` → service → response → state update → render.

---

## Pick your component

You **choose** the component. The three ideas below are domain-true starting
points for the grants aspect — but you may **propose your own** if it meets the
requirements and you defend the choice in the ADR.

1. **Reviewer-Assignment Panel.** Given a `GrantApplication`, show the pool of
   eligible peer reviewers and let a Grants Officer assign N reviewers, with the
   `ai-orchestrator` peer-review-panel agent flagging conflict-of-interest
   (same-institution, prior-collaboration) on candidates. Reads from
   `peer-review-service`, writes assignments back. Rich state: selection set,
   server-fetched eligibility, agent-derived COI warnings.
2. **Application-Screening Queue.** A filterable list of incoming
   `GrantApplication`s with AI screening flags (Section 508 / responsive-language
   per the Phase-1 seeds) surfaced inline; the officer triages — accept to panel,
   send back, reject. Server state (the queue) + client state (filters, the
   in-flight triage decision).
3. **Duplicate-Funding Risk Card.** For one application, call the RAG path over
   prior award abstracts and render a ranked list of possible duplicate-funding
   matches with similarity + citation, letting the reviewer mark each
   "duplicate / not duplicate." Exercises an async AI call, loading/streaming
   states, and a derived risk verdict.

**Propose-your-own rule:** if none of these fit, pitch your component in the ADR
`## Context`. It must still talk to the backend, have real interaction, and show
visible state flow. Defend why it's a better demonstration than the three above.

---

## State-flow explainer (required written walkthrough)

Include a short written walkthrough (in the ADR or a sibling note) that names,
explicitly:

- **State ownership** — which component holds which piece of state, and why
  there and not higher/lower.
- **Lifting** — any state you lifted to a common parent, and what forced it.
- **Derived vs server state** — what is computed on every render from existing
  state/props (derived, not stored) vs what comes from the backend (server
  state). This distinction is the spine of the challenge — see reading
  [`10-data-fetching-client-vs-server-state.md`](https://github.com/KarsunFDE/content/blob/main/topics/react/readings/10-data-fetching-client-vs-server-state.md).
- **Re-render triggers** — what causes this component (and its children) to
  re-render, and where reference identity matters. Tie to reading
  [`03-rendering-and-rerender-model.md`](https://github.com/KarsunFDE/content/blob/main/topics/react/readings/03-rendering-and-rerender-model.md)
  and [`04-purity-and-state-snapshot.md`](https://github.com/KarsunFDE/content/blob/main/topics/react/readings/04-purity-and-state-snapshot.md).

Coming from Angular, name at least one place where your mental model had to
change (e.g. no two-way `[(ngModel)]` binding; state is a snapshot per render;
re-render ≠ DOM write). The readings in
[`topics/react/readings/`](https://github.com/KarsunFDE/content/tree/main/topics/react/readings)
(especially 02 props-vs-state, 08 composition-and-lifting-state) are the source
material.

---

## Defend-your-design checklist

You will be asked these live. Have an answer for each before review:

- [ ] **Biggest decision.** What was the single most consequential design choice,
      and why did you make it that way?
- [ ] **Alternative rejected.** What did you seriously consider and *not* do?
      What did rejecting it cost you?
- [ ] **Cost accepted.** What tradeoff did you knowingly take on (complexity,
      a re-render, a coupling, a missing feature)?
- [ ] **Failure behavior — resilience over happy-path.** How does the component
      behave when:
      - the **backend is down** (gateway/service unreachable)?
      - the response is **slow** (does the UI block, show a skeleton, allow
        cancel)?
      - the result is **empty** (no reviewers eligible, no applications queued)?
      - the backend returns an **error** (4xx/5xx, malformed payload)?
- [ ] **Auth/tenant.** What does your component assume about the JWT and
      `agency_id`? (Note: multi-tenant boundary is debt item #10 — don't *rely*
      on a filter that isn't there; state your assumption.)

A component that only handles the happy path is **not done**. Resilience is
graded above features.

---

## Definition of done

- [ ] Component is hand-written, lives in this repo, and renders.
- [ ] It reads and/or writes real data through the gateway (`:8080`), not a mock.
- [ ] Loading / success / empty / error states are all reachable and distinct.
- [ ] ADR `0002` is filled in (Context / Decision / Alternatives / Consequences),
      cites the backend contract, and matches this repo's ADR style.
- [ ] Mermaid diagram shows state flow **and** frontend↔backend data flow.
- [ ] State-flow explainer written; Angular→React mental-model shift named.
- [ ] Defend-your-design checklist answered, including all four failure modes.
- [ ] Attestation signed by **both** partners.

### How it's evaluated

- **Codex review** — independent diff review for correctness and resilience
  (error/empty/loading paths actually present), and a smell-check for
  unexplained generated-looking scaffolding. Never silently skipped; if Codex is
  unavailable the review runs in `degraded-review` mode with explicit
  acknowledgment.
- **Instructor defense** — a live walkthrough against the defend-your-design
  checklist and the state-flow explainer. The defense is graded, not the diff.
  If you can't explain why the state lives where it lives, it doesn't pass —
  regardless of whether it works.

---

## Phase mapping

This is a **Phase 2** deliverable. It assumes the Phase-1 micro-builds
(`fde-mb-01` … `fde-mb-04`) are done — those established the individual
React/JS fundamentals. Phase 2 is where you build a real component **from
scratch** and **explain your state flow** end-to-end, against this repo's actual
backend. Phase-1 taught the pieces; Phase 2 proves you can assemble and defend
them.
