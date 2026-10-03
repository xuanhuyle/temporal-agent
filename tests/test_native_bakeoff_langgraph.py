from __future__ import annotations

from typing import TypedDict

import pytest

langgraph = pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class NativeResumeBlocked(RuntimeError):
    pass


class State(TypedDict, total=False):
    amount: int
    approved: bool
    resume_contract: str


def test_native_langgraph_can_recheck_live_authority_after_interrupt():
    environment = {"authority_active": True}
    executions: list[int] = []

    def review(state: State):
        approved = interrupt({"kind": "approval", "amount": state["amount"]})
        if not environment["authority_active"]:
            raise NativeResumeBlocked("authority revoked")
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
    config = {"configurable": {"thread_id": "native-authority"}}

    graph.invoke({"amount": 100}, config)
    environment["authority_active"] = False

    with pytest.raises(NativeResumeBlocked, match="authority revoked"):
        graph.invoke(Command(resume=True), config)

    assert executions == []


def test_native_langgraph_can_store_and_recheck_deployment_contract_in_state():
    environment = {"resume_contract": "deployment-v1"}
    executions: list[int] = []

    def review(state: State):
        approved = interrupt({"kind": "approval", "amount": state["amount"]})
        if state["resume_contract"] != environment["resume_contract"]:
            raise NativeResumeBlocked("deployment contract changed")
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
    config = {"configurable": {"thread_id": "native-deployment"}}

    graph.invoke(
        {"amount": 100, "resume_contract": environment["resume_contract"]},
        config,
    )

    # New deployment/tool/schema contract while the thread is parked.
    environment["resume_contract"] = "deployment-v2"

    with pytest.raises(NativeResumeBlocked, match="deployment contract changed"):
        graph.invoke(Command(resume=True), config)

    assert executions == []
