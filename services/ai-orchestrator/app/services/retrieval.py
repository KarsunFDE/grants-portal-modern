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


def _filter_superseded_amendments(citations: List[Citation]) -> List[Citation]:
    """
    ADR 0009 §11: when the same source_id has chunks at multiple last_revised dates,
    keep ALL chunks whose revision matches the latest date for that source_id.

    Keying only on source_id (prior bug) collapsed multiple valid sections/subsections
    from the same source down to a single chunk, losing all co-resident citations.
    Fix: determine the latest revision date per source_id, then retain every chunk
    that belongs to that revision — not just one representative chunk.
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
            # source has no dated citations — keep all undated chunks for this source
            result.append(c)
        elif c.last_revised is None or c.last_revised == best_date:
            result.append(c)
        # else: older revision — drop
    return result


def _make_cache_key(query: str, tenant_id: str, corpus_version: str) -> str:
    # ADR 0009 §7: normalize before hashing so "Merit Review" and "merit review" collide.
    normalized = query.lower().strip()
    raw = f"{normalized}|{tenant_id}|{corpus_version}"
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
    ) -> Tuple[List[Citation], float, float, datetime, str, bool]:
        """
        Retrieve citations for a query.
        Returns (citations, confidence, faithfulness, retrieved_at, retrieval_strategy, is_cache_hit).
        retrieval_strategy: "atlas" | "mongodb_text" | "static" | "cache"
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
                citations, confidence, faithfulness, created_at, original_strategy = cached
                # Pass original_strategy so cache_validator runs the correct existence check.
                # Cache hits with Atlas-sourced citations still verify chunk_ids in corpus_chunks.
                return citations, confidence, faithfulness, created_at, original_strategy, True

        citations, is_static_only, retrieval_strategy = self._retrieve_from_corpus(db, query, tenant_id)
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
    ) -> Optional[Tuple[List[Citation], float, float, datetime, str]]:
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
        # Return original retrieval_strategy so existence check fires correctly on cache hits.
        # Old entries without the field default to None — existence check is skipped for those.
        original_strategy = entry.get("retrieval_strategy")
        return citations, entry["confidence_score"], entry["faithfulness_score"], created_at, original_strategy

    def _retrieve_from_corpus(
        self, db, query: str, tenant_id: str
    ) -> Tuple[List[Citation], bool, str]:
        """
        Returns (citations, is_static_only, retrieval_strategy).
        retrieval_strategy: "atlas" | "mongodb_text"
        """
        # Atlas Vector Search path — ADR 0006/0007 Phase B.
        if atlas_search.ATLAS_RETRIEVAL_ENABLED:
            results = atlas_search.vector_search(query, tenant_id)
            if results:
                return results, False, "atlas"
            log.warning("Atlas vector_search returned no results — falling back to Layer 2")

        citations: List[Citation] = []

        # Layer 2: MongoDB clause_library text search (FAR/DFARS corpus)
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
                pass  # text index may not exist yet

        # Deduplicate and cap at 5
        seen: set = set()
        unique: List[Citation] = []
        for c in citations:
            if c.source_id not in seen:
                seen.add(c.source_id)
                unique.append(c)
            if len(unique) >= 5:
                break

        # Return what Layer 2 found (may be empty — caller handles HITL escalation).
        # ADR 0007: static corpus is ingestion-only; not a runtime retrieval fallback.
        return unique, False, "mongodb_text"

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
