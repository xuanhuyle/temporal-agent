"""Probe 2: node cache during replay; __copy__ fork; replay with interrupt_before; run_id metadata."""
import random
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.cache.memory import InMemoryCache
from langgraph.types import CachePolicy

CALLS = {"llm": 0}


class S(TypedDict, total=False):
    q: str
    a: str


def llm(state: S):
    CALLS["llm"] += 1
    return {"a": f"ans-{random.randint(0, 10**6)}"}


g = (
    StateGraph(S)
    .add_node("llm", llm, cache_policy=CachePolicy())
    .add_edge(START, "llm")
    .add_edge("llm", END)
    .compile(checkpointer=InMemorySaver(), cache=InMemoryCache())
)
cfg = {"configurable": {"thread_id": "c1"}}
r1 = g.invoke({"q": "x"}, cfg)
h = list(g.get_state_history(cfg))
before = next(s for s in h if s.next == ("llm",))
r2 = g.invoke(None, before.config)
print("with node cache: calls", CALLS, "same answer on replay:", r1["a"] == r2["a"])

# __copy__ fork
cp = InMemorySaver()
g2 = StateGraph(S).add_node("llm", llm).add_edge(START, "llm").add_edge("llm", END).compile(checkpointer=cp)
c2 = {"configurable": {"thread_id": "c2"}}
g2.invoke({"q": "x"}, c2)
h2 = list(g2.get_state_history(c2))
mid = next(s for s in h2 if s.next == ("llm",))
copy_cfg = g2.update_state(mid.config, None, as_node="__copy__")
cs = g2.get_state(copy_cfg)
print("copy src", cs.metadata, "copy parent", cs.parent_config["configurable"]["checkpoint_id"][-6:],
      "mid parent", mid.parent_config["configurable"]["checkpoint_id"][-6:], "next", cs.next)

# run_id in metadata?
import uuid
rid = uuid.uuid4()
g2.invoke({"q": "y"}, {"configurable": {"thread_id": "c3"}, "run_id": rid})
print("run_id metadata present:", g2.get_state({"configurable": {"thread_id": "c3"}}).metadata)

# history filtering by 'before' and as-of time: is there any timestamp query?
print("StateSnapshot.created_at sample:", h2[0].created_at)
