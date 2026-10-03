"""Runner protocol: outputs, ordering, failure preservation, no overwrites."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.agents import create_agent
from harness.canonical import tree_hash
from harness.runner import OUTPUT_FILES, RunConfig, run
from harness.scenario import ScenarioError, load_scenario
from harness.trace import read_jsonl
from scripted_agents import (
    GreedyAgent,
    IndexingAgent,
    InvalidResponseAgent,
    RaisingAgent,
    RecordingAgent,
    SetupFailAgent,
)


def test_run_writes_all_outputs(mini_scenario, runs_dir):
    result = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    assert result.status == "completed"
    for name in OUTPUT_FILES:
        assert (result.run_dir / name).is_file(), name
    meta = json.loads((result.run_dir / "metadata.json").read_text())
    assert meta["status"] == "completed"
    assert meta["fingerprint"] == result.fingerprint
    assert meta["scenario"]["scenario_id"] == "mini_v1"
    assert meta["agents"] == [{"name": "dummy", "kind": "dummy", "role": "reference", "config": {}}]
    assert set(meta["schemas"]) == {"event", "action", "trace", "scores", "scenario", "ground_truth"}
    assert len(read_jsonl(result.run_dir / "events.jsonl")) == 3
    actions = read_jsonl(result.run_dir / "actions.jsonl")
    assert [(a["seq"], a["agent"]) for a in actions] == [(1, "dummy"), (2, "dummy"), (3, "dummy")]
    assert all(set(a["usage"]) == {"model_input_tokens", "model_output_tokens", "retrieval_tokens", "model_calls", "cost_usd"} for a in actions)
    trace = read_jsonl(result.run_dir / "trace.jsonl")
    assert [r["idx"] for r in trace] == list(range(len(trace)))
    assert trace[0]["type"] == "run_start" and trace[-1]["type"] == "run_end"
    scores = json.loads((result.run_dir / "scores.json").read_text())
    eff = scores["agents"]["dummy"]["efficiency"]
    assert {"model_input_tokens", "model_output_tokens", "retrieval_tokens", "model_calls", "cost_usd",
            "tool_calls", "wall_clock_ms", "steps"} <= set(eff)
    assert (result.run_dir / "final_state" / "dummy" / "workspace" / "VENDOR.md").is_file()


def test_events_delivered_in_order_after_world_changes(mini_scenario, runs_dir):
    agent = RecordingAgent()
    run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir))
    assert agent.seen == [1, 2, 3]
    # No lookahead: event 2's payload is absent at step 1 and present from step 2.
    assert "VENDOR.md" not in agent.files_at[1]
    assert "VENDOR.md" in agent.files_at[2]
    assert "README.md" in agent.files_at[1]  # event 1's own change is applied before delivery


def test_lockstep_protocol_order(mini_scenario, runs_dir, monkeypatch):
    """World applied to every agent before delivery; scoring only after every agent finished the step."""
    from evaluation import scorer

    log: list[tuple[str, str, int]] = []

    class Logged(RecordingAgent):
        def on_event(self, event, tools):
            log.append(("on_event", self.name, event.seq))
            return super().on_event(event, tools)

    real_observe = scorer.Evaluator.observe_step

    def observe(self, agent, seq, actions):
        log.append(("observe", agent, seq))
        return real_observe(self, agent, seq, actions)

    monkeypatch.setattr(scorer.Evaluator, "observe_step", observe)
    result = run(mini_scenario, [Logged("a"), Logged("b"), Logged("c")], RunConfig(runs_dir=runs_dir))
    for seq in (1, 2, 3):
        steps = [i for i, (kind, _, s) in enumerate(log) if s == seq and kind == "on_event"]
        observes = [i for i, (kind, _, s) in enumerate(log) if s == seq and kind == "observe"]
        assert len(steps) == 3 and len(observes) == 3
        assert max(steps) < min(observes)
    trace = read_jsonl(result.run_dir / "trace.jsonl")
    for seq in (1, 2, 3):
        applied = [r["idx"] for r in trace if r.get("seq") == seq and r["type"] == "world_event_applied"]
        delivered = [r["idx"] for r in trace if r.get("seq") == seq and r["type"] == "event_delivered"]
        assert len(applied) == 3 and max(applied) < min(delivered)
        order = next(r["order"] for r in trace if r["type"] == "step_order" and r["seq"] == seq)
        assert [r["agent"] for r in trace if r.get("seq") == seq and r["type"] == "event_delivered"] == order
    assert all(sorted(r["order"]) == ["a", "b", "c"] for r in trace if r["type"] == "step_order")
    evaluation = read_jsonl(result.run_dir / "evaluation.jsonl")
    assert [(r["seq"], r["agent"]) for r in evaluation] == [(s, a) for s in (1, 2, 3) for a in ("a", "b", "c")]


def test_step_order_is_seeded_and_varies():
    from harness.runner import step_order

    names = ["a", "b", "c", "d"]
    assert step_order(names, 0, 1) == step_order(names, 0, 1)
    orders = {tuple(step_order(names, 0, seq)) for seq in range(1, 30)}
    assert len(orders) > 1 and all(sorted(o) == names for o in orders)


def test_contestants_refused_on_draft_scenarios(tmp_path, runs_dir):
    from conftest import build_mini_repo
    from harness.agent import Agent, AgentResponse

    class Contestant(Agent):
        kind = "contestant"

        def on_event(self, event, tools):
            return AgentResponse()

    scenario = load_scenario(build_mini_repo(tmp_path / "draft_repo"))
    with pytest.raises(ScenarioError, match="frozen"):
        run(scenario, [Contestant("c")], RunConfig(runs_dir=runs_dir, allow_draft=True))


def test_agent_failures_are_recorded_not_fatal(mini_scenario, runs_dir):
    agents = [RaisingAgent("raiser"), GreedyAgent("greedy"), InvalidResponseAgent("invalid"), SetupFailAgent("broken"),
              create_agent("dummy")]
    result = run(mini_scenario, agents, RunConfig(runs_dir=runs_dir))
    assert result.status == "completed"
    status = {a: s["step_status"] for a, s in result.scores["agents"].items()}
    assert status["raiser"] == {"agent_error": 1, "ok": 2}
    assert status["greedy"] == {"budget_exceeded": 3}
    assert status["invalid"] == {"invalid_response": 3}
    assert status["broken"] == {"disabled": 3}
    assert status["dummy"] == {"ok": 3}
    actions = read_jsonl(result.run_dir / "actions.jsonl")
    raiser2 = next(a for a in actions if a["agent"] == "raiser" and a["seq"] == 2)
    assert raiser2["error"] == "RuntimeError: model API exploded"
    assert raiser2["tool_calls"] == [{"tool": "read_file", "args": {"path": "app.py"}, "status": "ok"}]
    greedy = next(a for a in actions if a["agent"] == "greedy")
    assert len(greedy["tool_calls"]) == 21  # budget 20 + the refused call
    trace = read_jsonl(result.run_dir / "trace.jsonl")
    setup = next(r for r in trace if r["type"] == "agent_setup" and r["agent"] == "broken")
    assert setup["status"] == "agent_error" and "cannot load model weights" in setup["error"]


def test_run_directories_are_never_overwritten(mini_scenario, runs_dir):
    first = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    before = tree_hash(first.run_dir)
    second = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    third = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    assert second.run_id == first.run_id + "__2"
    assert third.run_id == first.run_id + "__3"
    assert tree_hash(first.run_dir) == before


def test_harness_failure_is_preserved(mini_scenario, runs_dir, monkeypatch):
    from evaluation import scorer

    def boom(self, *a, **k):
        raise RuntimeError("evaluator crashed")

    monkeypatch.setattr(scorer.Evaluator, "finalize", boom)
    with pytest.raises(RuntimeError, match="evaluator crashed"):
        run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    (run_dir,) = list(runs_dir.iterdir())
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["status"] == "failed" and "evaluator crashed" in meta["error"]
    trace = read_jsonl(run_dir / "trace.jsonl")
    assert trace[-1]["type"] == "run_end" and trace[-1]["status"] == "failed"
    assert len(read_jsonl(run_dir / "actions.jsonl")) == 3  # per-step records survived


def test_agent_names_must_be_unique_and_safe(mini_scenario, runs_dir):
    with pytest.raises(ValueError, match="unique"):
        run(mini_scenario, [create_agent("dummy"), create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    with pytest.raises(ValueError, match="invalid agent name"):
        run(mini_scenario, [create_agent("dummy:../evil")], RunConfig(runs_dir=runs_dir))
    with pytest.raises(ValueError, match="unknown agent kind"):
        create_agent("tesseract")


def test_draft_scenarios_require_explicit_opt_in(tmp_path, runs_dir):
    from conftest import build_mini_repo

    manifest = build_mini_repo(tmp_path / "draft_repo")
    scenario = load_scenario(manifest)
    with pytest.raises(ScenarioError, match="draft"):
        run(scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    result = run(scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, allow_draft=True))
    assert result.status == "completed"
    assert json.loads((result.run_dir / "metadata.json").read_text())["scenario"]["status"] == "draft"


def test_world_conflicts_are_recorded(mini_scenario, runs_dir):
    from harness.canonical import sha256_bytes
    from harness.scenario import ScenarioIntegrityError
    from scripted_agents import ReopenOnTriggerAgent

    # Event 3 now rewrites README.md expecting the version event 1 wrote.
    events = Path(mini_scenario.events_file)
    lines = events.read_text().splitlines()
    ev3 = json.loads(lines[2])
    ev3["world_changes"] = [{"op": "write_file", "path": "README.md", "content": "# Mini app v2\n",
                             "expect_sha256": sha256_bytes(b"# Mini app\n")}]
    lines[2] = json.dumps(ev3)
    events.write_text("\n".join(lines) + "\n")
    scenario = load_scenario(mini_scenario.manifest_path)
    with pytest.raises(ScenarioIntegrityError):  # frozen content changed
        run(scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    scenario.data["status"] = "draft"

    editor = ReopenOnTriggerAgent("editor", "evt-0002", "ADR-0001", writes={"README.md": "# edited by agent\n"})
    result = run(scenario, [editor, create_agent("dummy")], RunConfig(runs_dir=runs_dir, allow_draft=True))
    ev_out = read_jsonl(result.run_dir / "events.jsonl")[2]
    assert [c["reason"] for c in ev_out["conflicts"]["editor"]] == ["precondition"]
    assert ev_out["conflicts"]["dummy"] == []
    final = result.run_dir / "final_state" / "editor" / "workspace" / "README.md"
    assert final.read_text() == "# Mini app v2\n"  # the world is authoritative


def test_on_start_ingests_seed_with_budget_and_is_traced(mini_scenario, runs_dir):
    agent = IndexingAgent()
    result = run(mini_scenario, [agent, create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    assert "app.py" in agent.indexed and "README.md" not in agent.indexed  # seed only, before event 1
    trace = read_jsonl(result.run_dir / "trace.jsonl")
    start = {r["agent"]: r for r in trace if r["type"] == "agent_start"}
    assert start["indexer"]["status"] == "ok" and start["indexer"]["tool_calls"] == 1 + len(agent.indexed)
    assert start["dummy"]["tool_calls"] == 0
    first_event_idx = min(r["idx"] for r in trace if r["type"] == "world_event_applied")
    assert all(r["idx"] < first_event_idx for r in trace if r["type"] == "tool_call" and r["seq"] == 0)
    assert result.scores["agents"]["indexer"]["efficiency"]["tool_calls"] == 1 + len(agent.indexed)
