from __future__ import annotations

from typing import TypedDict

from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from resume_gate import GuardedLangGraph, InMemoryManifestStore, ResumeGateRefused


class State(TypedDict, total=False):
    amount: int
    approved: bool


@tool("refund_customer")
def refund_customer(amount: int) -> str:
    """Refund a customer order."""
    return f"refunded:{amount}"


def build_graph(checkpointer, *, refund_enabled: bool):
    def review(state: State):
        approved = interrupt(
            {
                "kind": "approval",
                "action": "refund_customer",
                "amount": state["amount"],
            }
        )
        return {"approved": bool(approved)}

    tools = [refund_customer] if refund_enabled else []

    builder = StateGraph(State)
    builder.add_node("review", review)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "review")
    builder.add_edge("review", "tools")
    builder.add_edge("tools", END)
    return builder.compile(checkpointer=checkpointer)


checkpointer = InMemorySaver()
manifest_store = InMemoryManifestStore()
config = {"configurable": {"thread_id": "demo-refund"}}

print("1. Deployment A exposes refund_customer and pauses for approval.")
graph_a = build_graph(checkpointer, refund_enabled=True)
guarded_a = GuardedLangGraph.auto(graph_a, store=manifest_store)
guarded_a.invoke({"amount": 100}, config)

saved = manifest_store.get("demo-refund::")
print("   Automatically captured tools:", sorted(saved["tools"]))

print("2. Deployment B removes refund_customer while the thread sleeps.")
graph_b = build_graph(checkpointer, refund_enabled=False)
guarded_b = GuardedLangGraph.auto(graph_b, store=manifest_store)

print("3. Try to resume the same persisted LangGraph thread.")
try:
    guarded_b.invoke(Command(resume=True), config)
except ResumeGateRefused as exc:
    print(f"RESUME REFUSED: {exc.decision.result.verdict.value}")
    for issue in exc.decision.result.issues:
        print(f"  - {issue.code}: {issue.message}")

print("The application supplied no checkpoint/current manifest callbacks.")
