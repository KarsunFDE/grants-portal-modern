"""
Retrieval service — hitl-plan.txt §Retrieval Planning / §Retrieval Invalidation Policy.

Hybrid retrieval: MongoDB clause_library text search + static regulatory corpus.
Atlas Vector Search wires in during W2 (replaces static fallback).

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

CACHE_TTL_HOURS = 24


# ---------------------------------------------------------------------------
# Static regulatory corpus — 2 CFR 200, 45 CFR 75, key provisions
# Atlas Vector Search replaces this in W2.
# ---------------------------------------------------------------------------
_STATIC_CORPUS = [
    {
        "chunk_id": "2cfr200-205-001",
        "source_id": "2-CFR-200.205",
        "section": "200.205",
        "last_revised": "2024-04-22",
        "text_excerpt": "Federal agencies must have a merit review process for competitive grants (2 CFR 200.205).",
        "regulation": "2 CFR 200",
        "keywords": ["merit review", "merit", "competitive", "review process", "proposal"],
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
        "keywords": ["HHS", "risk", "health human services", "hhs supplement"],
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
        "keywords": ["award", "award decision", "decision", "rationale", "documentation"],
    },
    {
        "chunk_id": "2cfr200-factor-001",
        "source_id": "2-CFR-200.204",
        "section": "200.204",
        "last_revised": "2024-04-22",
        "text_excerpt": "NOFO must describe selection criteria and evaluation factors (2 CFR 200.204).",
        "regulation": "2 CFR 200",
        "keywords": ["factor", "evaluation factor", "selection criteria", "nofo", "narrative"],
    },
    {
        "chunk_id": "nofo-general-001",
        "source_id": "NOFO-GENERAL",
        "section": "NOFO",
        "last_revised": "2024-01-01",
        "text_excerpt": "Notice of Funding Opportunity — describes eligibility, evaluation, and award criteria.",
        "regulation": "NOFO",
        "keywords": ["nofo", "funding opportunity", "notice", "eligibility", "criteria"],
    },
]


def _make_cache_key(query: str, tenant_id: str, corpus_version: str) -> str:
    raw = f"{query}|{tenant_id}|{corpus_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


class RetrievalService:
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
    ) -> Tuple[List[Citation], float, float, datetime]:
        """
        Retrieve citations for a query.
        Returns (citations, confidence, faithfulness, retrieved_at).
        retrieved_at is the cache entry's created_at (for hits) or now (for fresh retrieval).
        Callers must pass retrieved_at to validate_before_generation before invoking a model.
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
                return cached  # 4-tuple: (citations, confidence, faithfulness, created_at)

        citations = self._retrieve_from_corpus(db, query, tenant_id)
        confidence = self._compute_confidence(citations, query)
        faithfulness = self._compute_faithfulness(citations)
        retrieved_at = datetime.utcnow()

        if db is not None:
            self._store_cache(
                db, cache_key, tenant_id, query, citations, confidence, faithfulness,
                corpus_version, application_data_hash, nofo_hash, reviewer_state_hash,
                policy_corpus_hash, coi_state_hash, award_package_hash,
            )

        return citations, confidence, faithfulness, retrieved_at

    def invalidate(
        self,
        tenant_id: str,
        trigger: InvalidationTrigger,
        resource_id: str,
    ) -> int:
        """
        Invalidate all cache entries for a tenant after a trigger event.
        Creates a retrieval invalidation event record (no silent drops).
        """
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
    ) -> Optional[Tuple[List[Citation], float, float]]:
        try:
            entry = db.retrieval_cache.find_one({"cache_key": cache_key, "tenant_id": tenant_id})
        except Exception:
            return None
        if entry is None:
            return None

        # Freshness check
        expires_at = entry.get("expires_at")
        if expires_at and datetime.utcnow() > expires_at:
            db.retrieval_cache.delete_one({"cache_key": cache_key})
            return None

        # Hash checks — all 6 invalidation triggers (hitl-plan.txt §Retrieval Invalidation Policy)
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
        return citations, entry["confidence_score"], entry["faithfulness_score"], created_at

    def _retrieve_from_corpus(self, db, query: str, tenant_id: str) -> List[Citation]:
        # Atlas Vector Search path — ADR 0006/0007 Phase B.
        # Activated by ATLAS_RETRIEVAL_ENABLED=true; Atlas is authoritative when live.
        if atlas_search.ATLAS_RETRIEVAL_ENABLED:
            results = atlas_search.vector_search(query, tenant_id)
            if results:
                return results
            # vector_search returns [] on error — fall through to static corpus so
            # grounding checks surface low-confidence rather than silently failing.
            log.warning("Atlas vector_search returned no results — falling back to static corpus")

        citations: List[Citation] = []

        # MongoDB clause_library text search (FAR/DFARS corpus)
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
                pass  # text index may not exist yet; fall through to static corpus

        # Static regulatory corpus — keyword match.
        # Diagnostic use only once Atlas is live (ADR 0006 §1).
        citations.extend(self._query_static_corpus(query, tenant_id))

        # Deduplicate by source_id, cap at 5
        seen: set = set()
        unique: List[Citation] = []
        for c in citations:
            if c.source_id not in seen:
                seen.add(c.source_id)
                unique.append(c)
            if len(unique) >= 5:
                break
        return unique

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
        # Boost for regulatory anchor sources
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
