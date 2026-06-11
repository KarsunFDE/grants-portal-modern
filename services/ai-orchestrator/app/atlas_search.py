"""
Atlas Vector Search client — ADR 0006/0007 Phase B.

Local dev:   mongodb/mongodb-atlas-local (ATLAS_URI=mongodb://mongodb-atlas-local:27017)
Staging/prod: managed MongoDB Atlas connection string.

Schema and index definitions are identical across environments (ADR 0006 §2).

Feature flag: ATLAS_RETRIEVAL_ENABLED controls Atlas as the retrieval authority.
Default true (ADR 0009) — set false only to force Layer 2 fallback in isolated test environments.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import List

from pymongo import MongoClient
from pymongo.database import Database

from app.schemas.hitl import Citation

log = logging.getLogger("ai-orchestrator.atlas")

ATLAS_URI = os.getenv("ATLAS_URI", "mongodb://localhost:27017")
ATLAS_DB_NAME = os.getenv("ATLAS_DB_NAME", "grantsportal_retrieval")
ATLAS_RETRIEVAL_ENABLED = os.getenv("ATLAS_RETRIEVAL_ENABLED", "true").lower() == "true"

COLLECTION = "corpus_chunks"
VECTOR_INDEX = "corpus_chunks_vector_idx"
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSIONS = 1024  # titan-embed-text-v2 native dimension


@lru_cache(maxsize=1)
def _get_atlas_client() -> MongoClient:
    return MongoClient(ATLAS_URI, serverSelectionTimeoutMS=5000)


def get_atlas_db() -> Database:
    return _get_atlas_client()[ATLAS_DB_NAME]


# ---------------------------------------------------------------------------
# Bedrock embedding
# ---------------------------------------------------------------------------

def get_embedding(text: str) -> List[float]:
    """
    Embed text with Amazon Titan Text Embeddings v2 via Bedrock.
    boto3 imported lazily — keeps tests runnable without AWS deps installed.
    Raises RuntimeError on failure — callers must NOT fall back to a zero vector.
    ADR 0009 §4: zero vector yields cosine similarity of 0 for all docs (meaningless ranking).
    """
    try:
        import boto3  # lazy — not needed for non-Atlas paths
        client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        body = json.dumps({
            "inputText": text,
            "dimensions": EMBEDDING_DIMENSIONS,
            "normalize": True,
        })
        resp = client.invoke_model(modelId=EMBEDDING_MODEL_ID, body=body)
        return json.loads(resp["body"].read())["embedding"]
    except Exception as exc:
        raise RuntimeError(f"Bedrock embedding unavailable: {exc}") from exc


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def ensure_vector_index(db: Database) -> None:
    """
    Create the Atlas vector search index on corpus_chunks if absent.
    Safe to call on every startup — no-ops if the index already exists.

    Index spec (same definition required for managed Atlas — ADR 0006 §2, ADR 0009 §2):
      - vector field: embedding (1024d cosine, titan-embed-text-v2)
      - filter fields: tenant_id, regulation, source_id, last_revised
    """
    try:
        existing_names = {idx.get("name") for idx in db[COLLECTION].list_search_indexes()}
        if VECTOR_INDEX in existing_names:
            return
        db.command({
            "createSearchIndexes": COLLECTION,
            "indexes": [{
                "name": VECTOR_INDEX,
                "type": "vectorSearch",
                "definition": {
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": EMBEDDING_DIMENSIONS,
                            "similarity": "cosine",
                        },
                        {"type": "filter", "path": "tenant_id"},
                        {"type": "filter", "path": "regulation"},
                        {"type": "filter", "path": "source_id"},
                        {"type": "filter", "path": "last_revised"},
                    ]
                },
            }],
        })
        log.info("Created Atlas vector search index: %s", VECTOR_INDEX)
    except Exception as exc:
        log.warning("ensure_vector_index: %s", exc)


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------

# Reserved system tenant — shared regulatory corpus only.
# Must be the exact string used at ingestion; no alternate forms permitted.
_GLOBAL_TENANT = "__global__"

# Case-folded variants that must also be rejected at the request boundary.
_RESERVED_TENANT_FORMS = {"__global__", "global", "GLOBAL", "__GLOBAL__"}


def _reject_reserved_tenant(tenant_id: str) -> None:
    """
    Raise ValueError if the caller-supplied tenant_id is the reserved system marker.
    A caller who supplies '__global__' is indistinguishable from the shared corpus
    and could read all global chunks while bypassing normal tenant scoping.
    """
    if tenant_id.strip().lower() in {t.lower() for t in _RESERVED_TENANT_FORMS}:
        raise ValueError(
            f"tenant_id '{tenant_id}' is a reserved system value and cannot be used "
            "as a caller tenant identifier. Supply an authority-issued tenant ID."
        )


def vector_search(
    query_text: str,
    tenant_id: str,
    limit: int = 5,
) -> List[Citation]:
    """
    Run $vectorSearch against corpus_chunks.

    Tenant filter: matches tenant_id OR '__global__' so shared regulatory corpus
    (2 CFR 200, 45 CFR 75) is always reachable regardless of caller tenant.
    ADR 0009 §6: '__global__' is the exact required string; no alternate forms.

    Raises ValueError if tenant_id is the reserved '__global__' marker.
    Returns empty list on any other error — caller falls through to Layer 2.
    On Bedrock embedding failure, logs bedrock_embedding_failed and skips vector search.
    ADR 0009 §4: never use zero vector as query input.
    """
    _reject_reserved_tenant(tenant_id)
    if not ATLAS_RETRIEVAL_ENABLED:
        return []
    try:
        db = get_atlas_db()
        try:
            query_embedding = get_embedding(query_text)
        except RuntimeError as emb_exc:
            log.error(
                "bedrock_embedding_failed — skipping vector search, falling to Layer 2: %s",
                emb_exc,
            )
            return []
        pipeline = [
            {
                "$vectorSearch": {
                    "index": VECTOR_INDEX,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": max(150, limit * 15),
                    "limit": limit,
                    "filter": {
                        "tenant_id": {"$in": [tenant_id, "__global__"]},
                    },
                }
            },
            {
                "$project": {
                    "chunk_id": 1,
                    "source_id": 1,
                    "section": 1,
                    "subsection": 1,
                    "section_title": 1,
                    "last_revised": 1,
                    "text_excerpt": 1,
                    "regulation": 1,
                    "tenant_id": 1,
                    "score": {"$meta": "vectorSearchScore"},
                    "_id": 0,
                }
            },
        ]
        docs = list(db[COLLECTION].aggregate(pipeline))
        results = []
        for doc in docs:
            doc_tenant = doc.get("tenant_id")
            # Post-retrieval tenant guard — defence-in-depth beyond the Atlas pre-filter.
            # Drop any document whose tenant_id is neither the caller's tenant nor the
            # reserved global marker. A misconfigured index or filter bypass must not
            # leak another tenant's chunks into the caller's result set.
            if doc_tenant not in (tenant_id, _GLOBAL_TENANT):
                log.error(
                    "tenant_leak_detected chunk_id=%s doc_tenant=%s caller_tenant=%s — dropped",
                    doc.get("chunk_id"), doc_tenant, tenant_id,
                )
                continue
            results.append(Citation(
                chunk_id=doc["chunk_id"],
                source_id=doc["source_id"],
                section=doc.get("section"),
                subsection=doc.get("subsection"),
                section_title=doc.get("section_title"),
                last_revised=doc.get("last_revised"),
                text_excerpt=doc.get("text_excerpt"),
                tenant_id=doc_tenant,
                regulation=doc.get("regulation"),
                relevance_score=doc.get("score"),
            ))
        return results
    except Exception as exc:
        log.warning("Atlas vector_search failed (%s) — falling to Layer 2 (MongoDB text search)", exc)
        return []
