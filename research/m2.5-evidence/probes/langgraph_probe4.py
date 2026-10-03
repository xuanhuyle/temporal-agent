"""Probe 4: configurable keys copied into checkpoint metadata; as_node recorded where?"""
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

class S(TypedDict, total=False):
    topic: str
    joke: str

def gen(s): return {"topic": "socks"}
def write(s): return {"joke": "j:" + s["topic"]}

cp = InMemorySaver()
g = (StateGraph(S).add_node("gen", gen).add_node("write", write)
     .add_edge(START, "gen").add_edge("gen", "write").add_edge("write", END).compile(checkpointer=cp))
cfg = {"configurable": {"thread_id": "p4", "model_name": "model-A", "system_prompt_version": 3}}
g.invoke({}, cfg)
print("head metadata:", g.get_state({"configurable": {"thread_id": "p4"}}).metadata)
h = list(g.get_state_history({"configurable": {"thread_id": "p4"}}))
before = next(s for s in h if s.next == ("write",))
f = g.update_state(before.config, {"topic": "chickens"}, as_node="gen")
raw = cp.get_tuple(f)
print("fork metadata:", raw.metadata)
print("fork versions_seen:", raw.checkpoint["versions_seen"])
print("orig versions_seen:", cp.get_tuple(before.config).checkpoint["versions_seen"])
