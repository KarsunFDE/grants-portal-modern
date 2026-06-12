"""
Compiled LangGraph workflow graph.

Lazy singleton — graph is compiled on first call to get_graph().
Checkpointer: MongoDBSaver (workflow_checkpoints collection) with
MemorySaver fallback for CI / no-MongoDB environments.

Resume pattern:
  graph.invoke(Command(resume=gate_decision), config={"configurable": {"thread_id": workflow_run_id}})
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("ai-orchestrator.workflow.graph")

_graph = None


def get_graph():
    """Return compiled LangGraph graph (singleton)."""
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


def _build_checkpointer():
    import os
    require_mongo = os.getenv("REQUIRE_MONGO_CHECKPOINT", "").lower() in ("1", "true", "yes")
    try:
        from langgraph.checkpoint.mongodb import MongoDBSaver
        from app.db import get_mongo_client
        client = get_mongo_client()
        checkpointer = MongoDBSaver(client)
        log.info("Using MongoDBSaver checkpointer (durable)")
        return checkpointer
    except Exception as exc:
        if require_mongo:
            raise RuntimeError(
                f"REQUIRE_MONGO_CHECKPOINT=true but MongoDBSaver unavailable: {exc}"
            ) from exc
        log.warning(
            "MongoDBSaver unavailable (%s); falling back to MemorySaver "
            "(non-durable — set REQUIRE_MONGO_CHECKPOINT=true to hard-fail instead)",
            exc,
        )
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


def _build_graph():
    from langgraph.graph import StateGraph, END

    from app.workflow.state import WorkflowState
    from app.workflow.nodes import (
        triage_node,
        eligibility_node,
        reviewer_assignment_node,
        coi_check_node,
        gate_2_node,
        panel_confirmation_node,
        factor_suggest_node,
        ssdd_draft_node,
        seal_audit_node,
        route_gate_1,
        route_gate_2,
        route_gate_3,
        route_gate_4,
    )

    builder = StateGraph(WorkflowState)

    # Add nodes
    builder.add_node("triage", triage_node)
    builder.add_node("eligibility", eligibility_node)
    builder.add_node("reviewer_assignment", reviewer_assignment_node)
    builder.add_node("coi_check", coi_check_node)
    builder.add_node("gate_2", gate_2_node)
    builder.add_node("panel_confirmation", panel_confirmation_node)
    builder.add_node("factor_suggest", factor_suggest_node)
    builder.add_node("ssdd_draft", ssdd_draft_node)
    builder.add_node("seal_audit", seal_audit_node)

    # Entry point
    builder.set_entry_point("triage")

    # Linear edges (no branching)
    builder.add_edge("triage", "eligibility")
    builder.add_edge("reviewer_assignment", "coi_check")
    builder.add_edge("coi_check", "gate_2")
    builder.add_edge("panel_confirmation", "factor_suggest")
    builder.add_edge("seal_audit", END)

    # Gate-routed conditional edges
    builder.add_conditional_edges(
        "eligibility",
        route_gate_1,
        {
            "reviewer_assignment": "reviewer_assignment",
            "eligibility": "eligibility",   # RETURN_FOR_FIXES loops back
            "__end__": END,
        },
    )
    builder.add_conditional_edges(
        "gate_2",
        route_gate_2,
        {
            "panel_confirmation": "panel_confirmation",
            "reviewer_assignment": "reviewer_assignment",
            "__end__": END,
        },
    )
    builder.add_conditional_edges(
        "factor_suggest",
        route_gate_3,
        {
            "ssdd_draft": "ssdd_draft",
            "factor_suggest": "factor_suggest",
            "__end__": END,
        },
    )
    builder.add_conditional_edges(
        "ssdd_draft",
        route_gate_4,
        {
            "seal_audit": "seal_audit",
            "factor_suggest": "factor_suggest",
            "__end__": END,
        },
    )

    checkpointer = _build_checkpointer()
    graph = builder.compile(checkpointer=checkpointer)
    log.info("LangGraph workflow compiled successfully")
    return graph


def get_workflow_state(workflow_run_id: str) -> Optional[dict]:
    """Return current workflow state snapshot from checkpoint."""
    graph = get_graph()
    config = {"configurable": {"thread_id": workflow_run_id}}
    try:
        snapshot = graph.get_state(config)
        if snapshot and snapshot.values:
            return {
                "state": dict(snapshot.values),
                "next_nodes": list(snapshot.next),
                "is_paused": len(snapshot.next) > 0,
                "pending_interrupts": [
                    t.interrupts[0].value
                    for t in (snapshot.tasks or [])
                    if t.interrupts
                ],
            }
    except Exception as exc:
        log.warning("get_workflow_state error workflow=%s: %s", workflow_run_id, exc)
    return None
