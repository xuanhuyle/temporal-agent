"""Protocol v0.2 runtime inside real runs: world history, commands, metering, outputs.

Uses in-process reference agents on the mini scenario, so it checks the
harness integration independently of any contestant.
"""

from __future__ import annotations

import json

import pytest

from harness.agent import Agent, AgentResponse, ModelSettings, StepBudget
from harness.errors import BudgetExceeded, ToolError
from harness.replay import replay_run
from harness.runner import OUTPUT_FILES, RunConfig, run
from harness.trace import read_jsonl

NO_HYGIENE = {"hygiene": False}


class HistoryProbe(Agent):
    kind = "historyprobe"
    role = "reference"

    def __init__(self, name: str = "hprobe") -> None:
        super().__init__(name)
        self.log: list[dict] = []

    def _try(self, tools, fn) -> str:
        try:
            fn()
        except ToolError as exc:
            return str(exc)
        return "LEAK"

    def on_start(self, tools) -> None:
        self.log.append({
            "seq": 0,
            "history": [h["seq"] for h in tools.history()],
            "future": self._try(tools, lambda: tools.read_at(1, "app.py")),
        })

    def on_event(self, event, tools) -> AgentResponse:
        hist = tools.history()
        tools.write_file("app.py", "# my local edit\n")
        self.log.append({
            "seq": event.seq,
            "history": [h["seq"] for h in hist],
            "keys": sorted({k for h in hist for k in h}),
            "future": self._try(tools, lambda: tools.read_at(event.seq + 1, "app.py")),
            "future_list": self._try(tools, lambda: tools.list_at(event.seq + 1)),
            "future_diff": self._try(tools, lambda: tools.diff(0, event.seq + 1)),
            "absurd": self._try(tools, lambda: tools.read_at(10**9, "app.py")),
            "negative": self._try(tools, lambda: tools.read_at(-1, "app.py")),
            "now": tools.read_at(event.seq, "app.py"),
        })
        return AgentResponse()


def test_history_exposes_only_states_up_to_now(mini_scenario, runs_dir):
    probe = HistoryProbe()
    result = run(mini_scenario, [probe], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert result.status == "completed"
    assert probe.log[0]["history"] == [0]
    assert probe.log[0]["future"].startswith("no repository state at seq 1; available: 0..0")
    for entry in probe.log[1:]:
        seq = entry["seq"]
        assert entry["history"] == list(range(seq + 1))
        assert entry["keys"] == ["changed_paths", "event_id", "seq", "timestamp", "tree_sha256"]
        assert entry["future"] == f"no repository state at seq {seq + 1}; available: 0..{seq}"
        assert entry["future_list"] == entry["future"]
        assert entry["future_diff"] == entry["future"]
        assert entry["absurd"] == f"no repository state at seq {10**9}; available: 0..{seq}"
        assert entry["negative"] == f"no repository state at seq -1; available: 0..{seq}"
        # history is the world timeline: the agent's own edit is not in it
        assert "# my local edit" not in entry["now"]


def test_world_states_match_frozen_hashes_and_are_traced(mini_scenario, runs_dir):
    result = run(mini_scenario, [HistoryProbe()], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    revealed = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "world_state_revealed"]
    assert [r["seq"] for r in revealed] == list(range(len(mini_scenario.load_events()) + 1))
    expected = mini_scenario.data.get("world_state_hashes")
    if expected:
        assert [r["tree_sha256"] for r in revealed[1:]] == expected
    assert revealed[0]["tree_sha256"] == mini_scenario.data["content_hashes"]["seed_repo"]


class Spender(Agent):
    kind = "spender"
    role = "reference"

    def __init__(self, name: str = "spender") -> None:
        super().__init__(name)
        self.errors: list[str] = []

    def on_event(self, event, tools) -> AgentResponse:
        tools.history()
        tools.read_at(0, "app.py")
        tools.history()  # third counted call: over a budget of 2
        return AgentResponse()


def test_history_calls_count_against_the_tool_budget(mini_scenario, runs_dir):
    result = run(mini_scenario, [Spender()], RunConfig(runs_dir=runs_dir, budget=StepBudget(max_tool_calls_per_event=2), **NO_HYGIENE))
    assert result.scores["agents"]["spender"]["step_status"] == {"budget_exceeded": len(mini_scenario.load_events())}
    calls = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call" and r["seq"] == 1]
    assert [c["status"] for c in calls] == ["ok", "ok", "budget_exceeded"]


class Commander(Agent):
    kind = "commander"
    role = "reference"

    def __init__(self, name: str = "cmd") -> None:
        super().__init__(name)
        self.results: list[dict] = []

    def on_event(self, event, tools) -> AgentResponse:
        if event.seq == 1:
            self.results.append(tools.run_command('python -c "print(6 * 7)"'))
            try:
                tools.run_command("bash -c ls")
            except ToolError as exc:
                self.results.append({"error": str(exc)})
        return AgentResponse()


def test_run_command_is_traced_metered_and_deterministic(mini_scenario, runs_dir):
    agent = Commander()
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    ok = agent.results[0]
    assert ok["exit_code"] == 0 and ok["output"].strip() == "42" and ok["timed_out"] is False
    assert "wall_clock_ms" not in ok  # timing is volatile and kept out of the agent-visible result
    assert "error" in agent.results[1]
    calls = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call" and r["tool"] == "run_command"]
    assert [c["status"] for c in calls] == ["ok", "error"]
    assert "wall_clock_ms" in calls[0]["meter"]
    eff = result.scores["agents"]["cmd"]["efficiency"]
    assert eff["commands"] == 2 and eff["tool_calls"] == 2 and eff["command_output_chars"] > 0


def test_v0_2_outputs_and_metadata(mini_scenario, runs_dir):
    result = run(mini_scenario, [HistoryProbe()], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    for name in OUTPUT_FILES:
        assert (result.run_dir / name).is_file(), name
    meta = json.loads((result.run_dir / "metadata.json").read_text())
    assert meta["protocol_version"] == "v0.2"
    assert meta["isolation"] == {"hprobe": "in_process"}
    assert meta["config"]["model"]["provider"] == "none"
    assert "harness-metered" in meta["token_accounting"]
    assert meta["config"]["instructions_version"] == "tab.instructions/2"
    for key in ("max_commands_per_event", "max_model_calls_per_event", "wall_clock_s_per_event"):
        assert key in meta["config"]["budget"]


def test_replay_reproduces_history_and_command_calls(mini_scenario, runs_dir):
    result = run(mini_scenario, [HistoryProbe(), Commander()], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    _, report = replay_run(result.run_dir)
    assert report["match"], report


class ModelUser(Agent):
    kind = "modeluser"
    role = "reference"

    def on_event(self, event, tools) -> AgentResponse:
        from harness.llm import ModelMessage, ModelRequest

        req = ModelRequest(system="sys", messages=(ModelMessage("user", f"<<start>> {event.subject}"),), purpose="summary")
        tools.model_complete(req)
        tools.embed([event.subject, event.body])
        return AgentResponse()


def test_model_calls_are_metered_by_the_harness_and_replayed_from_the_recording(mini_scenario, runs_dir):
    settings = ModelSettings(provider="fake", name="fake-v1", embedding_provider="hash", embedding_model="hash-ngram-v1",
                             embedding_dims=64)
    result = run(mini_scenario, [ModelUser("m1"), ModelUser("m2")], RunConfig(runs_dir=runs_dir, model=settings, **NO_HYGIENE))
    n = len(mini_scenario.load_events())
    for name in ("m1", "m2"):
        eff = result.scores["agents"][name]["efficiency"]
        assert eff["model_calls"] == n and eff["embedding_calls"] == n
        assert eff["model_input_tokens"] > 0 and eff["model_output_tokens"] > 0 and eff["embedding_tokens"] > 0
        assert eff["reported_usage"]["model_calls"] == 0  # self-reports are not what counts
    meters = [r["meter"] for r in read_jsonl(result.run_dir / "trace.jsonl")
              if r["type"] == "tool_call" and r["tool"] == "model_complete"]
    assert {(m["provider"], m["model"]) for m in meters} == {("fake", "fake-v1")}
    _, report = replay_run(result.run_dir)
    assert report["match"], report


def test_model_tools_without_a_configured_model_are_tool_errors(mini_scenario, runs_dir):
    result = run(mini_scenario, [ModelUser("m")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert set(result.scores["agents"]["m"]["step_status"]) == {"agent_error"}
    errs = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call"]
    assert errs and all(r["status"] == "error" for r in errs)


@pytest.mark.parametrize("bad", [True, 1.5, "1"])
def test_history_seq_must_be_an_int(mini_scenario, runs_dir, bad):
    class BadSeq(Agent):
        kind = "badseq"
        role = "reference"

        def on_event(self, event, tools) -> AgentResponse:
            try:
                tools.read_at(bad, "app.py")
            except ToolError:
                return AgentResponse()
            raise AssertionError("accepted a non-int seq")

    result = run(mini_scenario, [BadSeq("bad")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert set(result.scores["agents"]["bad"]["step_status"]) == {"ok"}


def test_budget_exceeded_is_a_base_exception():
    assert issubclass(BudgetExceeded, BaseException) and not issubclass(BudgetExceeded, Exception)
