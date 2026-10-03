from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import TypedDict

import pytest

langgraph = pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from resume_gate import GuardedLangGraph, ResumeGateRefused, Verdict


class State(TypedDict, total=False):
    amount: int
    approved: bool


def _build_guarded_graph():
    executions: list[int] = []
    environment = {
        "now": "2026-10-03T12:00:00Z",
        "policy_version": "refund-policy-v1",
        "runtime": {
            "agent_version": "agent-v1",
            "state_schema": "refund-state-v1",
            "model": "test-model",
        },
        "tools": {
            "refund_customer": {
                "version": "tool-v1",
                "permission": "refund:write",
            }
        },
    }

    def review(state: State):
        approved = interrupt(
            {
                "kind": "approval",
                "action": "refund_customer",
                "amount": state["amount"],
            }
        )
        return {"approved": bool(approved)}

    def refund(state: State):
        if state.get("approved"):
            executions.append(state["amount"])
        return {}

    builder = StateGraph(State)
    builder.add_node("review", review)
    builder.add_node("refund", refund)
    builder.add_edge(START, "review")
    builder.add_edge("review", "refund")
    builder.add_edge("refund", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    def checkpoint_manifest(snapshot, config):
        manifest = deepcopy(environment)
        manifest["checkpoint_id"] = (
            (getattr(snapshot, "config", None) or {})
            .get("configurable", {})
            .get("checkpoint_id")
        )
        return manifest

    def current_manifest(snapshot, config):
        return deepcopy(environment)

    guarded = GuardedLangGraph(
        graph,
        checkpoint_manifest=checkpoint_manifest,
        current_manifest=current_manifest,
    )
    return guarded, environment, executions


def test_langgraph_resume_is_blocked_before_next_node_when_tool_revoked():
    guarded, environment, executions = _build_guarded_graph()
    config = {"configurable": {"thread_id": "refund-1"}}

    guarded.invoke({"amount": 100}, config)
    snapshot = guarded.get_state(config)
    assert any(task.interrupts for task in snapshot.tasks)

    # World/policy state drifts while the graph sleeps.
    environment["tools"] = {}

    with pytest.raises(ResumeGateRefused) as exc:
        guarded.invoke(Command(resume=True), config)

    assert exc.value.decision.result.verdict is Verdict.BLOCK
    assert "TOOL_REMOVED" in {
        issue.code for issue in exc.value.decision.result.issues
    }
    assert executions == []

    # Restoring current authority makes the same persisted LangGraph checkpoint
    # safe to resume. The action executes only after validation succeeds.
    environment["tools"] = {
        "refund_customer": {
            "version": "tool-v1",
            "permission": "refund:write",
        }
    }
    result = guarded.invoke(Command(resume=True), config)

    assert result["approved"] is True
    assert executions == [100]


def test_langgraph_resume_requires_migration_after_state_schema_drift():
    guarded, environment, executions = _build_guarded_graph()
    config = {"configurable": {"thread_id": "refund-2"}}

    guarded.invoke({"amount": 50}, config)
    environment["runtime"]["state_schema"] = "refund-state-v2"

    with pytest.raises(ResumeGateRefused) as exc:
        guarded.invoke(Command(resume=True), config)

    assert exc.value.decision.result.verdict is Verdict.MIGRATE
    assert "STATE_SCHEMA_CHANGED" in {
        issue.code for issue in exc.value.decision.result.issues
    }
    assert executions == []


def test_langgraph_resume_fails_closed_if_gate_manifest_is_missing():
    guarded, _environment, executions = _build_guarded_graph()
    config = {"configurable": {"thread_id": "refund-3"}}

    # Create the LangGraph checkpoint without going through the gate to model a
    # legacy thread created before Resume Gate was installed.
    guarded.graph.invoke({"amount": 20}, config)

    with pytest.raises(ResumeGateRefused) as exc:
        guarded.invoke(Command(resume=True), config)

    assert exc.value.decision.result.verdict is Verdict.BLOCK
    assert "MANIFEST_MISSING" in {
        issue.code for issue in exc.value.decision.result.issues
    }
    assert executions == []


def test_langgraph_async_resume_is_gated_before_execution():
    guarded, environment, executions = _build_guarded_graph()
    config = {"configurable": {"thread_id": "refund-async"}}

    async def run():
        await guarded.ainvoke({"amount": 75}, config)
        environment["tools"] = {}
        with pytest.raises(ResumeGateRefused) as exc:
            await guarded.ainvoke(Command(resume=True), config)
        return exc.value

    refused = asyncio.run(run())
    assert refused.decision.result.verdict is Verdict.BLOCK
    assert executions == []
