"""Probe ActiveGraph v1.12.0 temporal semantics (read-only analysis script).

Checks:
 A. fork(at_event) is a strict prefix (objects created after cutoff absent).
 B. promote.build_base_graph(parent, evt) acts as state_at(evt).
 C. compute_diff between two time slices of the SAME run (diff(t1,t2)).
 D. runs-table lineage columns.
 E. post-cutoff tool response served to a fork via parent-populated cache.
 F. fork inherits parent's CURRENT frame (goal/constraints), not as-of-t frame.
"""
import os
import sqlite3
import sys
import tempfile
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "activegraph"))

from pydantic import BaseModel

from activegraph import Graph, Runtime, behavior, llm_behavior, tool, clear_registry
from activegraph.frame import Frame
from activegraph.llm import LLMResponse, ToolCall
from activegraph.runtime.diff import compute_diff
from activegraph.runtime.promote import build_base_graph

tmp = tempfile.mkdtemp()

# ---------------- A-D: pure graph run ----------------
clear_registry()


@behavior(name="planner", on=["goal.created"])
def planner(event, graph, ctx):
    graph.add_object("decision", {"choice": "ship_v1", "status": "made"})
    graph.emit("world.update", {"note": "later evidence"})


@behavior(name="reviser", on=["world.update"])
def reviser(event, graph, ctx):
    d = graph.all_objects()[0] if hasattr(graph, "all_objects") else None
    graph.add_object("finding", {"text": "dependency deprecated"})


db = os.path.join(tmp, "a.db")
rt = Runtime(Graph(), persist_to=db, frame=Frame(goal="G-original", constraints=["c1"]))
rt.run_goal("evaluate")
evs = rt.graph.events
print("A/parent events:", [(e.id, e.type) for e in evs])
cut = next(e for e in evs if e.type == "object.created").id
fork = rt.fork(at_event=cut, label="probe-fork")
print("A/fork objects (no run):", [(o.type, o.data) for o in fork.graph.all_objects()])
print("A/parent objects:", [(o.type, o.data) for o in rt.graph.all_objects()])

# B: state_at
t1 = cut
t2 = evs[-1].id
g1 = build_base_graph(rt.graph, t1)
g2 = build_base_graph(rt.graph, t2)
print("B/state_at(t1) objects:", [o.type for o in g1.all_objects()])
print("B/state_at(t2) objects:", [o.type for o in g2.all_objects()])
d = compute_diff(g1, g2, "t1", "t2")
print("C/diff(t1,t2) divergent objects:", [x.summary() for x in d.divergent_objects])

# D: lineage
con = sqlite3.connect(db)
print("D/runs:", con.execute("select run_id,parent_run_id,forked_at_event_id,label,goal from runs").fetchall())

# F: frame inheritance: change parent frame after the fact, then fork at early event
rt.frame = Frame(goal="G-revised-later", constraints=["c2"])
fork2 = rt.fork(at_event=evs[0].id, label="frame-probe")
print("F/fork frame goal:", fork2.frame.goal if fork2.frame else None,
      "| parent goal.created payload:", evs[0].payload)

# ---------------- E: tool cache post-cutoff leakage ----------------
clear_registry()
WORLD = {"status": "calm"}


class _In(BaseModel):
    key: str


class _Out(BaseModel):
    value: str


class _Final(BaseModel):
    text: str


@tool(name="read_world", input_schema=_In, output_schema=_Out, deterministic=False)
def read_world(args, ctx):
    return _Out(value=WORLD[args.key])


from activegraph.tools.decorators import get_tool_registry
T = next(t for t in get_tool_registry() if t.name == "read_world")


def provider():
    responses = [
        LLMResponse(raw_text="", parsed=None, input_tokens=1, output_tokens=1,
                    cost_usd=Decimal("0"), latency_seconds=0.0, model="m",
                    finish_reason="tool_use",
                    tool_calls=[ToolCall(id="c1", name="read_world", args={"key": "status"})]),
        LLMResponse(raw_text="", parsed=_Final(text="done"), input_tokens=1, output_tokens=1,
                    cost_usd=Decimal("0"), latency_seconds=0.0, model="m",
                    finish_reason="end_turn"),
    ]

    class P:
        i = 0

        def complete(self, **kw):
            r = responses[self.i]
            self.i += 1
            return r

        def estimate_cost(self, **kw):
            return Decimal("0")

        def count_tokens(self, **kw):
            return 1

    return P()


@behavior(name="seed", on=["goal.created"])
def seed(event, graph, ctx):
    graph.add_object("doc", {"title": "t"})


@llm_behavior(name="checker", on=["object.created"], where={"object.type": "doc"},
              output_schema=_Final, tools=[T])
def checker(event, graph, ctx, out):
    pass


db2 = os.path.join(tmp, "e.db")
# The parent's tool call happens AFTER goal.created; by then the world says "breach".
WORLD["status"] = "breach_disclosed"
p = Runtime(Graph(), llm_provider=provider(), persist_to=db2)
p.run_goal("g")
cutoff = next(e for e in p.graph.events if e.type == "goal.created").id
post = [(e.id, e.payload.get("result") or e.payload) for e in p.graph.events if e.type == "tool.responded"]
print("E/parent cutoff:", cutoff, "parent post-cutoff tool.responded:", post)
# Re-create a "world as of cutoff" for the fork's live calls:
WORLD["status"] = "calm"
f = p.fork(at_event=cutoff, label="cache-probe", replay_llm_cache=True,
           replay_tool_cache=True, llm_provider=provider())
f.run_until_idle()
print("E/fork tool.responded (cache on):",
      [(e.id, e.payload.get("cache_hit"), e.payload.get("result") or e.payload.get("output")) for e in f.graph.events if e.type == "tool.responded"])
f2 = p.fork(at_event=cutoff, label="cache-off", replay_llm_cache=False,
            replay_tool_cache=False, llm_provider=provider())
f2.run_until_idle()
print("E/fork tool.responded (cache off):",
      [(e.id, e.payload.get("cache_hit"), e.payload.get("result") or e.payload.get("output")) for e in f2.graph.events if e.type == "tool.responded"])
