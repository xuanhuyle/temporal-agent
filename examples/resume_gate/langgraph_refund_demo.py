from __future__ import annotations

from copy import deepcopy
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from resume_gate import GuardedLangGraph, ResumeGateRefused


class State(TypedDict, total=False):
    amount: int
    approved: bool


environment = {
    "now": "2026-10-03T12:00:00Z",
    "policy_version": "refund-policy-v1",
    "runtime": {
        "agent_version": "refund-agent-v1",
        "state_schema": "refund-state-v1",
        "model": "example-model",
    },
    "tools": {
        "refund_customer": {
            "version": "tool-v1",
            "permission": "refund:write",
        }
    },
}

executions: list[int] = []


def review(state: State):
    approved = interrupt(
        {"kind": "approval", "action": "refund_customer", "amount": state["amount"]}
    )
    return {"approved": bool(approved)}


def refund(state: State):
    if state.get("approved"):
        executions.append(state["amount"])
        print(f"REFUND EXECUTED: {state['amount']}")
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
        (snapshot.config or {}).get("configurable", {}).get("checkpoint_id")
    )
    return manifest


def current_manifest(snapshot, config):
    return deepcopy(environment)


guarded = GuardedLangGraph(
    graph,
    checkpoint_manifest=checkpoint_manifest,
    current_manifest=current_manifest,
)

config = {"configurable": {"thread_id": "demo-refund"}}

print("1. Start workflow. It pauses for approval.")
guarded.invoke({"amount": 100}, config)

print("2. While the workflow sleeps, refund authority is revoked.")
environment["tools"] = {}

print("3. Try to resume.")
try:
    guarded.invoke(Command(resume=True), config)
except ResumeGateRefused as exc:
    print(f"RESUME REFUSED: {exc.decision.result.verdict.value}")
    for issue in exc.decision.result.issues:
        print(f"  - {issue.code}: {issue.message}")

assert executions == []
print("No refund was executed.")
