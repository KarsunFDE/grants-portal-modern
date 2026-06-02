"""
ai-orchestrator — main FastAPI entrypoint.

DELIBERATE BROWNFIELD DEBT (annotated for cohort discovery):

  Item 4 — No structured-output validation. /draft-grant-application returns the
           raw stub response (sometimes {"clause_id": null, ...}); downstream
           Spring service hits NullPointerException on .clause_id.toString().
           Newer endpoints (/draft-amendment, /answer-qa, /eval/ssdd-draft,
           /eval/factor-suggest, /agent/intake-triage) ALSO return raw dict —
           same Pydantic-validation drift across 4 distinct AI endpoints.

  Item 5 (partial) — This file uses the LangChain v1.0+ composed-Runnable
           pattern (prompt | llm | parser). The legacy LLMChain(...).run(...)
           pattern lives in app/legacy_chain.py and is invoked from 3 entry
           points: /draft-grant-application (Drafting Wizard), /draft-amendment
           (Amendment Editor), and the notification-copy generator (called
           upstream via the Spring Notifier.cparWindowOpened path which fans
           to /draft-amendment with a CPAR-window topic). Cohort consolidates
           in W2.

  Item 6 (partial) — No correlation-ID logging at all. Other services log
           X-Request-ID / correlationId / traceId — this one logs nothing.

  Item 7 — pinecone-client is in requirements.txt but no `import pinecone`
           anywhere. Cohort removes in W2.

  Item 11 — Dockerfile uses :latest (the OTHER 4 services do; this one is
           hand-pinned to 3.11-slim per the comment block at the top of the
           ai-orchestrator Dockerfile).

  Plus: no retry, no streaming, no real Bedrock retry/cost accounting in
  this code path. Bedrock InvokeModel is wired (D-060 — real-Bedrock-from-W2
  authorized) via app/bedrock_client.py; if AWS creds aren't present, the
  client falls back to a stub.
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ⚠ Item 5 — v1.0 composed-Runnable style. Imported but not actually wired to
# Bedrock in the stub (we return mock data). Cohort wires it up in W1 Thu.
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    _LANGCHAIN_V1_AVAILABLE = True
except ImportError:
    _LANGCHAIN_V1_AVAILABLE = False

# Note: legacy_chain.py also exists in this package and uses the pre-v1.0
# LLMChain pattern. Item 5 — cohort migrates that file's style to this one.
from app import legacy_chain  # noqa: F401 — imported to keep the v0.x entry
                                # point reachable; cohort grep finds the seam.
from app.bedrock_client import invoke_model, BEDROCK_MODEL_ID, AWS_REGION
from app.routers import gates as gates_router
from app.routers import retrieval_v2 as retrieval_v2_router
from app.services.grounding import compute_grounding_status, is_grounded
from app.services.retrieval import retrieval_service
from app.services.gate_enforcer import gate_enforcer
from app.services.cache_validator import validate_before_generation
from app.schemas.hitl import GateId, HumanReviewReason, GroundingStatus

# ⚠ DELIBERATE — no correlation-ID in the log format (Item 6).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s - %(message)s",
)
log = logging.getLogger("ai-orchestrator")

app = FastAPI(title="ai-orchestrator", version="0.1.0-brownfield")
app.include_router(gates_router.router)
app.include_router(retrieval_v2_router.router)


class DraftRequest(BaseModel):
    """
    ⚠ DELIBERATE — Item 4 reinforcement:
      No Field constraints, no examples, no descriptions. Cohort tightens
      in W1 Fri output validation.
    """
    topic: str
    constraints: str | None = None


class QaDraftRequest(BaseModel):
    """Applicant Q&A drafting request. ⚠ Item 4 — no Field constraints."""
    question: str
    grant_application_id: str | None = None
    constraints: str | None = None


class ClauseSearchRequest(BaseModel):
    """Hybrid RAG over the 2 CFR 200 Uniform Guidance corpus. ⚠ Item 4 — no Field."""
    query: str
    far_part: str | None = None
    agency_id: str | None = None  # ⚠ Item 10 surface — not enforced upstream
    top_k: int = 5


class FactorSuggestRequest(BaseModel):
    """Merit-criterion review-narrative suggestion. ⚠ Item 4 — no Field."""
    topic: str
    tenant_id: str
    constraints: str | None = None


class SSDDDraftRequest(BaseModel):
    """Award package / SSDD draft request — tenant_id required for Gate 4 tenant binding."""
    topic: str
    tenant_id: str
    constraints: str | None = None


class IntakeTriageRequest(BaseModel):
    """Multi-agent application-intake triage request. ⚠ Item 4 — no Field."""
    proposal_id: str
    grant_application_id: str | None = None
    raw_text: str | None = None


class EligibilityCheckRequest(BaseModel):
    """Eligibility/completeness screening request (2 CFR 200.206). ⚠ Item 4 — no Field."""
    tenant_id: str  # required for tenant isolation (hitl-plan.txt §Tenant Binding Invariant)
    grant_application_id: str | None = None
    applicant_type: str | None = None
    applicant_uei: str | None = None
    assistance_listing_number: str | None = None
    requested_amount_federal: float | None = None
    raw_text: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    """
    ⚠ DELIBERATE: always returns 200. No DB ping, no Bedrock ping.
    Cohort adds real health check in W5 Tue OTel work.
    """
    return {"status": "ok", "service": "ai-orchestrator"}


@app.post("/draft-grant-application")
def draft_grant_application(req: DraftRequest) -> dict[str, Any]:
    """
    Section C SOW + Section L instructions drafting (Workflow 1).

    Bedrock invocation via app.bedrock_client.invoke_model (D-060 — real
    Bedrock from W2, falls back to stub if no AWS creds). Result is
    interleaved with the same 1-in-3 null-clause_id drift the locked test
    asserts (Item 4).

    ⚠ DELIBERATE GAPS (Item 4):
      - No Pydantic response model — returns raw dict.
      - 1-in-3 calls return {"clause_id": null, ...} to exercise the
        downstream NullPointerException path.
      - No retry, no streaming, no cost tracking, no structured-output
        schema enforced.
    """
    log.info("draft-grant_application called topic=%r constraints=%r",
             req.topic, req.constraints)

    # Bedrock call (D-060). Drops result into 'draft' field; preserves the
    # null-clause_id drift surface on top.
    bedrock = invoke_model(
        f"Draft a federal grant project-narrative paragraph about: {req.topic}. "
        f"Constraints: {req.constraints or 'none'}.",
        system="You draft 2 CFR 200-compliant grant application narrative language.",
    )

    # ⚠ Item 4 — 1-in-3 returns null clause_id; downstream service can break.
    if random.randint(1, 3) == 1:
        return {
            "clause_id": None,  # ← will trigger downstream NPE
            "draft": bedrock["body"],
            "model": BEDROCK_MODEL_ID,
        }

    # Otherwise return a "happy" stub.
    return {
        "clause_id": f"2-CFR-200.{random.randint(200, 350)}-{random.randint(1, 30)}",
        "draft": bedrock["body"],
        "model": BEDROCK_MODEL_ID,
        "region": AWS_REGION,
    }


@app.post("/check-eligibility")
def check_eligibility(req: EligibilityCheckRequest) -> dict[str, Any]:
    """
    Eligibility / completeness screening for an incoming grant application
    (2 CFR 200.205-206 — merit + risk review). Returns a recommendation the
    Program Officer reviews before advancing INTAKE → SCREENING → PEER_REVIEW.

    ⚠ DELIBERATE — Item 4: no Pydantic response model; returns a raw dict.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    log.info("check-eligibility application_id=%r applicant_type=%r",
             req.grant_application_id, req.applicant_type)

    # Grounded retrieval — 2 CFR 200.205/206 required before generation (Gate 1)
    query = (
        f"eligibility risk review applicant_type={req.applicant_type or ''} "
        f"assistance_listing={req.assistance_listing_number or ''}"
    )
    citations, confidence, faithfulness, retrieved_at = retrieval_service.retrieve(
        query=query,
        tenant_id=req.tenant_id,
    )
    grounding_status, human_review_reasons = compute_grounding_status(citations, confidence, faithfulness)

    # Cache revalidation before generation (hitl-plan.txt §Cache Revalidation Policy — AC13)
    cache_ok, cache_reasons = validate_before_generation(
        citations=citations,
        confidence_score=confidence,
        faithfulness_score=faithfulness,
        cache_created_at=retrieved_at,
        tenant_id=req.tenant_id,
    )
    if not cache_ok:
        for r in cache_reasons:
            if r not in human_review_reasons:
                human_review_reasons.append(r)
        if is_grounded(grounding_status):
            grounding_status = GroundingStatus.UNGROUNDED

    # Block ungrounded regulatory guidance (hitl-plan.txt §Grounding Policy)
    ai_run_id = str(uuid.uuid4())
    if not is_grounded(grounding_status):
        escalation = gate_enforcer.create_escalation(
            gate_id=GateId.GATE_1,
            tenant_id=req.tenant_id,
            ai_run_id=ai_run_id,
            human_review_reasons=human_review_reasons,
            grounding_status=grounding_status,
            confidence_score=confidence,
        )
        return {
            "grant_application_id": req.grant_application_id,
            "eligible": None,
            "screening_notes": None,
            "recommended_status": "ESCALATED",
            "hitl_gate": GateId.GATE_1.value,
            "escalation_owner": "GRANTS_OFFICER",
            "requires_human_review": True,
            "human_review_reasons": [r.value for r in human_review_reasons],
            "grounding_status": grounding_status.value,
            "confidence_score": confidence,
            "faithfulness_score": faithfulness,
            "retrieved_sources": [c.source_id for c in citations],
            "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
            "escalation_id": escalation.escalation_id,
            "ai_run_id": ai_run_id,
            "model": BEDROCK_MODEL_ID,
        }

    bedrock = invoke_model(
        f"Screen this grant application for eligibility and completeness. "
        f"Applicant type: {req.applicant_type or '(unknown)'}; "
        f"Assistance Listing: {req.assistance_listing_number or '(none)'}; "
        f"Federal request: {req.requested_amount_federal or '(none)'}. "
        f"Context: {req.raw_text or '(none)'}. "
        f"Regulatory basis: {', '.join(c.source_id for c in citations)}.",
        system="You screen federal grant applications for eligibility and "
               "completeness under 2 CFR 200; flag missing SF-424 items and "
               "ineligible applicant types. A Program Officer makes the final call.",
    )
    ineligible_types = {"INDIVIDUAL", "FOR_PROFIT"}
    eligible = (req.applicant_type or "").upper() not in ineligible_types
    return {
        "grant_application_id": req.grant_application_id,
        "eligible": eligible,
        "screening_notes": bedrock["body"],
        "recommended_status": "PEER_REVIEW" if eligible else "WITHDRAWN",
        "hitl_gate": GateId.GATE_1.value,
        "escalation_owner": "GRANTS_OFFICER",
        "requires_human_review": True,  # Gate 1: human decision always required
        "human_review_reasons": [r.value for r in human_review_reasons],
        "grounding_status": grounding_status.value,
        "confidence_score": confidence,
        "faithfulness_score": faithfulness,
        "retrieved_sources": [c.source_id for c in citations],
        "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
        "citations": [c.model_dump() for c in citations],
        "ai_run_id": ai_run_id,
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/draft-amendment")
def draft_amendment(req: DraftRequest) -> dict[str, Any]:
    """
    Amendment narrative drafting (Workflow 2; FAR 15.206).

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 5 — routes through legacy_chain construction (the legacy LLMChain
       pattern is imported + constructed via legacy_chain.draft_with_legacy_chain
       upstream in the call graph). This is entry point #2 of 3 for Item 5.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    log.info("draft-amendment called topic=%r", req.topic)
    bedrock = invoke_model(
        f"Draft a NOFO amendment narrative for: {req.topic}. "
        f"Applicant-impact considerations: {req.constraints or 'standard scope change'}.",
        system="You draft Grants.gov NOFO amendment narratives (2 CFR 200.204).",
    )
    return {
        "amendment_text": bedrock["body"],
        "model": BEDROCK_MODEL_ID,
        "predicted_vendor_impact": "re-acknowledgement required",
    }


@app.post("/answer-qa")
def answer_qa(req: QaDraftRequest) -> dict[str, Any]:
    """
    Vendor Q&A response drafting using clause-library RAG.

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded.
    ⚠ Item 9 reinforcement — req.question may contain raw HTML; we feed it
       directly into the prompt (prompt-injection-via-stored-content
       surface for W4 Wed OWASP LLM01).
    """
    log.info("answer-qa called question=%r", req.question[:60])
    bedrock = invoke_model(
        f"Applicant question: {req.question}\n\n"
        f"Draft a 2 CFR 200-compliant agency answer. Cite section IDs where applicable.",
        system="You answer applicant questions about federal funding opportunities (NOFOs).",
    )
    return {
        "answer_draft": bedrock["body"],
        "cited_clauses": [],  # ⚠ Item 4 — schema mismatch; sometimes the body
                              # contains clause refs but this list stays empty
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/rag/clause-search")
def rag_clause_search(req: ClauseSearchRequest) -> dict[str, Any]:
    """
    Hybrid RAG over FAR/DFARS clause library (Atlas Vector Search).

    Cohort wires the Atlas hybrid retrieval in W2 (replacing the lexical-only
    stub here). Pinecone is listed in requirements.txt as "available vector
    store" but never imported (Item 7).

    ⚠ Item 6 — no correlation-id forwarded.
    ⚠ Item 7 — pinecone-client is in requirements.txt; this module does not
       import pinecone (stays unimported).
    """
    log.info("rag/clause-search query=%r far_part=%r top_k=%d",
             req.query[:60], req.far_part, req.top_k)
    # ⚠ Atlas Vector Search call would land here; stub returns a shaped
    # response so the surface flows.
    bedrock = invoke_model(
        f"Summarize 2 CFR 200 / 45 CFR 75 sections relevant to: {req.query}",
        system="You retrieve Uniform Guidance (2 CFR 200) sections; cite section IDs.",
    )
    hits = [
        {"clause_id": "2-CFR-200.205", "title": "Federal awarding agency review of merit of proposals",
         "score": 0.91, "far_part": "2 CFR 200"},
        {"clause_id": "2-CFR-200.430", "title": "Compensation — personal services (allowable costs)",
         "score": 0.87, "far_part": "2 CFR 200"},
    ][: req.top_k]
    return {
        "query": req.query,
        "hits": hits,
        "synthesis": bedrock["body"],
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/eval/factor-suggest")
def eval_factor_suggest(req: FactorSuggestRequest) -> dict[str, Any]:
    """
    Section M factor-narrative suggestion. HITL-gated by evaluator.

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    log.info("eval/factor-suggest topic=%r", req.topic)

    # Grounded retrieval — 2 CFR 200.204/205 required before factor suggestion (Gate 3)
    citations, confidence, faithfulness, retrieved_at = retrieval_service.retrieve(
        query=f"evaluation factor merit criterion {req.topic}",
        tenant_id=req.tenant_id,
    )
    grounding_status, human_review_reasons = compute_grounding_status(citations, confidence, faithfulness)

    # Cache revalidation before generation (AC13)
    cache_ok, cache_reasons = validate_before_generation(
        citations=citations,
        confidence_score=confidence,
        faithfulness_score=faithfulness,
        cache_created_at=retrieved_at,
        tenant_id=req.tenant_id,
    )
    if not cache_ok:
        for r in cache_reasons:
            if r not in human_review_reasons:
                human_review_reasons.append(r)
        if is_grounded(grounding_status):
            grounding_status = GroundingStatus.UNGROUNDED

    ai_run_id = str(uuid.uuid4())
    if not is_grounded(grounding_status):
        escalation = gate_enforcer.create_escalation(
            gate_id=GateId.GATE_3,
            tenant_id=req.tenant_id,
            ai_run_id=ai_run_id,
            human_review_reasons=human_review_reasons,
            grounding_status=grounding_status,
            confidence_score=confidence,
        )
        return {
            "narrative_suggestion": None,
            "hitl_gate": GateId.GATE_3.value,
            "escalation_owner": "HUMAN_REVIEWER",
            "requires_human_review": True,
            "human_review_reasons": [r.value for r in human_review_reasons],
            "grounding_status": grounding_status.value,
            "confidence_score": confidence,
            "faithfulness_score": faithfulness,
            "retrieved_sources": [c.source_id for c in citations],
            "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
            "escalation_id": escalation.escalation_id,
            "ai_run_id": ai_run_id,
            "model": BEDROCK_MODEL_ID,
        }

    bedrock = invoke_model(
        f"Suggest a merit-criterion review narrative for: {req.topic}. "
        f"Application context: {req.constraints or '(none)'}. "
        f"Cite: {', '.join(c.source_id for c in citations)}.",
        system="You suggest peer-reviewer narrative; HITL approves before publish.",
    )
    return {
        "narrative_suggestion": bedrock["body"],
        # Gate 3 rule: AI suggestions are assistive only — human acceptance always required
        "hitl_gate": GateId.GATE_3.value,
        "escalation_owner": "HUMAN_REVIEWER",
        "requires_human_review": True,
        "human_review_reasons": [r.value for r in human_review_reasons],
        "grounding_status": grounding_status.value,
        "confidence_score": confidence,
        "faithfulness_score": faithfulness,
        "retrieved_sources": [c.source_id for c in citations],
        "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
        "citations": [c.model_dump() for c in citations],
        "ai_run_id": ai_run_id,
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/eval/ssdd-draft")
def eval_ssdd_draft(req: SSDDDraftRequest) -> dict[str, Any]:
    """
    Source Selection Decision Document tradeoff narrative drafting.
    SSA-gated (FAR 15.308 — non-delegable).

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 5 — third entry point; copy generated via legacy_chain when the
       upstream notification path requests CPAR-window copy generation.
    ⚠ Item 6 — no correlation-id forwarded.
    """
    log.info("eval/ssdd-draft topic=%r", req.topic)

    # Grounded retrieval — 2 CFR 200.205/212 required before award package (Gate 4)
    citations, confidence, faithfulness, retrieved_at = retrieval_service.retrieve(
        query=f"award decision funding recommendation {req.topic}",
        tenant_id=req.tenant_id,
    )
    grounding_status, human_review_reasons = compute_grounding_status(citations, confidence, faithfulness)

    # Cache revalidation before generation (AC13)
    cache_ok, cache_reasons = validate_before_generation(
        citations=citations,
        confidence_score=confidence,
        faithfulness_score=faithfulness,
        cache_created_at=retrieved_at,
        tenant_id=req.tenant_id,
    )
    if not cache_ok:
        for r in cache_reasons:
            if r not in human_review_reasons:
                human_review_reasons.append(r)
        if is_grounded(grounding_status):
            grounding_status = GroundingStatus.UNGROUNDED

    ai_run_id = str(uuid.uuid4())
    if not is_grounded(grounding_status):
        escalation = gate_enforcer.create_escalation(
            gate_id=GateId.GATE_4,
            tenant_id=req.tenant_id,
            ai_run_id=ai_run_id,
            human_review_reasons=human_review_reasons,
            grounding_status=grounding_status,
            confidence_score=confidence,
        )
        return {
            "ssdd_narrative": None,
            "clause_id": None,
            "hitl_gate": GateId.GATE_4.value,
            "escalation_owner": "GRANTS_OFFICER",
            "requires_human_review": True,
            "human_review_reasons": [r.value for r in human_review_reasons],
            "grounding_status": grounding_status.value,
            "confidence_score": confidence,
            "faithfulness_score": faithfulness,
            "retrieved_sources": [c.source_id for c in citations],
            "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
            "escalation_id": escalation.escalation_id,
            "ai_run_id": ai_run_id,
            "model": BEDROCK_MODEL_ID,
        }

    bedrock = invoke_model(
        f"Draft a panel funding-recommendation narrative for: {req.topic}. "
        f"Constraints: {req.constraints or 'merit-based selection per 2 CFR 200.205'}. "
        f"Regulatory basis: {', '.join(c.source_id for c in citations)}.",
        system="You draft funding-recommendation memos; the Selecting Official reviews + approves.",
    )
    return {
        "ssdd_narrative": bedrock["body"],
        "clause_id": f"REC-{random.randint(1000, 9999)}",
        # Gate 4: no unattended award — human approval always required
        "hitl_gate": GateId.GATE_4.value,
        "escalation_owner": "GRANTS_OFFICER",
        "requires_human_review": True,
        "human_review_reasons": [r.value for r in human_review_reasons],
        "grounding_status": grounding_status.value,
        "confidence_score": confidence,
        "faithfulness_score": faithfulness,
        "retrieved_sources": [c.source_id for c in citations],
        "citation_refs": [f"{c.regulation}:{c.section}" for c in citations],
        "citations": [c.model_dump() for c in citations],
        "ai_run_id": ai_run_id,
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/agent/intake-triage")
def agent_intake_triage(req: IntakeTriageRequest) -> dict[str, Any]:
    """
    Multi-agent W3 flow: triage incoming proposal, route to TEP evaluators,
    escalate anomalies to CO.

    Sequential agent invocations (intake-classifier → evaluator-router →
    anomaly-escalator); each call is currently a single Bedrock invoke
    with the same stub fallback. LangGraph wiring comes in W3.

    ⚠ Item 4 — no Pydantic response model.
    ⚠ Item 6 — no correlation-id forwarded; each agent hop is invisible in
       the audit log because nothing threads a request id through.
    """
    log.info("agent/intake-triage proposal_id=%r", req.proposal_id)
    classify = invoke_model(
        f"Classify this application's program area + complexity: {req.raw_text or req.proposal_id}",
        system="You classify federal grant applications for merit-review-panel routing.",
    )
    route = invoke_model(
        f"Recommend 3 peer reviewers for application_id={req.proposal_id}.",
        system="You route applications to peer-review-panel members based on subject expertise.",
    )
    anomaly = invoke_model(
        f"Flag anomalies in application_id={req.proposal_id} that warrant Program Officer escalation.",
        system="You flag anomalies (completeness, eligibility, conflict of interest).",
    )
    return {
        "proposal_id": req.proposal_id,
        "classification": classify["body"],
        "routing": route["body"],
        "anomalies": anomaly["body"],
        "escalation_required": "CO" if "anomaly" in anomaly["body"].lower() else None,
        "hitl_gate": "co-review-on-escalation",
        "model": BEDROCK_MODEL_ID,
    }


@app.post("/draft-grant-application-v1")
def draft_grant_application_v1(req: DraftRequest) -> dict[str, Any]:
    """
    v1.0 composed-Runnable example (Item 5).

    Demonstrates the prompt | llm | parser pattern the cohort migrates the
    legacy_chain.py to in W2. Still a stub — doesn't hit real Bedrock.
    """
    if not _LANGCHAIN_V1_AVAILABLE:
        raise HTTPException(503, "langchain v1.0 not available")

    # Composed-Runnable scaffolding — would be:
    #   prompt | bedrock_llm | StrOutputParser()
    # We just demonstrate the construction without invoking it.
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You draft federal grant project narratives."),
        ("user", "Draft a paragraph about: {topic}. Constraints: {constraints}."),
    ])
    parser = StrOutputParser()
    _chain_scaffold = prompt | parser  # would normally be: prompt | llm | parser

    log.info("draft-grant_application-v1 (composed Runnable scaffold) topic=%r",
             req.topic)

    return {
        "clause_id": f"2-CFR-200.{random.randint(200, 350)}-{random.randint(1, 30)}",
        "draft": f"[stub-v1] composed-runnable draft about {req.topic}",
        "model": BEDROCK_MODEL_ID,
        "pattern": "prompt | llm | parser",
    }
