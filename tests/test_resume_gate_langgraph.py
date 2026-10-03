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


# v0.2 automatic manifest capture -------------------------------------------------

from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

from resume_gate import InMemoryManifestStore, JsonDirectoryManifestStore


def _build_auto_tool_graph(checkpointer, tool_variant: str):
    class AutoState(TypedDict, total=False):
        amount: int
        approved: bool

    def review(state: AutoState):
        approved = interrupt({"kind": "approval", "amount": state["amount"]})
        return {"approved": bool(approved)}

    @tool("refund_customer")
    def refund_v1(amount: int) -> str:
        """Refund an order amount."""
        return f"refunded:{amount}"

    @tool("refund_customer")
    def refund_v2(amount: int, reason: str = "customer_request") -> str:
        """Refund an order amount with an explicit reason."""
        return f"refunded:{amount}:{reason}"

    if tool_variant == "v1":
        tools = [refund_v1]
    elif tool_variant == "v2":
        tools = [refund_v2]
    elif tool_variant == "removed":
        tools = []
    else:
        raise ValueError(tool_variant)

    builder = StateGraph(AutoState)
    builder.add_node("review", review)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "review")
    builder.add_edge("review", "tools")
    builder.add_edge("tools", END)
    return builder.compile(checkpointer=checkpointer)


def _build_auto_simple_graph(checkpointer, state_version: int = 1):
    if state_version == 1:
        class AutoState(TypedDict, total=False):
            amount: int
            approved: bool
    else:
        class AutoState(TypedDict, total=False):
            amount: int
            approved: bool
            currency: str

    def review(state):
        approved = interrupt({"kind": "approval", "amount": state["amount"]})
        return {"approved": bool(approved)}

    builder = StateGraph(AutoState)
    builder.add_node("review", review)
    builder.add_edge(START, "review")
    builder.add_edge("review", END)
    return builder.compile(checkpointer=checkpointer)


def test_auto_mode_detects_tool_removed_across_deployment_without_annotations():
    saver = InMemorySaver()
    manifests = InMemoryManifestStore()
    config = {"configurable": {"thread_id": "auto-tool-removed"}}

    graph_v1 = _build_auto_tool_graph(saver, "v1")
    guarded_v1 = GuardedLangGraph.auto(graph_v1, store=manifests)
    guarded_v1.invoke({"amount": 100}, config)

    saved = manifests.get("auto-tool-removed::")
    assert saved is not None
    assert "refund_customer" in saved["tools"]

    # New deployment: same graph topology and persisted thread, but the
    # registered ToolNode no longer exposes refund_customer.
    graph_v2 = _build_auto_tool_graph(saver, "removed")
    guarded_v2 = GuardedLangGraph.auto(graph_v2, store=manifests)

    with pytest.raises(ResumeGateRefused) as exc:
        guarded_v2.invoke(Command(resume=True), config)

    assert exc.value.decision.result.verdict is Verdict.BLOCK
    assert "TOOL_REMOVED" in {
        issue.code for issue in exc.value.decision.result.issues
    }


def test_auto_mode_detects_tool_schema_change_without_annotations():
    saver = InMemorySaver()
    manifests = InMemoryManifestStore()
    config = {"configurable": {"thread_id": "auto-tool-schema"}}

    guarded_v1 = GuardedLangGraph.auto(
        _build_auto_tool_graph(saver, "v1"),
        store=manifests,
    )
    guarded_v1.invoke({"amount": 100}, config)

    guarded_v2 = GuardedLangGraph.auto(
        _build_auto_tool_graph(saver, "v2"),
        store=manifests,
    )
    with pytest.raises(ResumeGateRefused) as exc:
        guarded_v2.invoke(Command(resume=True), config)

    assert exc.value.decision.result.verdict is Verdict.REVALIDATE
    assert "TOOL_VERSION_CHANGED" in {
        issue.code for issue in exc.value.decision.result.issues
    }


def test_auto_mode_detects_state_schema_change_without_annotations():
    saver = InMemorySaver()
    manifests = InMemoryManifestStore()
    config = {"configurable": {"thread_id": "auto-schema"}}

    guarded_v1 = GuardedLangGraph.auto(
        _build_auto_simple_graph(saver, state_version=1),
        store=manifests,
    )
    guarded_v1.invoke({"amount": 50}, config)

    guarded_v2 = GuardedLangGraph.auto(
        _build_auto_simple_graph(saver, state_version=2),
        store=manifests,
    )
    with pytest.raises(ResumeGateRefused) as exc:
        guarded_v2.invoke(Command(resume=True), config)

    assert exc.value.decision.result.verdict is Verdict.MIGRATE
    assert "STATE_SCHEMA_CHANGED" in {
        issue.code for issue in exc.value.decision.result.issues
    }


def test_auto_mode_uses_one_context_provider_for_pause_and_resume():
    saver = InMemorySaver()
    manifests = InMemoryManifestStore()
    config = {"configurable": {"thread_id": "auto-authority"}}
    environment = {
        "policy_version": "policy-v1",
        "authorities": [
            {
                "id": "approval-1",
                "scope": "refund:100",
                "status": "active",
                "policy_version": "policy-v1",
            }
        ],
    }

    def live_context(snapshot, config):
        return deepcopy(environment)

    guarded = GuardedLangGraph.auto(
        _build_auto_simple_graph(saver),
        store=manifests,
        context_provider=live_context,
    )
    guarded.invoke({"amount": 100}, config)

    environment["authorities"][0]["status"] = "revoked"

    with pytest.raises(ResumeGateRefused) as exc:
        guarded.invoke(Command(resume=True), config)

    assert exc.value.decision.result.verdict is Verdict.BLOCK
    assert "AUTHORITY_NOT_ACTIVE" in {
        issue.code for issue in exc.value.decision.result.issues
    }


def test_json_directory_store_survives_gate_reinstantiation(tmp_path):
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "persistent-manifest"}}

    graph = _build_auto_simple_graph(saver)
    first_store = JsonDirectoryManifestStore(tmp_path / "manifests")
    first_gate = GuardedLangGraph.auto(graph, store=first_store)
    first_gate.invoke({"amount": 25}, config)

    # Simulate a new application process using the same durable manifest
    # directory and the same durable LangGraph checkpoint backend.
    second_store = JsonDirectoryManifestStore(tmp_path / "manifests")
    second_gate = GuardedLangGraph.auto(graph, store=second_store)
    result = second_gate.invoke(Command(resume=True), config)

    assert result["approved"] is True
    assert second_store.get("persistent-manifest::") is None
