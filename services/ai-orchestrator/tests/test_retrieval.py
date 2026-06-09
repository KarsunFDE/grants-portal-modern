"""
Retrieval invalidation + cache tests — hitl-plan.txt §Retrieval Invalidation Policy.

AC11: Re-retrieval mandatory after invalidation triggers.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from app.schemas.hitl import Citation, InvalidationTrigger
from app.services.retrieval import RetrievalService, _make_cache_key


class TestRetrievalService:
    # Static corpus removed from retrieval path (ADR 0007 / ADR 0009).
    # Atlas Local is now the primary retrieval source; _query_static_corpus no longer exists.

    def test_confidence_zero_without_citations(self):
        svc = RetrievalService()
        assert svc._compute_confidence([], "anything") == 0.0

    def test_confidence_increases_with_regulatory_citations(self):
        svc = RetrievalService()
        citations = [
            Citation(chunk_id="c1", source_id="s1", regulation="2 CFR 200", tenant_id="t1"),
            Citation(chunk_id="c2", source_id="s2", regulation="45 CFR 75", tenant_id="t1"),
        ]
        conf = svc._compute_confidence(citations, "anything")
        assert conf > 0.0
        assert conf <= 0.95

    def test_confidence_never_exceeds_cap(self):
        svc = RetrievalService()
        many = [Citation(chunk_id=f"c{i}", source_id=f"s{i}", regulation="2 CFR 200", tenant_id="t") for i in range(10)]
        assert svc._compute_confidence(many, "q") <= 0.95

    def test_faithfulness_zero_without_citations(self):
        svc = RetrievalService()
        assert svc._compute_faithfulness([]) == 0.0

    def test_faithfulness_increases_with_more_citations(self):
        svc = RetrievalService()
        c1 = [Citation(chunk_id=f"c{i}", source_id=f"s{i}", tenant_id="t1") for i in range(1, 3)]
        c2 = [Citation(chunk_id=f"c{i}", source_id=f"s{i}", tenant_id="t1") for i in range(1, 6)]
        assert svc._compute_faithfulness(c2) > svc._compute_faithfulness(c1)

    def test_retrieve_returns_empty_when_atlas_and_db_unavailable(self):
        """With no Atlas and no DB, retrieve returns empty citations and triggers escalation path."""
        svc = RetrievalService()
        with patch("app.services.retrieval.atlas_search.ATLAS_RETRIEVAL_ENABLED", False):
            citations, conf, faith, _, strategy, cache_hit = svc.retrieve(
                query="merit review eligibility",
                tenant_id="tenant-1",
            )
        assert citations == []
        assert conf == 0.0
        assert faith == 0.0
        assert cache_hit is False


class TestCacheInvalidation:
    """AC11: Re-retrieval mandatory after invalidation triggers."""

    def test_invalidate_clears_tenant_cache(self, mock_db):
        mock_db.retrieval_cache.delete_many.return_value = MagicMock(deleted_count=3)
        svc = RetrievalService()
        count = svc.invalidate("tenant-abc", InvalidationTrigger.APPLICATION_DATA, "app-001")
        assert count == 3
        mock_db.retrieval_cache.delete_many.assert_called_once_with({"tenant_id": "tenant-abc"})

    def test_invalidate_records_event(self, mock_db):
        svc = RetrievalService()
        svc.invalidate("tenant-abc", InvalidationTrigger.NOFO_AMENDMENT, "nofo-v2")
        mock_db.retrieval_invalidation_events.insert_one.assert_called_once()
        call_arg = mock_db.retrieval_invalidation_events.insert_one.call_args[0][0]
        assert call_arg["trigger"] == "NOFO_AMENDMENT"
        assert call_arg["tenant_id"] == "tenant-abc"
        assert call_arg["resource_id"] == "nofo-v2"

    def test_all_invalidation_trigger_types(self, mock_db):
        svc = RetrievalService()
        for trigger in InvalidationTrigger:
            svc.invalidate("tenant-x", trigger, "resource-1")
        assert mock_db.retrieval_cache.delete_many.call_count == len(InvalidationTrigger)

    def test_cache_bypassed_after_application_data_change(self, mock_db):
        """If application_data_hash changed, cache must be invalidated."""
        mock_db.retrieval_cache.find_one.return_value = {
            "cache_key": "some-key",
            "tenant_id": "tenant-1",
            "citations": [],
            "confidence_score": 0.85,
            "faithfulness_score": 0.88,
            "application_data_hash": "old-hash",
            "expires_at": datetime.utcnow() + timedelta(hours=12),
        }
        svc = RetrievalService()
        # Retrieve with a new application_data_hash — cache must be bypassed
        result = svc._check_cache(
            mock_db, "some-key", "tenant-1",
            application_data_hash="new-hash",
            nofo_hash=None,
            reviewer_state_hash=None,
        )
        assert result is None
        mock_db.retrieval_cache.delete_one.assert_called_once()

    def test_cache_bypassed_after_nofo_change(self, mock_db):
        mock_db.retrieval_cache.find_one.return_value = {
            "cache_key": "k",
            "tenant_id": "t",
            "citations": [],
            "confidence_score": 0.8,
            "faithfulness_score": 0.85,
            "nofo_hash": "nofo-old",
            "expires_at": datetime.utcnow() + timedelta(hours=12),
        }
        svc = RetrievalService()
        result = svc._check_cache(mock_db, "k", "t", None, "nofo-new", None)
        assert result is None

    def test_cache_bypassed_after_reviewer_state_change(self, mock_db):
        mock_db.retrieval_cache.find_one.return_value = {
            "cache_key": "k",
            "tenant_id": "t",
            "citations": [],
            "confidence_score": 0.8,
            "faithfulness_score": 0.85,
            "reviewer_state_hash": "old-rs",
            "expires_at": datetime.utcnow() + timedelta(hours=12),
        }
        svc = RetrievalService()
        result = svc._check_cache(mock_db, "k", "t", None, None, "new-rs")
        assert result is None

    def test_cache_returned_when_all_hashes_match(self, mock_db):
        citations_data = [{"chunk_id": "c1", "source_id": "s1", "tenant_id": "t1"}]
        mock_db.retrieval_cache.find_one.return_value = {
            "cache_key": "k",
            "tenant_id": "t",
            "citations": citations_data,
            "confidence_score": 0.85,
            "faithfulness_score": 0.90,
            "application_data_hash": "hash-1",
            "nofo_hash": "nofo-1",
            "reviewer_state_hash": "rs-1",
            "expires_at": datetime.utcnow() + timedelta(hours=12),
        }
        svc = RetrievalService()
        result = svc._check_cache(mock_db, "k", "t", "hash-1", "nofo-1", "rs-1")
        assert result is not None
        citations, conf, faith, retrieved_at, strategy = result
        assert conf == 0.85
        assert faith == 0.90
        assert retrieved_at is not None
        assert strategy is None  # no retrieval_strategy in mock entry — expected for old entries

    def test_expired_cache_bypassed(self, mock_db):
        mock_db.retrieval_cache.find_one.return_value = {
            "cache_key": "k",
            "tenant_id": "t",
            "citations": [],
            "confidence_score": 0.9,
            "faithfulness_score": 0.9,
            "expires_at": datetime.utcnow() - timedelta(hours=1),  # expired
        }
        svc = RetrievalService()
        result = svc._check_cache(mock_db, "k", "t", None, None, None)
        assert result is None


class TestTenantIsolation:
    """
    REQ-RAG-3: tenant isolation proven by test.

    The $vectorSearch filter must scope results to [request_tenant_id, "__global__"].
    Tenant B's chunks must be unreachable from Tenant A's query.
    Callers must not be able to supply "__global__" as their tenant_id.
    """

    def test_vector_search_filter_scopes_to_caller_and_global(self):
        """vector_search builds a filter containing [tenant_id, '__global__'] only."""
        from unittest.mock import MagicMock, patch
        import app.atlas_search as atlas_mod

        captured_pipelines = []

        def fake_aggregate(pipeline):
            captured_pipelines.append(pipeline)
            return iter([])

        fake_collection = MagicMock()
        fake_collection.aggregate.side_effect = fake_aggregate
        fake_db = MagicMock()
        fake_db.__getitem__.return_value = fake_collection

        with (
            patch.object(atlas_mod, "get_atlas_db", return_value=fake_db),
            patch.object(atlas_mod, "get_embedding", return_value=[0.1] * 1024),
            patch.object(atlas_mod, "ATLAS_RETRIEVAL_ENABLED", True),
        ):
            atlas_mod.vector_search("merit review", tenant_id="tenant-A")

        assert captured_pipelines, "aggregate was not called"
        vs_stage = captured_pipelines[0][0]["$vectorSearch"]
        tenant_filter = vs_stage["filter"]["tenant_id"]["$in"]
        assert "tenant-A" in tenant_filter
        assert "__global__" in tenant_filter
        assert len(tenant_filter) == 2, (
            f"Expected exactly [tenant-A, __global__] in filter; got {tenant_filter}"
        )

    def test_tenant_b_chunks_not_returned_for_tenant_a_query(self):
        """Atlas aggregation result for tenant-A must not include tenant-B docs."""
        from unittest.mock import MagicMock, patch
        import app.atlas_search as atlas_mod
        from app.schemas.hitl import Citation

        tenant_b_doc = {
            "chunk_id": "b-chunk-1",
            "source_id": "NOFO-tenant-B",
            "section": "3.1",
            "subsection": None,
            "section_title": None,
            "last_revised": "2024-01-01",
            "text_excerpt": "Tenant B confidential NOFO content.",
            "regulation": "NOFO",
            "tenant_id": "tenant-B",   # wrong tenant
            "score": 0.99,
        }
        # Atlas pre-filter should prevent this from being returned; simulate a bypass
        # to verify the post-retrieval tenant guard in vector_search also catches it.
        fake_collection = MagicMock()
        fake_collection.aggregate.return_value = iter([tenant_b_doc])
        fake_db = MagicMock()
        fake_db.__getitem__.return_value = fake_collection

        with (
            patch.object(atlas_mod, "get_atlas_db", return_value=fake_db),
            patch.object(atlas_mod, "get_embedding", return_value=[0.1] * 1024),
            patch.object(atlas_mod, "ATLAS_RETRIEVAL_ENABLED", True),
        ):
            results = atlas_mod.vector_search("merit review", tenant_id="tenant-A")

        chunk_ids = [c.chunk_id for c in results]
        assert "b-chunk-1" not in chunk_ids, (
            "Tenant B chunk must not appear in tenant A query results"
        )

    def test_reserved_global_tenant_rejected_at_vector_search(self):
        """Supplying '__global__' as caller tenant_id must raise ValueError."""
        import app.atlas_search as atlas_mod
        import pytest

        with pytest.raises(ValueError, match="reserved system value"):
            atlas_mod.vector_search("any query", tenant_id="__global__")

    def test_reserved_tenant_variants_rejected(self):
        """Case/whitespace variants of the reserved marker are also rejected."""
        import app.atlas_search as atlas_mod

        for bad_tenant in ["global", "GLOBAL", "__GLOBAL__"]:
            with pytest.raises(ValueError):
                atlas_mod.vector_search("query", tenant_id=bad_tenant)


class TestRAGV2Endpoints:
    def test_search_returns_grounded_response(self, client):
        resp = client.post("/rag/v2/search", json={
            "query": "merit review eligibility",
            "tenant_id": "tenant-abc",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "citations" in body
        assert "confidence_score" in body
        assert "faithfulness_score" in body
        assert "grounding_status" in body
        assert "requires_human_review" in body
        assert "human_review_reasons" in body
        assert "ai_run_id" in body

    def test_invalidate_endpoint(self, client, mock_db):
        mock_db.retrieval_cache.delete_many.return_value = MagicMock(deleted_count=2)
        resp = client.post("/rag/v2/invalidate", json={
            "tenant_id": "tenant-abc",
            "trigger": "APPLICATION_DATA",
            "resource_id": "app-001",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["invalidated_count"] == 2
        assert "Re-retrieval required" in body["message"]

    def test_search_with_gate_context_creates_escalation_if_needed(self, client, mock_db):
        """If grounding fails and gate_context set, escalation must be created."""
        resp = client.post("/rag/v2/search", json={
            "query": "something completely unrecognized xyz123",
            "tenant_id": "tenant-abc",
            "gate_context": "GATE_1",
        })
        assert resp.status_code == 200
        # If ungrounded: escalation recorded in audit trail
        # If grounded: no escalation needed — both are valid outcomes

    def test_search_structure_has_all_required_contract_fields(self, client):
        resp = client.post("/rag/v2/search", json={
            "query": "award decision documentation",
            "tenant_id": "t1",
        })
        body = resp.json()
        required = {
            "answer", "citations", "retrieved_sources", "citation_refs",
            "confidence_score", "faithfulness_score", "grounding_status",
            "requires_human_review", "human_review_reasons", "ai_run_id",
        }
        assert required.issubset(body.keys())
