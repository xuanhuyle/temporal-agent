"""Regression tests for findings from the adversarial benchmark review.

Each test reproduces a confirmed defect (leakage, determinism/replay, robustness)
and pins the fix.
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import tempfile
import threading
from pathlib import Path

import pytest

from conftest import MINI_CANARY
from harness.agent import Agent, AgentResponse, HistoricalState, NoteAction, ReopenAction, StepBudget
from harness.agents import create_agent
from harness.replay import replay_run
from harness.runner import RunConfig, run
from harness.tools import BudgetExceeded
from harness.trace import read_jsonl, run_fingerprint
from harness.workspace import ToolError
from scripted_agents import _TestAgent

NO_HYGIENE = {"hygiene": False}


def _status(result, agent):
    return result.scores["agents"][agent]["step_status"]


# ------------------------------------------------- agent faults never abort a run
@pytest.mark.parametrize("hook", ["setup", "on_start", "on_event", "teardown"])
@pytest.mark.parametrize("exc_type", [SystemExit, asyncio.CancelledError, GeneratorExit])
def test_base_exceptions_from_agents_are_recorded_not_fatal(mini_scenario, runs_dir, hook, exc_type):
    class Exploding(_TestAgent):
        kind = "exploding"

        def setup(self, context):
            super().setup(context)
            if hook == "setup":
                raise exc_type("boom")

        def on_start(self, tools):
            if hook == "on_start":
                raise exc_type("boom")

        def on_event(self, event, tools):
            if hook == "on_event" and event.seq == 2:
                raise exc_type("boom")
            return AgentResponse()

        def teardown(self):
            if hook == "teardown":
                raise exc_type("boom")

    result = run(mini_scenario, [Exploding("x"), create_agent("dummy")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert result.status == "completed"
    assert _status(result, "dummy") == {"ok": 3}
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# --------------------------------------------------- serialization is total
class SurrogateAgent(_TestAgent):
    kind = "surrogate"

    def on_event(self, event, tools):
        if event.seq == 1:
            try:
                tools.write_file("notes/\udcff.md", "x")
            except ToolError:
                pass
            try:
                tools.write_file("notes/ok.md", "half an emoji \ud83d")
            except ToolError:
                pass
            return AgentResponse(actions=[NoteAction("truncated \ud83d"), ReopenAction("ADR-0001", rationale="\udcff")])
        if event.seq == 2:
            raise RuntimeError("bad text \ud83d")
        return AgentResponse()


def test_lone_surrogates_never_crash_the_run(mini_scenario, runs_dir):
    result = run(mini_scenario, [SurrogateAgent("s")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert result.status == "completed"
    calls = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call"]
    assert [c["status"] for c in calls] == ["error", "error"]  # both rejected as non-UTF-8 arguments
    assert (result.run_dir / "MANIFEST.sha256").stat().st_size > 0
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# ----------------------------------------- OS-level tool failures are recorded
class OddPathAgent(_TestAgent):
    kind = "oddpath"

    def on_event(self, event, tools):
        if event.seq == 1:
            for fn, args in (
                (tools.read_file, ("app.py/inner.txt",)),
                (tools.write_file, ("app.py/inner.txt", "x")),
                (tools.read_file, ("x" * 300,)),
                (tools.write_file, (Path("notes.md"), "x")),
                (tools.read_file, (b"app.py",)),
                (tools.list_files, ("app.py/",)),
            ):
                try:
                    fn(*args)
                except ToolError:
                    pass
        return AgentResponse()


def test_os_errors_and_odd_arguments_are_traced_and_replayable(mini_scenario, runs_dir):
    result = run(mini_scenario, [OddPathAgent("o")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    calls = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call"]
    assert len(calls) == 6 == result.scores["agents"]["o"]["efficiency"]["tool_calls"]
    text = (result.run_dir / "trace.jsonl").read_text()
    assert "tab-lane" not in text and tempfile.gettempdir() + "/" not in text
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# ----------------------------------------------- budget replay fidelity
class FlushOnBudgetAgent(_TestAgent):
    kind = "flusher"

    def on_event(self, event, tools):
        if event.seq == 1:
            try:
                while True:
                    tools.list_files()
            finally:
                try:
                    tools.write_file("notes.md", "flush")  # refused too: the budget is spent
                except BudgetExceeded:
                    pass
        if event.seq == 2:
            raise BudgetExceeded("own token budget exhausted")
        return AgentResponse()


def test_budget_steps_replay_faithfully(mini_scenario, runs_dir):
    result = run(mini_scenario, [FlushOnBudgetAgent("f")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert _status(result, "f") == {"budget_exceeded": 2, "ok": 1}
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# ----------------------------------------------- guard violations & replay
class CuriousAgent(_TestAgent):
    kind = "curious"

    def __init__(self, name, target):
        super().__init__(name)
        self.target = target

    def on_event(self, event, tools):
        if event.seq == 1:
            try:
                open(self.target).read()
            except PermissionError:
                pass
        if event.seq == 2:
            try:
                open(self.target).read()
            finally:
                pass  # the violation is followed by an agent error
        return AgentResponse()


def test_guard_violations_survive_errors_and_do_not_break_replay(mini_scenario, runs_dir):
    agent = CuriousAgent("c", mini_scenario.ground_truth_dir / "labels.json")
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    responses = {r["seq"]: r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "agent_response"}
    assert responses[1]["guard_violations"] == ["open"] and responses[1]["status"] == "ok"
    assert responses[2]["guard_violations"] == ["open"] and responses[2]["status"] == "agent_error"
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# ----------------------------------------------- fingerprint vs private state
class PathRecordingMemory(_TestAgent):
    kind = "pathmem"

    def on_event(self, event, tools):
        (self.context.state_dir / "config.json").write_text(json.dumps({"persist_directory": str(self.context.state_dir)}))
        return AgentResponse()


def test_fingerprint_ignores_path_bearing_private_state(mini_scenario, runs_dir):
    a = run(mini_scenario, [PathRecordingMemory("m")], RunConfig(runs_dir=runs_dir / "a", **NO_HYGIENE))
    b = run(mini_scenario, [PathRecordingMemory("m")], RunConfig(runs_dir=runs_dir / "b", **NO_HYGIENE))
    assert a.fingerprint == b.fingerprint


def test_replay_directory_manifest_is_complete(mini_scenario, runs_dir):
    original = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    replayed, _ = replay_run(original.run_dir)
    listed = {line.split("  ", 1)[1] for line in (replayed.run_dir / "MANIFEST.sha256").read_text().splitlines()}
    assert "replay_report.json" in listed


def test_generators_are_materialized_in_actions():
    hs = HistoricalState(known_then=(x for x in ["seed"]), known_now_about_then=iter(["evt-0002"]))
    assert hs.known_then == ("seed",) and hs.known_now_about_then == ("evt-0002",)
    assert ReopenAction("ADR-0001", evidence=(e for e in ["evt-0002"])).evidence == ("evt-0002",)


# ------------------------------------------------------------- guard coverage
class ThreadIndexer(_TestAgent):
    """Indexes 'the project' from a worker thread, as a memory library might."""

    kind = "threadindexer"

    def __init__(self, name, root, leaks):
        super().__init__(name)
        self.root, self.leaks, self.outcomes = root, leaks, {}

    def setup(self, context):
        super().setup(context)

        def work():
            try:
                for dirpath, _, files in os.walk(self.root):
                    for f in files:
                        try:
                            if MINI_CANARY in open(os.path.join(dirpath, f), errors="replace").read():
                                self.leaks.append(os.path.join(dirpath, f))
                        except PermissionError:
                            pass
                (Path(context.state_dir) / "index.txt").write_text("own state is writable from threads")
                self.outcomes["state_write"] = "ok"
            except Exception as exc:  # noqa: BLE001
                self.outcomes["error"] = repr(exc)

        t = threading.Thread(target=work)
        t.start()
        t.join()

    def on_event(self, event, tools):
        return AgentResponse()


def test_guard_covers_agent_threads(mini_scenario, runs_dir):
    leaks: list[str] = []
    agent = ThreadIndexer("t", mini_scenario.base_dir, leaks)
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert leaks == []
    assert agent.outcomes == {"state_write": "ok"}
    setup = next(r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "agent_setup")
    assert setup["guard_violations"]  # the walk into world/ and scenarios/ was refused


def test_prior_runs_in_the_repository_are_protected(mini_scenario, tmp_path):
    prior = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=mini_scenario.base_dir / "runs", **NO_HYGIENE))
    assert prior.status == "completed"

    class PriorReader(_TestAgent):
        kind = "prior"
        outcome = None

        def on_event(self, event, tools):
            if event.seq == 1:
                try:
                    (prior.run_dir / "scores.json").read_text()
                    PriorReader.outcome = "read"
                except PermissionError:
                    PriorReader.outcome = "denied"
            return AgentResponse()

    run(mini_scenario, [PriorReader("p")], RunConfig(runs_dir=tmp_path / "elsewhere", **NO_HYGIENE))
    assert PriorReader.outcome == "denied"


class HomeCacheAgent(_TestAgent):
    """Persists memory under ~/.cache, a common library default."""

    kind = "homecache"
    seen_before: list[int] = []

    def setup(self, context):
        super().setup(context)
        cache = Path.home() / ".cache" / "ragmem"
        cache.mkdir(parents=True, exist_ok=True)
        db = cache / "events.txt"
        HomeCacheAgent.seen_before.append(len(db.read_text().splitlines()) if db.exists() else 0)
        self.db = db

    def on_event(self, event, tools):
        with open(self.db, "a") as fh:
            fh.write(event.event_id + "\n")
        try:
            Path("/tmp/tab-escape-attempt.txt").write_text("x")
        except PermissionError:
            pass
        return AgentResponse()


def test_memory_cannot_persist_outside_the_run(mini_scenario, runs_dir):
    HomeCacheAgent.seen_before = []
    first = run(mini_scenario, [HomeCacheAgent("h")], RunConfig(runs_dir=runs_dir / "1", **NO_HYGIENE))
    run(mini_scenario, [HomeCacheAgent("h")], RunConfig(runs_dir=runs_dir / "2", **NO_HYGIENE))
    assert HomeCacheAgent.seen_before == [0, 0]  # no lookahead from a previous run
    assert not Path("/tmp/tab-escape-attempt.txt").exists()
    kept = first.run_dir / "final_state" / "h" / "state" / ".home" / ".cache" / "ragmem" / "events.txt"
    assert kept.read_text().split() == ["evt-0001", "evt-0002", "evt-0003"]  # preserved with the run


def _child_read(path, queue):
    try:
        queue.put(open(path).read()[:20])
    except Exception as exc:  # noqa: BLE001
        queue.put(repr(exc))


class ProcessAndFdAgent(_TestAgent):
    kind = "procfd"
    outcomes: dict[str, str] = {}

    def __init__(self, name, gt_dir, base_dir):
        super().__init__(name)
        self.gt_dir, self.base_dir = gt_dir, base_dir

    def on_event(self, event, tools):
        if event.seq != 1:
            return AgentResponse()
        for method in ("spawn", "forkserver", "fork"):
            try:
                ctx = multiprocessing.get_context(method)
                q = ctx.Queue()
                p = ctx.Process(target=_child_read, args=(str(self.gt_dir / "labels.json"), q))
                p.start()
                p.join(10)
                ProcessAndFdAgent.outcomes[method] = "started"
            except PermissionError:
                ProcessAndFdAgent.outcomes[method] = "denied"
        found = []
        try:
            for root, _, files, _ in os.fwalk(self.base_dir):
                found += [f for f in files if f == "labels.json"]
        except PermissionError:
            pass
        ProcessAndFdAgent.outcomes["fwalk_found"] = str(found)
        return AgentResponse()


def test_guard_blocks_multiprocessing_and_fd_relative_walks(mini_scenario, runs_dir):
    ProcessAndFdAgent.outcomes = {}
    agent = ProcessAndFdAgent("pf", mini_scenario.ground_truth_dir, mini_scenario.base_dir)
    run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert ProcessAndFdAgent.outcomes == {
        "spawn": "denied", "forkserver": "denied", "fork": "denied", "fwalk_found": "[]"}


# ----------------------------------------------------------- robustness
class DirectoryMaker(_TestAgent):
    kind = "dirmaker"

    def on_event(self, event, tools):
        if event.seq == 1:
            tools.write_file("VENDOR.md/sneaky.txt", "the world will write VENDOR.md next")
        return AgentResponse()


def test_world_writes_clear_agent_made_obstructions(mini_scenario, runs_dir):
    result = run(mini_scenario, [DirectoryMaker("d")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert result.status == "completed"
    ev2 = read_jsonl(result.run_dir / "events.jsonl")[1]
    assert ev2["conflicts"]["d"][0]["reason"] == "obstructed"
    assert (result.run_dir / "final_state" / "d" / "workspace" / "VENDOR.md").is_file()


def test_runs_dir_containing_the_temp_dir_is_rejected(mini_scenario):
    with pytest.raises(ValueError, match="temp directory"):
        run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=Path(tempfile.gettempdir()).parent))


def test_step_budget_must_be_positive():
    for bad in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            StepBudget(max_tool_calls_per_event=bad)  # type: ignore[arg-type]


def test_evaluator_temp_storage_is_not_leaked_on_early_failure(mini_scenario, tmp_path, monkeypatch):
    before = {p.name for p in Path(tempfile.gettempdir()).glob("tab-eval-snapshots-*")}
    blocker = tmp_path / "runs-is-a-file"
    blocker.write_text("not a directory")
    with pytest.raises(OSError):
        run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=blocker, **NO_HYGIENE))
    after = {p.name for p in Path(tempfile.gettempdir()).glob("tab-eval-snapshots-*")}
    assert after == before


def test_tool_names_match_the_toolbox_surface():
    from harness.tools import TOOL_NAMES, ToolBox

    public = sorted(n for n in vars(ToolBox) if not n.startswith("_") and callable(getattr(ToolBox, n)) and n != "close")
    assert sorted(TOOL_NAMES) == public


# ------------------------------------------- guard: every hook, every process API
@pytest.mark.parametrize("hook,record", [("setup", "agent_setup"), ("on_start", "agent_start"),
                                         ("on_event", "agent_response"), ("teardown", "agent_teardown")])
def test_guard_applies_in_every_agent_hook(mini_scenario, runs_dir, hook, record):
    import subprocess

    labels = mini_scenario.ground_truth_dir / "labels.json"
    world = mini_scenario.base_dir / "world"
    outcomes: dict[str, str] = {}

    class Prober(_TestAgent):
        kind = "prober"

        def _probe(self):
            for label, fn in (("open", lambda: open(labels).read()), ("listdir", lambda: os.listdir(world)),
                              ("subprocess", lambda: subprocess.run(["true"], check=False))):
                try:
                    fn()
                    outcomes[label] = "allowed"
                except PermissionError:
                    outcomes[label] = "denied"

        def setup(self, context):
            super().setup(context)
            if hook == "setup":
                self._probe()

        def on_start(self, tools):
            if hook == "on_start":
                self._probe()

        def on_event(self, event, tools):
            if hook == "on_event" and event.seq == 1:
                self._probe()
            return AgentResponse()

        def teardown(self):
            if hook == "teardown":
                self._probe()

    result = run(mini_scenario, [Prober("p")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert outcomes == {"open": "denied", "listdir": "denied", "subprocess": "denied"}
    rec = next(r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == record)
    assert len(rec["guard_violations"]) == 3


def test_guard_blocks_every_process_creation_api(mini_scenario, runs_dir):
    import pty

    outcomes: dict[str, str] = {}

    def fork_and_exit():
        pid = os.fork()
        if pid == 0:  # only reached if the guard failed; never let the child run pytest
            os._exit(0)
        os.waitpid(pid, 0)

    class Spawner(_TestAgent):
        kind = "spawner"

        def on_event(self, event, tools):
            if event.seq == 1:
                for label, fn in (
                    ("os.system", lambda: os.system("true")),
                    ("os.posix_spawn", lambda: os.waitpid(os.posix_spawn("/bin/true", ["true"], dict(os.environ)), 0)),
                    ("os.fork", fork_and_exit),
                    ("os.spawnv", lambda: os.spawnv(os.P_WAIT, "/bin/true", ["true"])),
                    ("pty.spawn", lambda: pty.spawn(["true"])),
                ):
                    try:
                        fn()
                        outcomes[label] = "allowed"
                    except PermissionError:
                        outcomes[label] = "denied"
            return AgentResponse()

    run(mini_scenario, [Spawner("s")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert set(outcomes.values()) == {"denied"}, outcomes
    from harness import guard

    assert {"os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "os.system", "subprocess.Popen"} <= guard._PROCESS_EVENTS


def test_agents_cannot_touch_each_others_private_state(mini_scenario, runs_dir):
    shared: dict[str, Path] = {}
    outcomes: dict[str, str] = {}

    class Victim(_TestAgent):
        kind = "victim"

        def setup(self, context):
            super().setup(context)
            (context.state_dir / "secret-notes.txt").write_text("private memory")
            shared["victim_state"] = context.state_dir

        def on_event(self, event, tools):
            return AgentResponse()

    class Snoop(_TestAgent):
        kind = "snoop"

        def on_event(self, event, tools):
            if event.seq == 1:
                target = shared["victim_state"]
                for label, fn in (("read", lambda: (target / "secret-notes.txt").read_text()),
                                  ("list", lambda: os.listdir(target)),
                                  ("write", lambda: (target / "planted.txt").write_text("x"))):
                    try:
                        fn()
                        outcomes[label] = "allowed"
                    except PermissionError:
                        outcomes[label] = "denied"
            return AgentResponse()

    result = run(mini_scenario, [Snoop("snoop"), Victim("victim")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert outcomes == {"read": "denied", "list": "denied", "write": "denied"}
    rec = next(r for r in read_jsonl(result.run_dir / "trace.jsonl")
               if r["type"] == "agent_response" and r["agent"] == "snoop" and r["seq"] == 1)
    assert len(rec["guard_violations"]) == 3


# ------------------------------------------------------- replay & delivery scope
def test_replay_detects_tampered_trace_only_fields(mini_scenario, runs_dir):
    from harness.replay import compare_runs
    from harness.trace import FINGERPRINT_FILES

    original = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    path = original.run_dir / "trace.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    for rec in records:
        if rec["type"] == "step_complete":
            rec["workspace_tree"] = "0" * 64
            break
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    replayed, report = replay_run(original.run_dir)
    assert not report["match"]
    assert [m["file"] for m in report["mismatches"]] == ["trace.jsonl"]
    assert {m["file"] for m in compare_runs(replayed.run_dir, replayed.run_dir)} == set()
    assert FINGERPRINT_FILES == ("events.jsonl", "actions.jsonl", "trace.jsonl", "evaluation.jsonl", "scores.json")


def test_agents_receive_the_contestant_view_object(mini_scenario, runs_dir):
    import dataclasses

    from harness.agent import AgentEvent

    received = []

    class Capture(_TestAgent):
        kind = "capture"

        def on_event(self, event, tools):
            received.append(event)
            return AgentResponse()

    run(mini_scenario, [Capture("c")], RunConfig(runs_dir=runs_dir, **NO_HYGIENE))
    assert len(received) == 3
    for ev in received:
        assert type(ev) is AgentEvent
        assert set(vars(ev)) == {f.name for f in dataclasses.fields(AgentEvent)}
        assert not hasattr(ev, "world_changes")
