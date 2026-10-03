"""Probe 3: is the long-term Store rolled back by time travel?"""
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore

class S(TypedDict, total=False):
    n: int

def bump(state: S, *, store: BaseStore):
    item = store.get(("mem",), "counter")
    v = (item.value["v"] if item else 0) + 1
    store.put(("mem",), "counter", {"v": v})
    return {"n": v}

st = InMemoryStore()
g = StateGraph(S).add_node("bump", bump).add_edge(START, "bump").add_edge("bump", END).compile(checkpointer=InMemorySaver(), store=st)
cfg = {"configurable": {"thread_id": "s"}}
g.invoke({"n": 0}, cfg)
g.invoke({"n": 0}, cfg)
h = list(g.get_state_history(cfg))
first_before = [s for s in h if s.next == ("bump",)][-1]
print("store before time travel:", st.get(("mem",), "counter").value)
out = g.invoke(None, first_before.config)
print("replay from first run's pre-bump checkpoint -> state n:", out["n"], "| store now:", st.get(("mem",), "counter").value)
