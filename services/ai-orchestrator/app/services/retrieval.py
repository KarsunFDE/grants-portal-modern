"""
Retrieval service — hitl-plan.txt §Retrieval Planning / §Retrieval Invalidation Policy.

Hybrid retrieval: Atlas Vector Search (Layer 1) → MongoDB text search (Layer 2)
→ static regulatory corpus (Layer 3 fallback — keeps demo grounded before corpus ingestion).

Invalidation: per hitl-plan.txt, re-retrieval is required when application data,
NOFO/amendment, policy corpus version, reviewer assignments/COI state, or award
package content changes. Cache hits blocked and escalated if any check fails.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from app import atlas_search
from app.db import get_db
from app.schemas.hitl import (
    Citation,
    GroundingStatus,
    InvalidationTrigger,
    RetrievalInvalidationEvent,
)

log = logging.getLogger("ai-orchestrator.retrieval")

try:
    from langsmith import traceable as _traceable
except ImportError:  # pragma: no cover
    def _traceable(**_kw):
        def _d(fn): return fn
        return _d

CACHE_TTL_HOURS = 24


# ---------------------------------------------------------------------------
# Static regulatory corpus — Layer 3 fallback.
# Used when Atlas vector search and MongoDB text search both return nothing
# (e.g., before ingest_corpus.py has been run or Titan embeddings unavailable).
# Keywords are lowercase for case-insensitive matching against the query.
# ---------------------------------------------------------------------------
_STATIC_CORPUS = [
    {
        "chunk_id": "2cfr200-205-001",
        "source_id": "2-CFR-200.205",
        "section": "200.205",
        "last_revised": "2024-04-22",
        "text_excerpt": "Federal agencies must have a merit review process for competitive grants (2 CFR 200.205).",
        "regulation": "2 CFR 200",
        "keywords": ["merit review", "merit", "competitive", "review process", "proposal",
                     "evaluation", "scoring", "criterion"],
    },
    {
        "chunk_id": "2cfr200-206-001",
        "source_id": "2-CFR-200.206",
        "section": "200.206",
        "last_revised": "2024-04-22",
        "text_excerpt": "Federal agencies must evaluate risks posed by applicants (2 CFR 200.206).",
        "regulation": "2 CFR 200",
        "keywords": ["risk", "risk review", "risk assessment", "applicant risk", "eligibility"],
    },
    {
        "chunk_id": "45cfr75-206-001",
        "source_id": "45-CFR-75.206",
        "section": "75.206",
        "last_revised": "2023-10-01",
        "text_excerpt": "HHS supplement — risk evaluation for HHS grant applicants (45 CFR 75.206).",
        "regulation": "45 CFR 75",
        "keywords": ["hhs", "risk", "health human services", "hhs supplement"],
    },
    {
        "chunk_id": "2cfr200-coi-001",
        "source_id": "2-CFR-200.318",
        "section": "200.318",
        "last_revised": "2024-04-22",
        "text_excerpt": "Conflict of interest requirements for federal grant procurement (2 CFR 200.318).",
        "regulation": "2 CFR 200",
        "keywords": ["conflict of interest", "coi", "reviewer", "panel", "disclosure"],
    },
    {
        "chunk_id": "2cfr200-award-001",
        "source_id": "2-CFR-200.212",
        "section": "200.212",
        "last_revised": "2024-04-22",
        "text_excerpt": "Award decisions must be documented with a written record of rationale (2 CFR 200.212).",
        "regulation": "2 CFR 200",
        "keywords": ["award", "award decision", "decision", "rationale", "documentation",
                     "recommendation", "funding recommendation", "funding"],
    },
    {
        "chunk_id": "2cfr200-factor-001",
        "source_id": "2-CFR-200.204",
        "section": "200.204",
        "last_revised": "2024-04-22",
        "text_excerpt": "NOFO must describe selection criteria and evaluation factors (2 CFR 200.204).",
        "regulation": "2 CFR 200",
        "keywords": ["factor", "evaluation factor", "selection criteria", "nofo", "narrative",
                     "criterion", "criteria", "merit criterion"],
    },
    {
        "chunk_id": "nofo-general-001",
        "source_id": "NOFO-GENERAL",
        "section": "NOFO",
        "last_revised": "2024-01-01",
        "text_excerpt": "Notice of Funding Opportunity — describes eligibility, evaluation, and award criteria.",
        "regulation": "NOFO",
        "keywords": ["nofo", "funding opportunity", "notice", "eligibility", "criteria",
                     "criterion", "factors", "funding", "recommendation"],
    },
    {
        "chunk_id": "45cfr75-merit-001",
        "source_id": "45-CFR-75.205",
        "section": "75.205",
        "last_revised": "2023-10-01",
        "text_excerpt": "HHS agencies must apply merit review evaluation criteria for competitive grant awards (45 CFR 75.205).",
        "regulation": "45 CFR 75",
        "keywords": ["merit", "evaluation", "criterion", "criteria", "merit review",
                     "evaluation criteria", "scoring", "factor"],
    },
    {
        "chunk_id": "45cfr75-award-001",
        "source_id": "45-CFR-75.210",
        "section": "75.210",
        "last_revised": "2023-10-01",
        "text_excerpt": "HHS post-award requirements: award decisions must document funding recommendations and rationale (45 CFR 75.210).",
        "regulation": "45 CFR 75",
        "keywords": ["award", "award decision", "funding", "recommendation",
                     "funding recommendation", "post-award", "decision"],
    },
]


def _filter_superseded_amendments(citations: List[Citation]) -> List[Citation]:
    """
    ADR 0009 §11: when the same source_id has chunks at multiple last_revised dates,
    keep ALL chunks whose revision matches the latest date for that source_id.
    """
    latest_date: dict = {}
    for c in citations:
        if not c.source_id or not c.last_revised:
            continue
        existing = latest_date.get(c.source_id)
        if existing is None or c.last_revised > existing:
            latest_date[c.source_id] = c.last_revised

    result: List[Citation] = []
    for c in citations:
        if not c.source_id:
            result.append(c)
            continue
        best_date = latest_date.get(c.source_id)
        if best_date is None:
            result.append(c)
        elif c.last_revised is None or c.last_revised == best_date:
            result.append(c)
    return result


def _make_cache_key(query: str, tenant_id: str, corpus_version: str) -> str:
    # ADR 0009 §7: normalize before hashing so "Merit Review" and "merit review" collide.
    normalized = query.lower().strip()
    raw = f"{normalized}|{tenant_id}|{corpus_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


class RetrievalService:
    @_traceable(name="retrieval_service.retrieve", run_type="retriever", tags=["rag", "2cfr200"])
    def retrieve(
        self,
        query: str,
        tenant_id: str,
        application_data_hash: Optional[str] = None,
        nofo_hash: Optional[str] = None,
        reviewer_state_hash: Optional[str] = None,
        policy_corpus_hash: Optional[str] = None,
        coi_state_hash: Optional[str] = None,
        award_package_hash: Optional[str] = None,
        corpus_version: str = "v1",
        skip_cache: bool = False,
    ) -> Tuple[List[Citation], float, float, datetime, str, bool]:
        """
        Retrieve citations for a query.
        Returns (citations, confidence, faithfulness, retrieved_at, retrieval_strategy, is_cache_hit).
        retrieval_strategy: "atlas" | "mongodb_text" | "static" | "cache"
        """
        db = self._safe_get_db()
        cache_key = _make_cache_key(query, tenant_id, corpus_version)

        if not skip_cache and db is not None:
            cached = self._check_cache(
                db, cache_key, tenant_id,
                application_data_hash, nofo_hash, reviewer_state_hash,
                policy_corpus_hash, coi_state_hash, award_package_hash,
            )
            if cached is not None:
                citations, confidence, faithfulness, created_at, original_strategy = cached
                return citations, confidence, faithfulness, created_at, original_strategy, True

        citations, retrieval_strategy = self._retrieve_from_corpus(db, query, tenant_id)
        citations = _filter_superseded_amendments(citations)
        confidence = self._compute_confidence(citations, query)
        faithfulness = self._compute_faithfulness(citations)
        retrieved_at = datetime.utcnow()

        if db is not None:
            self._store_cache(
                db, cache_key, tenant_id, query, citations, confidence, faithfulness,
                corpus_version, application_data_hash, nofo_hash, reviewer_state_hash,
                policy_corpus_hash, coi_state_hash, award_package_hash,
                retrieval_strategy=retrieval_strategy,
            )

        return citations, confidence, faithfulness, retrieved_at, retrieval_strategy, False

    def invalidate(
        self,
        tenant_id: str,
        trigger: InvalidationTrigger,
        resource_id: str,
    ) -> int:
        db = self._safe_get_db()
        count = 0
        if db is not None:
            try:
                result = db.retrieval_cache.delete_many({"tenant_id": tenant_id})
                count = result.deleted_count
                event = RetrievalInvalidationEvent(
                    tenant_id=tenant_id,
                    trigger=trigger,
                    resource_id=resource_id,
                )
                db.retrieval_invalidation_events.insert_one(event.model_dump())
            except Exception as exc:
                log.warning("retrieval invalidation db error: %s", exc)
        return count

    def _safe_get_db(self):
        try:
            return get_db()
        except Exception:
            return None

    def _check_cache(
        self,
        db,
        cache_key: str,
        tenant_id: str,
        application_data_hash: Optional[str],
        nofo_hash: Optional[str],
        reviewer_state_hash: Optional[str],
        policy_corpus_hash: Optional[str] = None,
        coi_state_hash: Optional[str] = None,
        award_package_hash: Optional[str] = None,
    ) -> Optional[Tuple[List[Citation], float, float, datetime, str]]:
        try:
            entry = db.retrieval_cache.find_one({"cache_key": cache_key, "tenant_id": tenant_id})
        except Exception:
            return None
        if entry is None:
            return None

        expires_at = entry.get("expires_at")
        if expires_at and datetime.utcnow() > expires_at:
            db.retrieval_cache.delete_one({"cache_key": cache_key})
            return None

        for field, value in [
            ("application_data_hash", application_data_hash),
            ("nofo_hash", nofo_hash),
            ("reviewer_state_hash", reviewer_state_hash),
            ("policy_corpus_hash", policy_corpus_hash),
            ("coi_state_hash", coi_state_hash),
            ("award_package_hash", award_package_hash),
        ]:
            if value and entry.get(field) != value:
                db.retrieval_cache.delete_one({"cache_key": cache_key})
                return None

        citations = [Citation(**c) for c in entry.get("citations", [])]
        raw_ts = entry.get("created_at")
        if isinstance(raw_ts, datetime):
            created_at = raw_ts
        elif isinstance(raw_ts, str):
            created_at = datetime.fromisoformat(raw_ts)
        else:
            created_at = datetime.utcnow()
        original_strategy = entry.get("retrieval_strategy", "static")
        return citations, entry["confidence_score"], entry["faithfulness_score"], created_at, original_strategy

    def _retrieve_from_corpus(self, db, query: str, tenant_id: str) -> Tuple[List[Citation], str]:
        """
        Returns (citations, retrieval_strategy).
        Layer 1: Atlas Vector Search.
        Layer 2: MongoDB clause_library text search.
        Layer 3: Static regulatory corpus (keyword match — fallback before corpus ingestion).
        """
        # Layer 1: Atlas Vector Search
        if atlas_search.ATLAS_RETRIEVAL_ENABLED:
            results = atlas_search.vector_search(query, tenant_id)
            if results:
                log.info("retrieval_strategy=atlas citations=%d query=%r", len(results), query[:60])
                return results, "atlas"
            log.warning("Atlas vector_search returned no results — falling to Layer 2")

        citations: List[Citation] = []

        # Layer 2: MongoDB clause_library text search
        if db is not None:
            try:
                results = list(
                    db.clause_library.find(
                        {"$text": {"$search": query}},
                        {"score": {"$meta": "textScore"}, "clauseId": 1, "farPart": 1,
                         "title": 1, "body": 1, "lastRevised": 1},
                        limit=3,
                    ).sort([("score", {"$meta": "textScore"})])
                )
                for doc in results:
                    cid = str(doc.get("_id", uuid.uuid4()))
                    far_part = doc.get("farPart", "")
                    citations.append(Citation(
                        chunk_id=cid,
                        source_id=doc.get("clauseId", cid),
                        section=far_part,
                        last_revised=doc.get("lastRevised"),
                        text_excerpt=(doc.get("body") or "")[:200] or None,
                        tenant_id=tenant_id,
                        regulation="DFARS" if "DFARS" in far_part.upper() else "FAR",
                    ))
            except Exception:
                pass

        if citations:
            seen: set = set()
            unique: List[Citation] = []
            for c in citations:
                if c.source_id not in seen:
                    seen.add(c.source_id)
                    unique.append(c)
                if len(unique) >= 5:
                    break
            log.info("retrieval_strategy=mongodb_text citations=%d", len(unique))
            return unique, "mongodb_text"

        # Layer 3: Static regulatory corpus — keyword match
        static_hits = self._query_static_corpus(query, tenant_id)
        log.info("retrieval_strategy=static citations=%d query=%r", len(static_hits), query[:60])
        return static_hits, "static"

    def _query_static_corpus(self, query: str, tenant_id: str) -> List[Citation]:
        q = query.lower()
        results: List[Citation] = []
        for entry in _STATIC_CORPUS:
            if any(k in q for k in entry["keywords"]):
                results.append(Citation(
                    chunk_id=entry["chunk_id"],
                    source_id=entry["source_id"],
                    section=entry["section"],
                    last_revised=entry["last_revised"],
                    text_excerpt=entry["text_excerpt"],
                    tenant_id=tenant_id,
                    regulation=entry["regulation"],
                ))
        return results

    def _compute_confidence(self, citations: List[Citation], query: str) -> float:
        if not citations:
            return 0.0
        base = min(len(citations) * 0.15, 0.70)
        has_reg = any(c.regulation in ("2 CFR 200", "45 CFR 75") for c in citations)
        has_nofo = any(c.regulation == "NOFO" for c in citations)
        if has_reg:
            base += 0.15
        if has_nofo:
            base += 0.05
        return min(round(base, 2), 0.95)

    def _compute_faithfulness(self, citations: List[Citation]) -> float:
        if not citations:
            return 0.0
        return min(round(0.60 + len(citations) * 0.07, 2), 0.95)

    def _store_cache(
        self,
        db,
        cache_key: str,
        tenant_id: str,
        query: str,
        citations: List[Citation],
        confidence: float,
        faithfulness: float,
        corpus_version: str,
        application_data_hash: Optional[str],
        nofo_hash: Optional[str],
        reviewer_state_hash: Optional[str],
        policy_corpus_hash: Optional[str] = None,
        coi_state_hash: Optional[str] = None,
        award_package_hash: Optional[str] = None,
        retrieval_strategy: Optional[str] = None,
    ) -> None:
        try:
            now = datetime.utcnow()
            db.retrieval_cache.replace_one(
                {"cache_key": cache_key},
                {
                    "cache_key": cache_key,
                    "tenant_id": tenant_id,
                    "query": query,
                    "citations": [c.model_dump() for c in citations],
                    "confidence_score": confidence,
                    "faithfulness_score": faithfulness,
                    "grounding_status": (
                        GroundingStatus.GROUNDED.value if citations else GroundingStatus.UNGROUNDED.value
                    ),
                    "corpus_version": corpus_version,
                    "retrieval_strategy": retrieval_strategy,
                    "application_data_hash": application_data_hash,
                    "nofo_hash": nofo_hash,
                    "reviewer_state_hash": reviewer_state_hash,
                    "policy_corpus_hash": policy_corpus_hash,
                    "coi_state_hash": coi_state_hash,
                    "award_package_hash": award_package_hash,
                    "created_at": now,
                    "expires_at": now + timedelta(hours=CACHE_TTL_HOURS),
                },
                upsert=True,
            )
        except Exception as exc:
            log.warning("retrieval cache store error: %s", exc)


retrieval_service = RetrievalService()
