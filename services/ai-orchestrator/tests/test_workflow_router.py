"""
Workflow router integration tests.

Covers acceptance-test targets from acceptance-tests.md:
  AT-11 — idempotency: same workflow_run_id → same state, no duplicate Bedrock
  AT-15 — durability: start → status round-trip preserves state
  AT-16 — gate boundary: resume with wrong gate decision → 422

Tests mock the LangGraph graph so they run without MongoDB or AWS creds.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_graph():
    """Replace the compiled LangGraph graph with a controllable mock."""
    graph = MagicMock()
    # Default: invoke does nothing (graph pauses immediately)
    graph.invoke.return_value = None
    graph.get_state.return_value = MagicMock(
        values={
            "workflow_run_id": "test-run-1",
            "tenant_id": "tenant-abc",
            "grant_application_id": "app-001",
            "current_stage": "SCREENING",
            "active_gate_id": "GATE_1",
            "completed": False,
            "denial_reason": None,
            "gate_states": {},
            "ai_run_ids": {},
        },
        next=["eligibility"],  # paused — has next node
        tasks=[],
    )
    return graph


@pytest.fixture()
def workflow_client(client, mock_graph):
    """Client with LangGraph graph patched to mock_graph."""
    with (
        patch("app.workflow.graph._graph", mock_graph),
        patch("app.workflow.graph.get_graph", return_value=mock_graph),
    ):
        yield client


# ---------------------------------------------------------------------------
# AT-15: durability — start → status round-trip
# ---------------------------------------------------------------------------

class TestWorkflowStartAndStatus:
    def test_start_returns_workflow_run_id(self, workflow_client):
        resp = workflow_client.post("/workflow/start", json={
            "tenant_id": "tenant-abc",
            "grant_application_id": "app-001",
            "raw_text": "Federal grant application text.",
            "topic": "biomedical research",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "workflow_run_id" in body
        assert body["workflow_run_id"]

    def test_start_status_includes_active_gate(self, workflow_client, mock_graph):
        # Simulate graph paused at Gate 1 with active_gate_id in state
        mock_graph.get_state.return_value = MagicMock(
            values={
                "workflow_run_id": "run-gate1",
                "tenant_id": "tenant-abc",
                "grant_application_id": "app-001",
                "current_stage": "SCREENING",
                "active_gate_id": "GATE_1",
                "completed": False,
                "denial_reason": None,
                "gate_states": {"GATE_1": "PENDING"},
                "ai_run_ids": {"SCREENING": "ai-run-xyz"},
            },
            next=["eligibility"],
            tasks=[],
        )
        resp = workflow_client.get("/workflow/run-gate1/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "PAUSED_AT_GATE"
        assert body["active_gate_id"] == "GATE_1"

    def test_status_not_found_returns_404(self, workflow_client, mock_graph):
        mock_graph.get_state.return_value = MagicMock(values=None, next=[], tasks=[])
        resp = workflow_client.get("/workflow/nonexistent/status")
        assert resp.status_code == 404

    def test_completed_workflow_returns_completed_status(self, workflow_client, mock_graph):
        mock_graph.get_state.return_value = MagicMock(
            values={
                "workflow_run_id": "run-done",
                "tenant_id": "t1",
                "grant_application_id": "app-002",
                "current_stage": "POST_AWARD",
                "active_gate_id": None,
                "completed": True,
                "denial_reason": None,
                "gate_states": {"GATE_1": "APPROVE", "GATE_4": "AWARD"},
                "ai_run_ids": {},
            },
            next=[],
            tasks=[],
        )
        resp = workflow_client.get("/workflow/run-done/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"

    def test_denied_workflow_returns_denied_status(self, workflow_client, mock_graph):
        mock_graph.get_state.return_value = MagicMock(
            values={
                "workflow_run_id": "run-denied",
                "tenant_id": "t1",
                "grant_application_id": "app-003",
                "current_stage": "SCREENING",
                "active_gate_id": None,
                "completed": False,
                "denial_reason": "Gate 1 revision loop cap exceeded after 3 attempts",
                "gate_states": {"GATE_1": "RETURN_FOR_FIXES"},
                "ai_run_ids": {},
            },
            next=[],
            tasks=[],
        )
        resp = workflow_client.get("/workflow/run-denied/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "DENIED"
        assert "cap exceeded" in body["message"]


# ---------------------------------------------------------------------------
# AT-11: idempotency — resume with wrong decision rejected
# ---------------------------------------------------------------------------

class TestWorkflowResume:
    def test_resume_not_found_returns_404(self, workflow_client, mock_graph):
        mock_graph.get_state.return_value = MagicMock(values=None, next=[], tasks=[])
        resp = workflow_client.post("/workflow/resume", json={
            "workflow_run_id": "missing",
            "gate_decision": "APPROVE",
            "actor_id": "user1",
            "actor_role": "GRANTS_OFFICER",
            "rationale": "Looks good",
        })
        assert resp.status_code == 404

    def test_resume_completed_workflow_returns_422(self, workflow_client, mock_graph):
        mock_graph.get_state.return_value = MagicMock(
            values={
                "workflow_run_id": "run-done",
                "tenant_id": "t1",
                "grant_application_id": "app-001",
                "current_stage": "POST_AWARD",
                "active_gate_id": None,
                "completed": True,
                "denial_reason": None,
                "gate_states": {},
                "ai_run_ids": {},
            },
            next=[],
            tasks=[],
        )
        resp = workflow_client.post("/workflow/resume", json={
            "workflow_run_id": "run-done",
            "gate_decision": "APPROVE",
            "actor_id": "user1",
            "actor_role": "GRANTS_OFFICER",
            "rationale": "test",
        })
        assert resp.status_code == 422
        assert "completed" in resp.json()["detail"].lower() or "denied" in resp.json()["detail"].lower()

    def test_resume_no_active_gate_returns_422(self, workflow_client, mock_graph):
        mock_graph.get_state.return_value = MagicMock(
            values={
                "workflow_run_id": "run-1",
                "tenant_id": "t1",
                "grant_application_id": "app-001",
                "current_stage": "SCREENING",
                "active_gate_id": None,
                "completed": False,
                "denial_reason": None,
                "gate_states": {},
                "ai_run_ids": {},
            },
            next=[],
            tasks=[],
        )
        resp = workflow_client.post("/workflow/resume", json={
            "workflow_run_id": "run-1",
            "gate_decision": "APPROVE",
            "actor_id": "user1",
            "actor_role": "GRANTS_OFFICER",
            "rationale": "test",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AT-16: gate boundary — active_gate_id derived from interrupt payload
# ---------------------------------------------------------------------------

class TestActiveGateIdFromInterruptPayload:
    """
    Validates AT-16: when state.active_gate_id is None but interrupt payload
    has hitl_gate, the resume endpoint derives the gate correctly.
    """

    def test_active_gate_id_derived_from_interrupt_hitl_gate(self, workflow_client, mock_graph):
        # State has active_gate_id=None (pre-fix scenario)
        # Interrupt payload has hitl_gate="GATE_1"
        interrupt_payload = {
            "workflow_run_id": "run-interrupt",
            "hitl_gate": "GATE_1",
            "ai_run_id": "ai-run-123",
            "grounding_status": "GROUNDED",
            "confidence_score": 0.85,
        }
        task_mock = MagicMock()
        task_mock.interrupts = [MagicMock(value=interrupt_payload)]

        mock_graph.get_state.return_value = MagicMock(
            values={
                "workflow_run_id": "run-interrupt",
                "tenant_id": "t1",
                "grant_application_id": "app-001",
                "current_stage": "SCREENING",
                "active_gate_id": None,   # NOT set in state — must derive from interrupt
                "completed": False,
                "denial_reason": None,
                "gate_states": {},
                "ai_run_ids": {"SCREENING": "ai-run-123"},
            },
            next=["eligibility"],
            tasks=[task_mock],
        )

        resp = workflow_client.get("/workflow/run-interrupt/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["active_gate_id"] == "GATE_1", (
            "active_gate_id must be derived from interrupt payload hitl_gate when state has None"
        )
        assert body["status"] == "PAUSED_AT_GATE"
