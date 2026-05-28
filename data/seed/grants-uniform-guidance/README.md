# Grants Uniform Guidance — RAG starter corpus (2 CFR 200)

> **STARTER STUBS — not the full text.** Each file is a 1–2 paragraph excerpt /
> paraphrase of a real 2 CFR 200 (Uniform Administrative Requirements, Cost
> Principles, and Audit Requirements for Federal Awards) section, kept short on
> purpose. The cohort **expands and re-ingests** the full corpus in W2 RAG work
> (Atlas Vector Search, collection `grants_uniform_guidance` /
> `COLLECTION_GRANTS_UNIFORM_GUIDANCE`).
>
> Section numbers and titles are real (2 CFR Part 200, Subparts A–F; HHS
> supplement at 45 CFR Part 75 mirrors these). Authoritative full text:
> https://www.ecfr.gov/current/title-2/subtitle-A/chapter-II/part-200
>
> **Do not treat these excerpts as legally authoritative** — they are teaching
> seeds for the retrieval pipeline only.

## Files

| File | Section | Topic |
|------|---------|-------|
| `200-subpart-a-definitions.md` | 2 CFR 200 Subpart A | Key definitions (recipient, Federal award, period of performance, Assistance Listing) |
| `200.204-nofo.md` | § 200.204 | Notices of funding opportunity (NOFO content) |
| `200.205-merit-review.md` | § 200.205 | Federal awarding agency review of merit of proposals |
| `200.206-risk-review.md` | § 200.206 | Federal awarding agency review of risk posed by applicants |
| `200.211-award-information.md` | § 200.211 | Information contained in a Federal award |
| `200.328-329-reporting.md` | §§ 200.328–200.329 | Performance & financial reporting (Subpart D) |
| `200.344-closeout.md` | § 200.344 | Closeout |
| `200.430-431-allowable-costs.md` | §§ 200.430–200.431 | Compensation & fringe (allowable costs, Subpart E) |
| `sf-424-field-reference.md` | — | SF-424 "Application for Federal Assistance" field reference card |

## Ingestion (W2 cohort task)

These files are intentionally **not** wired into a vector index yet. The W2 RAG
anchor task is to chunk + embed them into Atlas Vector Search under the
`grants_uniform_guidance` collection and replace the lexical-only stub in
`services/ai-orchestrator/app/main.py` (`/rag/clause-search`).
