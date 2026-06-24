"""
Corpus ingestion script — ADR 0007 Phase B.

Embeds regulatory corpus chunks with Bedrock Titan Text Embeddings v2 and
upserts them into the Atlas Local corpus_chunks collection.  Run once (or on
corpus updates). Atlas retrieval is enabled by default (ADR 0009).

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

import hashlib
import logging
import os
import sys

# Allow running from repo root or scripts/ dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ATLAS_URI", "mongodb://localhost:27018")
os.environ.setdefault("ATLAS_RETRIEVAL_ENABLED", "true")  # needed so imports resolve

from app.atlas_search import (  # noqa: E402
    COLLECTION,
    EMBEDDING_MODEL_ID,
    get_atlas_db,
    get_embedding,
    ensure_vector_index,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest_corpus")

# ADR 0009 §6: exact string required; no alternate forms ("global", "GLOBAL") permitted.
GLOBAL_TENANT = "__global__"

# ADR 0009 §12: content without provenance MUST NOT be indexed.
# CORPUS_APPROVER_ID must be an explicit, real approver identifier — no default fallback.
# Set via environment: CORPUS_APPROVER_ID=firstname.lastname@agency.gov
INGESTION_ACTOR = os.getenv("INGESTION_ACTOR", "ingest_corpus.py")
APPROVER_ID = os.getenv("CORPUS_APPROVER_ID", "")

_REGULATION_SOURCE_URIS = {
    "2 CFR 200": "https://www.ecfr.gov/current/title-2/part-200",
    "45 CFR 75": "https://www.ecfr.gov/current/title-45/part-75",
    "NOFO": "agency-provided",
}


def _validate_provenance(doc: dict) -> None:
    """
    ADR 0009 §12: reject documents with missing or placeholder provenance before any upsert.
    Aborts by raising ValueError — caller must not proceed with ingestion.
    """
    source_uri = doc.get("source_uri", "")
    approver = doc.get("approver_id", "")
    if not source_uri or source_uri == "unknown":
        raise ValueError(
            f"chunk_id={doc.get('chunk_id')}: source_uri is missing or 'unknown'. "
            "Provide an explicit URI before indexing."
        )
    if not approver:
        raise ValueError(
            f"chunk_id={doc.get('chunk_id')}: approver_id is empty. "
            "Set CORPUS_APPROVER_ID env var to an explicit approver identifier "
            "(e.g. firstname.lastname@agency.gov)."
        )

# Regulatory seed corpus — embedded here so ingestion has no dependency on retrieval.py.
# This is the authoritative source of truth for corpus content; retrieval.py no longer
# holds a copy. ADR 0007: static corpus is for ingestion only, not runtime retrieval.
_STATIC_CORPUS = [
    {
        "chunk_id": "2cfr200-205-001",
        "source_id": "2-CFR-200.205",
        "section": "200.205",
        "last_revised": "2024-04-22",
        "text_excerpt": "Federal agencies must have a merit review process for competitive grants (2 CFR 200.205).",
        "regulation": "2 CFR 200",
    },
    {
        "chunk_id": "2cfr200-206-001",
        "source_id": "2-CFR-200.206",
        "section": "200.206",
        "last_revised": "2024-04-22",
        "text_excerpt": "Federal agencies must evaluate risks posed by applicants (2 CFR 200.206).",
        "regulation": "2 CFR 200",
    },
    {
        "chunk_id": "45cfr75-206-001",
        "source_id": "45-CFR-75.206",
        "section": "75.206",
        "last_revised": "2023-10-01",
        "text_excerpt": "HHS supplement — risk evaluation for HHS grant applicants (45 CFR 75.206).",
        "regulation": "45 CFR 75",
    },
    {
        "chunk_id": "2cfr200-coi-001",
        "source_id": "2-CFR-200.318",
        "section": "200.318",
        "last_revised": "2024-04-22",
        "text_excerpt": "Conflict of interest requirements for federal grant procurement (2 CFR 200.318).",
        "regulation": "2 CFR 200",
    },
    {
        "chunk_id": "2cfr200-award-001",
        "source_id": "2-CFR-200.212",
        "section": "200.212",
        "last_revised": "2024-04-22",
        "text_excerpt": "Award decisions must be documented with a written record of rationale (2 CFR 200.212).",
        "regulation": "2 CFR 200",
    },
    {
        "chunk_id": "2cfr200-factor-001",
        "source_id": "2-CFR-200.204",
        "section": "200.204",
        "last_revised": "2024-04-22",
        "text_excerpt": "NOFO must describe selection criteria and evaluation factors (2 CFR 200.204).",
        "regulation": "2 CFR 200",
    },
    {
        "chunk_id": "nofo-general-001",
        "source_id": "NOFO-GENERAL",
        "section": "NOFO",
        "last_revised": "2024-01-01",
        "text_excerpt": "Notice of Funding Opportunity — describes eligibility, evaluation, and award criteria.",
        "regulation": "NOFO",
    },
]


def build_document(entry: dict) -> dict:
    """
    Build a corpus document with provenance and embedding.
    Raises ValueError if provenance is missing (ADR 0009 §12).
    Raises RuntimeError if Bedrock embedding fails (ADR 0009 §4).
    get_embedding already raises on failure — never returns a zero vector.
    """
    text = entry["text_excerpt"]
    regulation = entry.get("regulation", "")
    source_uri = _REGULATION_SOURCE_URIS.get(regulation, "unknown")
    doc = {
        "chunk_id": entry["chunk_id"],
        "source_id": entry["source_id"],
        "section": entry.get("section"),
        "last_revised": entry.get("last_revised"),
        "text_excerpt": text,
        "regulation": regulation,
        "tenant_id": GLOBAL_TENANT,
        "embedding_model_version": EMBEDDING_MODEL_ID,
        "source_uri": source_uri,
        "source_checksum": hashlib.sha256(text.encode()).hexdigest(),
        "approver_id": APPROVER_ID,
        "ingestion_actor": INGESTION_ACTOR,
    }
    # Provenance gate — reject before any embedding call or upsert.
    _validate_provenance(doc)
    log.info("Embedding %s ...", entry["source_id"])
    doc["embedding"] = get_embedding(text)
    return doc


def ingest() -> None:
    db = get_atlas_db()

    log.info("Ensuring Atlas vector search index ...")
    ensure_vector_index(db)

    # ADR 0009 §12: pre-build ALL documents before any upsert.
    # A failure in provenance validation or Bedrock embedding aborts the entire run;
    # no partial corpus is written to Atlas.
    log.info("Building and embedding %d corpus chunks (pre-flight) ...", len(_STATIC_CORPUS))
    docs = []
    for entry in _STATIC_CORPUS:
        try:
            docs.append(build_document(entry))
        except (ValueError, RuntimeError) as exc:
            log.error("INGESTION ABORTED — provenance/embedding failure for %s: %s",
                      entry.get("source_id", "unknown"), exc)
            sys.exit(1)

    log.info("All %d documents validated and embedded. Upserting to %s ...", len(docs), COLLECTION)
    inserted = updated = 0
    for doc in docs:
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
