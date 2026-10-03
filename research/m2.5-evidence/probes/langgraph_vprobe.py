"""Verifier probe (independent of analyst probes)."""
from dataclasses import dataclass
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

class S(TypedDict, total=False):
    topic: str
    joke: str

@dataclass
class Ctx:
    model_name: str

def gen(s): return {"topic": "socks"}
def write(s): return {"joke": "j:" + s["topic"]}

cp = InMemorySaver()
g = (StateGraph(S, context_schema=Ctx).add_node("gen", gen).add_node("write", write)
     .add_edge(START, "gen").add_edge("gen", "write").add_edge("write", END).compile(checkpointer=cp))
cfg = {"configurable": {"thread_id": "v"}}
g.invoke({}, cfg, context=Ctx(model_name="model-CTX"))
print("A head metadata (context= only):", g.get_state(cfg).metadata)
h = list(g.get_state_history(cfg))
before = next(s for s in h if s.next == ("write",))
snap_before = g.get_state(before.config)
print("B before tasks (pre-update):", [(t.name, t.result) for t in snap_before.tasks])
# update_state with metadata in the config
ucfg = {"configurable": {**before.config["configurable"]}, "metadata": {"why": "ADR-7 reopened", "actor": "agent"}}
f = g.update_state(ucfg, {"topic": "chickens"}, as_node="gen")
print("C fork metadata with config metadata:", cp.get_tuple(f).metadata)
snap_before2 = g.get_state(before.config)
print("D before tasks (post-update):", [(t.name, t.result) for t in snap_before2.tasks])
print("D2 before values unchanged:", snap_before.values == snap_before2.values)
print("E raw pending writes on source:", [(w[1], w[2]) for w in cp.get_tuple(before.config).pending_writes])
# filter history by custom metadata
print("F filter by why:", [s.metadata.get("source") for s in g.get_state_history(cfg, filter={"why": "ADR-7 reopened"})])
# __copy__
c = g.update_state(before.config, None, as_node="__copy__")
t = cp.get_tuple(c)
print("G copy meta:", t.metadata, "parent==before.parent:", t.parent_config["configurable"]["checkpoint_id"] == before.parent_config["configurable"]["checkpoint_id"])
