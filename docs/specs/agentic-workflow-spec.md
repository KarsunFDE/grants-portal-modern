# Agentic Workflow Specification

**Service:** `grants-portal-modern` — `services/ai-orchestrator`
**Date:** 2026-06-09
**Source of truth:** `docs/specs/agentic-workflow-visualization.html`

---

## 1. Responsibility Lanes

| Lane | Owner | Role |
|------|-------|------|
| **Human (HITL)** | Grants Officer, Program Officer, Review Lead, Human Reviewer | Policy authority, final decisions |
| **Programmatic** | `ai-orchestrator` control plane | Validation, grounding, audit, routing |
| **AI** | Claude Sonnet via AWS Bedrock | Assistive drafting and reasoning — no autonomous final decisions |

---

## 2. HITL Gates

| Gate | Stage (`WorkflowStage`) | Owner Role (`GateOwnerRole`) | Allowed Decisions (`GateDecision`) | SLA |
|------|------------------------|-----------------------------|------------------------------------|-----|
| `GATE_1` | `SCREENING` | `GRANTS_OFFICER`, `PROGRAM_OFFICER` | `APPROVE`, `REJECT`, `RETURN_FOR_FIXES` | 5 business days |
| `GATE_2` | `PEER_REVIEW` | `REVIEW_LEAD` | `RESOLVE_AND_CONTINUE`, `REMOVE_REVIEWER`, `OVERRIDE` | 2 business days |
| `GATE_3` | `PEER_REVIEW` | `HUMAN_REVIEWER` | `ACCEPT`, `EDIT`, `REJECT` | 3 business days |
| `GATE_4` | `AWARD` | `GRANTS_OFFICER` | `AWARD`, `DO_NOT_AWARD`, `RETURN_TO_REVIEW` | 10 business days |

Routing tables in `app/schemas/hitl.py`: `GATE_OWNER_ROLES`, `GATE_WORKFLOW_STAGE`, `GATE_ALLOWED_DECISIONS`, `GATE_BLOCKING_DECISIONS`.

---

## 3. Grounding Thresholds

Applied programmatically **before every gate** via `app/services/grounding.py`.

| `confidence_score` | `faithfulness_score` | Action |
|--------------------|----------------------|--------|
| ≥ 0.80 | ≥ 0.70 | Auto-proceed to gate owner |
| 0.65 – 0.79 | ≥ 0.70 | `LOW_CONFIDENCE` flag + `EscalationRecord` — still advance |
| < 0.65 | any | `BLOCK` — gate owner must release before AI retries |
| any | < 0.70 | `BLOCK` (citation mismatch — treated as confidence < 0.65) |

**Revision loop cap:** 3 per gate. Exceeding cap sets `override_flag = True` requirement on `GateDecisionRequest`.

> Note: `grounding.py` currently uses `CONFIDENCE_THRESHOLD = 0.70` and `FAITHFULNESS_THRESHOLD = 0.80` as internal service defaults. The thresholds in the table above are the HITL policy thresholds that govern gate routing; align both if they diverge.

---

## 4. Data Models

All Pydantic models live in `app/schemas/hitl.py`.

### 4.1 Stage-to-Stage Handoffs

```
User Input
  tenant_id, grant_application_id, raw_text, applicant fields
        ↓ sanitized + persisted
Intake Output
  + ai_run_id, audit_start_ts
        ↓ retrieval query
Retrieval Output
  retrieved_sources, citation_candidates, corpus_version
        ↓ context + citations
GroundedResponse
  answer, citation_refs, confidence_score, faithfulness_score,
  grounding_status, requires_human_review, human_review_reasons
        ↓ to gate owner
GateDecisionRequest
  actor_id, actor_role, decision, rationale, override_flag, evidence_refs
        ↓ decision persisted
GateDecisionRecord          EscalationRecord
  (append-only)               error_type, human_review_reason,
                              gate_id, ai_run_id
```

### 4.2 Key Model Fields

**`GroundedResponse`**
```python
answer: str
citations: List[Citation]
retrieved_sources: List[str]
citation_refs: List[str]
confidence_score: float          # 0.0 – 1.0
faithfulness_score: float        # 0.0 – 1.0
grounding_status: GroundingStatus
requires_human_review: bool
human_review_reasons: List[HumanReviewReason]
hitl_gate: Optional[GateId]
escalation_owner: Optional[str]
ai_run_id: str
```

**`GateDecisionRecord`** (append-only)
```python
gate_decision_id: str
gate_id: GateId
workflow_stage: WorkflowStage
actor_id: str
actor_role: GateOwnerRole
tenant_id: str
timestamp: datetime
ai_run_id: str
decision: GateDecision
rationale: str                   # min_length=1
override_flag: bool
evidence_refs: List[EvidenceRef]
retrieved_sources: List[str]
citation_refs: List[str]
confidence_score: float
grounding_status: GroundingStatus
```

**`EscalationRecord`**
```python
escalation_id: str
gate_id: GateId
gate_owner_roles: List[GateOwnerRole]
tenant_id: str
ai_run_id: str
reason: str
human_review_reasons: List[HumanReviewReason]
grounding_status: GroundingStatus
confidence_score: float
created_at: datetime
resolved: bool
resolved_at: Optional[datetime]
resolution_decision_id: Optional[str]
```

**`Citation`**
```python
chunk_id: str
source_id: str
section: Optional[str]
last_revised: Optional[str]
text_excerpt: Optional[str]
tenant_id: Optional[str]
regulation: Optional[str]        # e.g. "2CFR200", "45CFR75"
```

### 4.3 Enumerations

```python
class GroundingStatus(str, Enum):
    GROUNDED = "GROUNDED"
    UNGROUNDED = "UNGROUNDED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MISSING_CITATIONS = "MISSING_CITATIONS"
    CITATION_CONFLICT = "CITATION_CONFLICT"

class HumanReviewReason(str, Enum):
    CITATION_CONFLICT = "CITATION_CONFLICT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LOW_FAITHFULNESS = "LOW_FAITHFULNESS"
    REGULATORY_CONFLICT = "REGULATORY_CONFLICT"
    MISSING_CITATIONS = "MISSING_CITATIONS"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    CACHE_REVALIDATION_FAILED = "CACHE_REVALIDATION_FAILED"
    UNGROUNDED = "UNGROUNDED"
    FAR_DFARS_CONFLICT = "FAR_DFARS_CONFLICT"
```

---

## 5. Main Workflow: Intake → Screening → Peer Review → Award

### 5.1 Intake & Validation

**Endpoint:** `POST /agent/intake-triage`
**Request model:** `IntakeTriageRequest`

```python
class IntakeTriageRequest(BaseModel):
    proposal_id: str
    grant_application_id: Optional[str]
    raw_text: Optional[str]
```

Programmatic steps before any AI call:
1. Persist intake record, generate `ai_run_id`
2. Run `validate_before_generation` — injection fence, blocklist, schema check
3. Tenant-bound retrieval via `app/services/retrieval.py`
4. Idempotency check: `idempotency_store.check(ai_run_id)` — skip Bedrock if already complete

**Three sequential Bedrock calls (current impl in `main.py`):**
```python
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
```

**Response shape:**
```python
{
    "proposal_id": req.proposal_id,
    "classification": classify["body"],   # risk_tier, completeness
    "routing": route["body"],
    "anomalies": anomaly["body"],          # flagged_issues
    "escalation_required": "CO" if "anomaly" in anomaly["body"].lower() else None,
    "hitl_gate": "co-review-on-escalation",
    "model": BEDROCK_MODEL_ID,
}
```

### 5.2 Gate 1: Screening

**AI endpoint:** `POST /check-eligibility`
**Request model:** `EligibilityCheckRequest`

```python
class EligibilityCheckRequest(BaseModel):
    tenant_id: str
    grant_application_id: Optional[str]
    applicant_type: Optional[str]
    applicant_uei: Optional[str]
    assistance_listing_number: Optional[str]
    requested_amount_federal: Optional[float]
    raw_text: Optional[str]
```

AI produces eligibility/risk draft grounded on 2 CFR 200 / 45 CFR 75 corpus. Grounding validator runs; result flows to Gate 1 owner. Possible outcomes:

- `APPROVE` → `GateDecisionRecord` persisted (append-only), advance to reviewer assignment
- `REJECT` → Denial record, terminate workflow
- `RETURN_FOR_FIXES` → `revision_notes` appended, loop back to retrieval (max 3)

### 5.3 Gate 2: COI Resolution

Reviewer assignment + COI check run programmatically. Review Lead resolves:

- `RESOLVE_AND_CONTINUE` → proceed to Gate 3 AI step
- `REMOVE_REVIEWER` → reassign or escalate if panel exhausted

### 5.4 Gate 3: Factor Acceptance

**AI endpoint:** `POST /eval/factor-suggest`

Human Reviewer outcomes:

- `ACCEPT` → advance to Gate 4 AI step
- `EDIT` → `human_feedback` appended to prompt, re-run AI (max 3 loops)
- `REJECT` → `EscalationRecord`, escalate to Review Lead

### 5.5 Gate 4: Final Award

**AI endpoints:** `POST /eval/ssdd-draft`

Grants Officer outcomes:

- `AWARD` → `GateDecisionRecord` sealed, audit trail closed, workflow complete
- `DO_NOT_AWARD` → Denial record with `rationale` + `evidence_refs`, terminate — no revision at Gate 4

---

## 6. Side Workflows

### 6.1 Amendment Workflow

**Endpoint:** `POST /draft-amendment`

```python
# AmendmentRequest (inline dict — no dedicated model yet)
{
    "original_grant_application_id": str,
    "amendment_reason": str,
    "changed_sections": List[str],
}
```

1. Persist amendment, link to original `GateDecisionRecord` chain, generate new `ai_run_id`
2. Retrieval + `corpus_version` pin
3. AI drafts amended sections via `invoke_model()`
4. Grounding validator
5. Amendment Review Gate (Grants Officer, SLA 5 business days)
   - `APPROVE` → `AmendmentDecisionRecord` (append-only)
   - `REJECT` → denial record, original approval unchanged
   - `RETURN_FOR_FIXES` → `human_feedback` appended, loop ≤ 3

### 6.2 QA Workflow (no gate — informational only)

**Endpoint:** `POST /answer-qa`

```python
class QaDraftRequest(BaseModel):
    question: str
    grant_application_id: Optional[str]
    constraints: Optional[str]
```

Flow:
1. `validate_before_generation` — injection fence + blocklist
2. Retrieval: top-K chunks from 2 CFR 200 / 45 CFR 75; optional application context (tenant check)
3. AI generates answer
4. Grounding check:
   - Grounded → persist `QAResponse` with `ai_run_id`, return `answer_draft + citation_refs + disclaimer`
   - Ungrounded → return `INSUFFICIENT_GROUNDING`, no fabricated answer
5. If `grant_application_id` maps to live application → set `requires_human_review = True`, route to active gate owner

---

## 7. Retrieval & Caching

**Endpoint:** `POST /rag/v2/search`
**Router:** `app/routers/retrieval_v2.py`

```python
class RetrievalRequest(BaseModel):
    query: str
    tenant_id: str
    gate_context: Optional[str]
    application_data_hash: Optional[str]
    nofo_hash: Optional[str]
    reviewer_state_hash: Optional[str]
    policy_corpus_hash: Optional[str]
    coi_state_hash: Optional[str]
    award_package_hash: Optional[str]
    corpus_version: str = "v1"
    skip_cache: bool = False
```

Cache key: `sha256(f"{query}|{tenant_id}|{corpus_version}")` — TTL 24 hours (`CACHE_TTL_HOURS = 24`).

**Cache invalidation** (`POST /rag/v2/invalidate`):

```python
class InvalidationRequest(BaseModel):
    tenant_id: str
    trigger: InvalidationTrigger   # APPLICATION_DATA | NOFO_AMENDMENT | POLICY_CORPUS |
    resource_id: str               # REVIEWER_ASSIGNMENTS | COI_STATE | AWARD_PACKAGE
```

Atlas Vector Search (W2 wire-in):
- Index: `corpus_chunks_vector_idx`
- Collection: `corpus_chunks`
- Embedding model: `amazon.titan-embed-text-v2:0` (1024 dims)
- Filter fields: `tenant_id`, `regulation`

---

## 8. Bedrock Client

**File:** `app/bedrock_client.py`

```python
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-7-sonnet-20250219-v1:0",
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

def invoke_model(
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> dict[str, Any]:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    # Returns: {"body": str, "model": BEDROCK_MODEL_ID, "region": AWS_REGION, "stub": bool}
```

Auto-stubs when no AWS credentials are present (local dev / CI).

---

## 9. LangChain V1 Migration

> **Brownfield debt item 5** — `legacy_chain.py` uses pre-v1.0 `LLMChain`. Migration scheduled **W2**.

### 9.1 Current (Legacy) Pattern — `app/legacy_chain.py`

```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

def draft_with_legacy_chain(topic: str, constraints: str, llm) -> str:
    prompt = PromptTemplate(
        input_variables=["topic", "constraints"],
        template=(
            "You draft federal grant project narratives. "
            "Draft a paragraph about: {topic}. Constraints: {constraints}."
        ),
    )
    chain = LLMChain(llm=llm, prompt=prompt)   # ← debt item 5
    return chain.run(topic=topic, constraints=constraints or "none")
```

Exposed via `POST /draft-grant-application-v1` for cohort comparison.

### 9.2 Target (V1 LCEL) Pattern

Replace `LLMChain(...).run()` with a LangChain Expression Language (LCEL) runnable chain. Use the same prompt variables (`topic`, `constraints`) and the same Bedrock-backed LLM.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock

def build_draft_chain(model_id: str = BEDROCK_MODEL_ID, region: str = AWS_REGION):
    llm = ChatBedrock(
        model_id=model_id,
        region_name=region,
        model_kwargs={"temperature": 0.2, "max_tokens": 1024},
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You draft federal grant project narratives."),
        ("user", "Draft a paragraph about: {topic}. Constraints: {constraints}."),
    ])
    return prompt | llm | StrOutputParser()

# Invoke:
chain = build_draft_chain()
result: str = chain.invoke({"topic": topic, "constraints": constraints or "none"})
```

### 9.3 V1 Pattern for Eligibility / Grounded Endpoints

Eligibility draft with grounding context injected via retrieval output:

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock

ELIGIBILITY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You assess federal grant eligibility grounded strictly on provided regulatory context. "
        "Cite regulation sections. Never fabricate citations.",
    ),
    (
        "user",
        "Grant application: {grant_application_id}\n"
        "Applicant type: {applicant_type}\n"
        "UEI: {applicant_uei}\n"
        "Assistance listing: {assistance_listing_number}\n"
        "Federal amount requested: {requested_amount_federal}\n\n"
        "Regulatory context:\n{retrieved_sources}\n\n"
        "Provide eligibility assessment with citation_refs.",
    ),
])

def build_eligibility_chain(model_id: str = BEDROCK_MODEL_ID, region: str = AWS_REGION):
    llm = ChatBedrock(
        model_id=model_id,
        region_name=region,
        model_kwargs={"temperature": 0.2, "max_tokens": 1024},
    )
    return ELIGIBILITY_PROMPT | llm | StrOutputParser()
```

Invocation after retrieval:
```python
chain = build_eligibility_chain()
answer = chain.invoke({
    "grant_application_id": req.grant_application_id,
    "applicant_type": req.applicant_type,
    "applicant_uei": req.applicant_uei,
    "assistance_listing_number": req.assistance_listing_number,
    "requested_amount_federal": req.requested_amount_federal,
    "retrieved_sources": "\n\n".join(retrieval_output.retrieved_sources),
})
```

### 9.4 V1 Pattern for Intake Triage (Multi-Step)

Replace three sequential `invoke_model()` calls with three chained runnables sharing one LLM instance:

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_aws import ChatBedrock

def build_triage_chains(model_id: str = BEDROCK_MODEL_ID, region: str = AWS_REGION):
    llm = ChatBedrock(
        model_id=model_id,
        region_name=region,
        model_kwargs={"temperature": 0.2, "max_tokens": 512},
    )
    parser = StrOutputParser()

    classify_chain = (
        ChatPromptTemplate.from_messages([
            ("system", "You classify federal grant applications for merit-review-panel routing."),
            ("user", "Classify program area + complexity: {raw_text}"),
        ])
        | llm | parser
    )

    route_chain = (
        ChatPromptTemplate.from_messages([
            ("system", "You route applications to peer-review-panel members based on subject expertise."),
            ("user", "Recommend 3 peer reviewers for application_id={proposal_id}."),
        ])
        | llm | parser
    )

    anomaly_chain = (
        ChatPromptTemplate.from_messages([
            ("system", "You flag anomalies (completeness, eligibility, conflict of interest)."),
            ("user", "Flag anomalies in application_id={proposal_id} that warrant Program Officer escalation."),
        ])
        | llm | parser
    )

    return classify_chain, route_chain, anomaly_chain
```

### 9.5 Key Differences: Legacy vs V1

| Aspect | Legacy (`LLMChain`) | V1 (LCEL) |
|--------|---------------------|-----------|
| Composition | `LLMChain(llm=llm, prompt=prompt)` | `prompt \| llm \| parser` |
| Invocation | `chain.run(topic=..., constraints=...)` | `chain.invoke({"topic": ..., "constraints": ...})` |
| Streaming | Manual callback handlers | `chain.stream(inputs)` native |
| Async | `chain.arun()` | `await chain.ainvoke(inputs)` |
| Output | Raw string | Typed via `StrOutputParser` or custom parser |
| Tracing | Implicit | Native LangSmith via `with_config(run_name=...)` |

---

## 10. Audit Trail

**File:** `app/services/audit_trail.py`
**Collections:** `hitl_audit_trail`, `hitl_escalations`

All gate decisions and escalations are append-only. Record type distinguished by `_type: "gate_decision" | "escalation"`.

Gate decisions sealed at Gate 4 `AWARD`. Escalations resolved via `resolved = True`, `resolved_at`, `resolution_decision_id`.

---

## 11. Programmatic Control Checklist (per AI call)

1. `validate_before_generation` — injection fence + blocklist + schema
2. `idempotency_store.check(ai_run_id)` — skip if already complete
3. Tenant-bound retrieval — `cache_key = sha256(f"{query}|{tenant_id}|{corpus_version}")`
4. Grounding validator — `confidence_score`, `faithfulness_score`, `_has_citation_conflict()`, `_has_regulatory_conflict()`, `_has_far_dfars_conflict()`
5. Threshold routing → `GroundingStatus` → gate advance or `EscalationRecord`
6. SLA timer start on gate assignment; auto-escalation on breach
7. `GateDecisionRecord` appended on each gate resolution
