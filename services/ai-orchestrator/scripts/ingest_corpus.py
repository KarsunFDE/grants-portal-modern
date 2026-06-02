"""
Corpus ingestion script — ADR 0007 Phase B.

Embeds regulatory corpus chunks with Bedrock Titan Text Embeddings v2 and
upserts them into the Atlas Local corpus_chunks collection.  Run once (or on
corpus updates) before flipping ATLAS_RETRIEVAL_ENABLED=true.

Usage:
    # From services/ai-orchestrator/
    ATLAS_URI=mongodb://localhost:27018 python scripts/ingest_corpus.py

    # Or inside docker network after stack is up:
    docker exec -e ATLAS_URI=mongodb://mongodb-atlas-local:27017 \
        grants-portal-modern-ai-orchestrator-1 \
        python scripts/ingest_corpus.py

Environment variables:
    ATLAS_URI         - Atlas Local connection string (default: mongodb://localhost:27018)
    ATLAS_DB_NAME     - Database name (default: grantsportal_retrieval)
    AWS_REGION        - Bedrock region (default: us-east-1)
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN — if not using instance role
"""
from __future__ import annotations

import logging
import os
import sys

# Allow running from repo root or scripts/ dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ATLAS_URI", "mongodb://localhost:27018")
os.environ.setdefault("ATLAS_RETRIEVAL_ENABLED", "true")  # needed so imports resolve

from app.atlas_search import (  # noqa: E402
    COLLECTION,
    get_atlas_db,
    get_embedding,
    ensure_vector_index,
)
from app.services.retrieval import _STATIC_CORPUS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest_corpus")

# Tenant tag for shared regulatory corpus — all tenants can read these chunks.
GLOBAL_TENANT = "global"


def build_document(entry: dict) -> dict:
    text = entry["text_excerpt"]
    log.info("Embedding %s ...", entry["source_id"])
    embedding = get_embedding(text)
    return {
        "chunk_id": entry["chunk_id"],
        "source_id": entry["source_id"],
        "section": entry.get("section"),
        "last_revised": entry.get("last_revised"),
        "text_excerpt": text,
        "regulation": entry.get("regulation"),
        "tenant_id": GLOBAL_TENANT,
        "embedding": embedding,
    }


def ingest() -> None:
    db = get_atlas_db()

    log.info("Ensuring Atlas vector search index ...")
    ensure_vector_index(db)

    log.info("Ingesting %d corpus chunks into %s ...", len(_STATIC_CORPUS), COLLECTION)
    inserted = updated = 0
    for entry in _STATIC_CORPUS:
        doc = build_document(entry)
        result = db[COLLECTION].replace_one(
            {"chunk_id": doc["chunk_id"]},
            doc,
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        else:
            updated += 1

    log.info("Done. inserted=%d updated=%d", inserted, updated)
    log.info(
        "Next step: set ATLAS_RETRIEVAL_ENABLED=true in docker-compose ai-orchestrator "
        "environment and restart the service to activate Atlas retrieval (ADR 0007 Phase D)."
    )


if __name__ == "__main__":
    ingest()
