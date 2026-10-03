"""Empirical probe of LangGraph checkpoint / replay / update_state semantics.

Run against the editable install of the cloned langgraph repo (commit 7dc9195e).
"""
import random
from typing import Annotated
from operator import add
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

CALLS = {"plan": 0, "act": 0, "tool": 0}
EXTERNAL_WORLD = {"file_written": []}  # stands in for an external side effect


class State(TypedDict, total=False):
    goal: str
    plan: str
    log: Annotated[list[str], add]


def plan(state: State):
    CALLS["plan"] += 1
    # nondeterministic "LLM" output
    return {"plan": f"plan-{random.randint(0, 10**6)}", "log": ["plan"]}


def act(state: State):
    CALLS["act"] += 1
    EXTERNAL_WORLD["file_written"].append(state["plan"])  # side effect outside state
    return {"log": [f"act:{state['plan']}"]}


def show(label, snaps):
    print(f"--- {label}")
    for s in snaps:
        c = s.config["configurable"]
        p = s.parent_config["configurable"]["checkpoint_id"][-6:] if s.parent_config else None
        print(
            f"id=..{c['checkpoint_id'][-6:]} parent=..{p} src={s.metadata.get('source')} "
            f"step={s.metadata.get('step')} parents={s.metadata.get('parents')} next={s.next} "
            f"plan={s.values.get('plan')} log={s.values.get('log')} meta_keys={sorted(s.metadata)}"
        )


cp = InMemorySaver()
g = (
    StateGraph(State)
    .add_node("plan", plan)
    .add_node("act", act)
    .add_edge(START, "plan")
    .add_edge("plan", "act")
    .add_edge("act", END)
    .compile(checkpointer=cp)
)
cfg = {"configurable": {"thread_id": "t1"}}
g.invoke({"goal": "g", "log": []}, cfg)
hist = list(g.get_state_history(cfg))
show("original run", hist)
print("CALLS after run", CALLS, "EXTERNAL", EXTERNAL_WORLD)

# Raw checkpoint tuple contents
before_act = next(s for s in hist if s.next == ("act",))
raw = cp.get_tuple(before_act.config)
print("RAW checkpoint keys:", sorted(raw.checkpoint.keys()))
print("RAW channel_values:", raw.checkpoint["channel_values"])
print("RAW channel_versions:", raw.checkpoint["channel_versions"])
print("RAW versions_seen:", raw.checkpoint["versions_seen"])
print("RAW metadata:", raw.metadata)
print("RAW pending_writes:", raw.pending_writes)
print("RAW parent_config:", raw.parent_config)

# Replay from before "act"
r = g.invoke(None, before_act.config)
print("CALLS after replay-before-act", CALLS, "EXTERNAL", EXTERNAL_WORLD)
# Replay from before "plan" -> plan re-executes with new random output
before_plan = next(s for s in hist if s.next == ("plan",))
r2 = g.invoke(None, before_plan.config)
print("CALLS after replay-before-plan", CALLS, "EXTERNAL", EXTERNAL_WORLD)
print("replay2 plan:", r2["plan"], "original plan:", hist[0].values["plan"])
hist2 = list(g.get_state_history(cfg))
show("history after two replays (all branches interleaved?)", hist2)

# Is the original checkpoint still intact (values + writes)?
raw_after = cp.get_tuple(before_act.config)
print("original before_act values unchanged:", raw_after.checkpoint["channel_values"] == raw.checkpoint["channel_values"])
print("original before_act pending_writes after replays:", raw_after.pending_writes)

# update_state fork from before_act
n_writes_before = len(cp.get_tuple(before_act.config).pending_writes or [])
fork_cfg = g.update_state(before_act.config, {"plan": "HUMAN-EDITED"})
fs = g.get_state(fork_cfg)
show("fork checkpoint", [fs])
print("fork parent == before_act:", fs.parent_config["configurable"]["checkpoint_id"] == before_act.config["configurable"]["checkpoint_id"])
print("latest == fork:", g.get_state(cfg).config["configurable"]["checkpoint_id"] == fork_cfg["configurable"]["checkpoint_id"])
pw_after = cp.get_tuple(before_act.config).pending_writes or []
print("pending writes on SOURCE checkpoint before/after update_state:", n_writes_before, len(pw_after), pw_after)
g.invoke(None, fork_cfg)
print("CALLS after fork run", CALLS, "EXTERNAL", EXTERNAL_WORLD)

# Is there a 'reason' / provenance field anywhere?
print("fork metadata:", fs.metadata)

# filter by metadata source
print("count source=update:", len(list(g.get_state_history(cfg, filter={"source": "update"}))))
print("count source=fork:", len(list(g.get_state_history(cfg, filter={"source": "fork"}))))

# custom metadata via config
g.invoke({"goal": "g2", "log": []}, {"configurable": {"thread_id": "t2"}, "metadata": {"why": "testing-reason"}})
print("custom metadata on t2 head:", g.get_state({"configurable": {"thread_id": "t2"}}).metadata)

# ---------------- interrupts ----------------
CALLS2 = {"ask": 0}


class S2(TypedDict, total=False):
    v: Annotated[list[str], add]


def ask(state: S2):
    CALLS2["ask"] += 1
    ans = interrupt("name?")
    return {"v": [f"hi {ans}"]}


g2 = StateGraph(S2).add_node("ask", ask).add_edge(START, "ask").compile(checkpointer=InMemorySaver())
c2 = {"configurable": {"thread_id": "i1"}}
g2.invoke({"v": []}, c2)
g2.invoke(Command(resume="Alice"), c2)
h = list(g2.get_state_history(c2))
b = [s for s in h if s.next == ("ask",)][-1]
out = g2.invoke(None, b.config)
print("interrupt replay output:", out, "ask calls:", CALLS2)
st = g2.get_state(c2)
print("after replay: next", st.next, "interrupts", st.interrupts)

# ---------------- subgraph namespaces ----------------
class SS(TypedDict, total=False):
    v: Annotated[list[str], add]


def sa(state):
    x = interrupt("a?")
    return {"v": [f"a:{x}"]}


def sb(state):
    return {"v": ["b"]}


sub = StateGraph(SS).add_node("sa", sa).add_node("sb", sb).add_edge(START, "sa").add_edge("sa", "sb").compile()
parent = StateGraph(SS).add_node("subnode", sub).add_edge(START, "subnode").compile(checkpointer=(cp3 := InMemorySaver()))
c3 = {"configurable": {"thread_id": "s1"}}
parent.invoke({"v": []}, c3)
ps = parent.get_state(c3, subgraphs=True)
print("parent task state config:", ps.tasks[0].state.config)
print("namespaces stored:", list(cp3.storage["s1"].keys()))
parent.invoke(Command(resume="X"), c3)
print("namespaces stored after completion:", {ns: len(v) for ns, v in cp3.storage["s1"].items()})
for ns, v in cp3.storage["s1"].items():
    if ns:
        for cid in v:
            t = cp3.get_tuple({"configurable": {"thread_id": "s1", "checkpoint_ns": ns, "checkpoint_id": cid}})
            print("  sub ckpt", ns, "src", t.metadata.get("source"), "step", t.metadata.get("step"), "parents", t.metadata.get("parents"))
