"""
Shared fixtures for HITL test suite.
Patches MongoDB so no real DB is needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_db():
    """
    Patch get_db everywhere it is imported so all service calls go to a MagicMock.
    autouse=True means every test in this suite gets this patch automatically.
    """
    db = MagicMock()

    def _chainable_cursor(rows=()):
        """Return a cursor mock that supports .sort(...).limit(...) chaining."""
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = iter(rows)
        cursor.__iter__ = lambda self: iter(rows)
        return cursor

    # Default: find_one returns None (no existing records)
    db.hitl_audit_trail.find_one.return_value = None
    db.hitl_audit_trail.find.return_value = _chainable_cursor()
    db.hitl_escalations.find.return_value = _chainable_cursor()
    db.retrieval_cache.find_one.return_value = None
    db.retrieval_cache.delete_many.return_value = MagicMock(deleted_count=0)
    db.retrieval_cache.delete_one.return_value = MagicMock()
    db.clause_library.find.return_value = _chainable_cursor()
    # Attach helper to db so tests can use it
    db._chainable_cursor = _chainable_cursor

    with (
        patch("app.services.audit_trail.get_db", return_value=db),
        patch("app.services.retrieval.get_db", return_value=db),
    ):
        yield db


@pytest.fixture
def client(mock_db):
    from app.main import app
    return TestClient(app)


@pytest.fixture
def gate1_approve_payload():
    return {
        "gate_id": "GATE_1",
        "actor_id": "officer-001",
        "actor_role": "GRANTS_OFFICER",
        "tenant_id": "tenant-abc",
        "ai_run_id": "run-001",
        "decision": "APPROVE",
        "rationale": "Application meets 2 CFR 200.205 merit criteria.",
        "confidence_score": 0.85,
        "grounding_status": "GROUNDED",
    }


@pytest.fixture
def gate2_resolve_payload():
    return {
        "gate_id": "GATE_2",
        "actor_id": "lead-001",
        "actor_role": "REVIEW_LEAD",
        "tenant_id": "tenant-abc",
        "ai_run_id": "run-002",
        "decision": "RESOLVE_AND_CONTINUE",
        "rationale": "Reviewer disclosures reviewed; no disqualifying COI found.",
        "confidence_score": 0.90,
        "grounding_status": "GROUNDED",
    }


@pytest.fixture
def gate3_accept_payload():
    return {
        "gate_id": "GATE_3",
        "actor_id": "reviewer-001",
        "actor_role": "HUMAN_REVIEWER",
        "tenant_id": "tenant-abc",
        "ai_run_id": "run-003",
        "decision": "ACCEPT",
        "rationale": "AI factor suggestion accepted as written.",
        "confidence_score": 0.80,
        "grounding_status": "GROUNDED",
    }


@pytest.fixture
def gate4_award_payload():
    return {
        "gate_id": "GATE_4",
        "actor_id": "officer-001",
        "actor_role": "GRANTS_OFFICER",
        "tenant_id": "tenant-abc",
        "ai_run_id": "run-004",
        "decision": "AWARD",
        "rationale": "Panel recommendation accepted; award authorized per 2 CFR 200.212.",
        "confidence_score": 0.92,
        "grounding_status": "GROUNDED",
    }
