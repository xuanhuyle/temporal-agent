"""Contestant process boundary (protocol amendment A4): ``harness.process`` and ``harness.worker``.

Drives ``ProcessAgent`` directly with a real ``ToolBox`` over a temporary
workspace, using the test-only contestants in ``tests/contestant_pkgs``.
Escape attempts are made from inside the contestant process and reported
back through note actions, so these tests check the boundary as a contestant
would experience it.
"""

from __future__ import annotations

import gc
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import harness.process as process
from harness import guard
from harness.agent import (
    AgentContext,
    AgentEvent,
    AgentResponse,
    ChangedPath,
    ModelSettings,
    NoteAction,
    ReopenAction,
    StepBudget,
    Usage,
)
from harness.canonical import tree_hash
from harness.errors import BudgetExceeded
from harness.llm import EmbeddingResponse, ModelRequest, ModelResponse
from harness.process import (
    BUNDLE_HARNESS_MODULES,
    ContestantCrashed,
    ContestantError,
    ContestantProtocolError,
    InvalidContestantResponse,
    ProcessAgent,
    StepTimeout,
    build_bundle,
)
from harness.tools import ToolBox
from harness.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
PKG = Path(__file__).resolve().parent / "contestant_pkgs" / "tab_test_contestants"
ENTRY = "tab_test_contestants.scripted:ScriptedAgent"


# -------------------------------------------------------------------- helpers
class FakeModel:
    """A minimal harness ModelService (deterministic)."""

    def estimate_input_tokens(self, request: ModelRequest) -> int:
        return 10

    def complete(self, request: ModelRequest, *, max_output_tokens: int | None, timeout_s: float | None):
        text = "echo:" + request.messages[-1].content
        response = ModelResponse(text=text, stop_reason="end_turn", model="fake-test", input_tokens=10, output_tokens=3)
        return response, {"input_tokens": 10, "output_tokens": 3, "cost_usd": 0.0}

    def estimate_embedding_tokens(self, texts: list[str]) -> int:
        return len(texts)

    def embed(self, texts: list[str], purpose: str, *, timeout_s: float | None):
        vectors = tuple((float(len(t)), 1.0) for t in texts)
        return EmbeddingResponse(vectors=vectors, model="fake-embed", input_tokens=len(texts)), {
            "input_tokens": len(texts),
            "cost_usd": 0.0,
        }


@dataclass
class Lane:
    root: Path
    ctx: AgentContext
    workspace: Workspace
    records: list[dict[str, Any]]

    def tools(self, budget: StepBudget | None = None, model: Any = None) -> ToolBox:
        return ToolBox(self.workspace, budget or self.ctx.budget, self.records.append, model=model)


def make_lane(root: Path, budget: StepBudget | None = None, name: str = "probe") -> Lane:
    state, ws = root / "state", root / "workspace"
    state.mkdir(parents=True)
    ws.mkdir()
    (ws / "README.md").write_text("# Tasklane\n", encoding="utf-8")
    ctx = AgentContext(
        agent_name=name,
        seed=0,
        state_dir=state,
        budget=budget or StepBudget(),
        model=ModelSettings(),
        instructions="Maintain the repository.",
        instructions_version="test/1",
    )
    return Lane(root=root, ctx=ctx, workspace=Workspace(ws), records=[])


def make_agent(name: str = "probe", entry: str = ENTRY, config: dict | None = None, packages: Any = None) -> ProcessAgent:
    return ProcessAgent(name, kind="scripted", entry=entry, config=config or {}, packages=packages or [PKG])


def ev(seq: int, subject: str) -> AgentEvent:
    return AgentEvent(
        schema_version="tab.event/1",
        event_id=f"evt-{seq:04d}",
        seq=seq,
        timestamp="2026-01-02T09:00:00Z",
        channel="chat",
        author="Sam (Platform)",
        subject=subject,
        body="",
        changed_paths=(ChangedPath(op="write_file", path="README.md"),),
    )


def note(resp: AgentResponse, index: int = -1) -> dict[str, Any]:
    texts = [a.text for a in resp.actions if isinstance(a, NoteAction)]
    return json.loads(texts[index])


def gone(pid: int) -> bool:
    """The process has been reaped and its process group is empty."""
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        pass
    try:
        os.killpg(pid, 0)
        return False
    except ProcessLookupError:
        return True


@pytest.fixture(scope="module")
def shared(tmp_path_factory: pytest.TempPathFactory):
    """One contestant process reused by the tests that do not kill it."""
    lane = make_lane(tmp_path_factory.mktemp("shared") / "lane")
    agent = make_agent("shared")
    agent.setup(lane.ctx)
    agent.on_start(lane.tools())
    assert agent.drain_notices() == [{"event": "spawned", "restart_count": 0}]
    yield agent, lane
    agent.teardown()


# --------------------------------------------------------------------- bundle
def _listing(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_bundle_holds_exactly_the_contestant_side_code_read_only(tmp_path: Path) -> None:
    dest = tmp_path / "bundle"
    sha = build_bundle(dest, [PKG])
    expected_pkg = sorted(f"tab_test_contestants/{p.name}" for p in PKG.glob("*.py"))
    assert _listing(dest) == sorted([f"harness/{m}.py" for m in BUNDLE_HARNESS_MODULES] + expected_pkg)
    assert sorted(p.name for p in dest.iterdir()) == ["harness", "tab_test_contestants"]
    for forbidden in ("runner", "scenario", "events", "world", "replay", "cli", "guard", "tools", "workspace",
                      "history", "commands", "model", "process", "canonical", "trace", "instructions"):
        assert not (dest / "harness" / f"{forbidden}.py").exists()
        assert not (dest / "harness" / forbidden).exists()
    for p in [dest, *dest.rglob("*")]:
        assert p.stat().st_mode & 0o222 == 0, p
    assert sha == tree_hash(dest)
    # Byte-identical copies of the harness sources.
    for m in BUNDLE_HARNESS_MODULES:
        assert (dest / "harness" / f"{m}.py").read_bytes() == (SRC_ROOT / "harness" / f"{m}.py").read_bytes()


def test_bundle_skips_caches_and_its_hash_tracks_content(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "tab_test_contestants"
    shutil.copytree(PKG, pkg, ignore=shutil.ignore_patterns("__pycache__"))
    (pkg / "__pycache__").mkdir()
    (pkg / "__pycache__" / "scripted.cpython-311.pyc").write_bytes(b"\0junk")
    (pkg / "stray.pyc").write_bytes(b"\0junk")
    (pkg / "link.py").symlink_to(SRC_ROOT / "harness" / "runner.py")  # must not smuggle benchmark code in
    a = build_bundle(tmp_path / "a", [pkg])
    b = build_bundle(tmp_path / "b", [PKG])
    assert a == b
    assert not any("__pycache__" in p or p.endswith(".pyc") or p.endswith("link.py") for p in _listing(tmp_path / "a"))
    (pkg / "scripted.py").write_text((pkg / "scripted.py").read_text() + "\n# changed\n")
    assert build_bundle(tmp_path / "c", [pkg]) != a
    with pytest.raises(FileExistsError):
        build_bundle(tmp_path / "a", [PKG])


def test_bundle_and_agent_reject_benchmark_packages_and_bad_entries(tmp_path: Path) -> None:
    for bad in (["harness"], ["evaluation"], [SRC_ROOT / "harness"], [SRC_ROOT / "evaluation"], ["no_such_pkg"],
                [PKG, PKG], ["../src"], [tmp_path / "not-a-package-name"]):
        with pytest.raises(ValueError):
            build_bundle(tmp_path / "x", bad)
    with pytest.raises(TypeError):
        build_bundle(tmp_path / "y", "baseline")  # a bare string is not a sequence of packages
    for entry in ("harness.runner:Runner", "evaluation.scorer:X", "tab_test_contestants.scripted",
                  "tab_test_contestants/scripted:X", "os:system"):
        with pytest.raises(ValueError):
            make_agent(entry=entry)
    with pytest.raises(TypeError):
        ProcessAgent("x", kind="k", entry=ENTRY, config=None, packages=[PKG])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        make_agent(config={"not json": object()})


# ------------------------------------------------------------------- describe
def test_describe_works_before_setup_is_stable_and_leaves_nothing(tmp_path: Path, monkeypatch) -> None:
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(scratch))
    first = make_agent(config={"k": 7})
    d1 = first.describe()
    d2 = make_agent(config={"k": 7}).describe()
    assert d1 == d2
    assert d1 == {
        "kind": "scripted",
        "role": "contestant",
        "config": {"k": 7, "reported_by": "child"},  # as reported by the contestant's describe()
        "isolation": "process",
        "entry": ENTRY,
        "bundle_sha256": build_bundle(tmp_path / "ref", [PKG]),
    }
    d1["config"]["k"] = "mutated"
    assert first.describe()["config"]["k"] == 7  # cached and not aliased
    assert list(scratch.iterdir()) == []  # the short-lived worker's directory is removed
    assert first.pid is None and first.drain_notices() == []


# ------------------------------------------------------------- tool round trip
def test_tools_round_trip_through_the_real_toolbox(shared) -> None:
    agent, lane = shared
    lane.records.clear()
    resp = agent.on_event(ev(1, "tools"), lane.tools())
    assert isinstance(resp, AgentResponse)
    reopen = resp.actions[0]
    assert isinstance(reopen, ReopenAction)
    assert reopen.target == "ADR-0001" and reopen.evidence == ("evt-0001",)
    assert reopen.historical_state is not None and reopen.historical_state.known_then == ("seed",)
    assert resp.usage == Usage(model_calls=1, model_input_tokens=5)
    out = note(resp)
    assert out["start_files"] == ["README.md"]  # on_start ran in the child with tools
    assert out["files"] == ["README.md"]
    assert out["readme"] == "# Tasklane\n"
    assert out["via_call"] == "hello from the contestant process\n"
    assert out["search"] == "notes/x.md"
    assert out["traversal"][0] == "AccessDenied" and "traversal" in out["traversal"][1]
    assert out["wrong_type"] == ["ToolError", "read_file: argument path must be a UTF-8 string"]
    assert "unexpected argument 'pathx'" in out["bad_kwarg"]
    assert out["unknown_tool"] == "unknown tool 'no_such_tool'"
    assert out["history"] == ["ToolError", "history is not available in this run"]
    # The harness ToolBox executed and recorded every call; the workspace changed on the harness side.
    calls = [(r["tool"], r["status"]) for r in lane.records]
    assert calls == [
        ("list_files", "ok"),
        ("read_file", "ok"),
        ("write_file", "ok"),
        ("read_file", "ok"),
        ("search", "ok"),
        ("read_file", "denied"),
        ("read_file", "error"),
        ("history", "error"),
    ]
    assert lane.records[6]["args"] == {"path": {"unrecordable_type": "set"}}
    assert (lane.workspace.root / "notes" / "x.md").read_text() == "hello from the contestant process\n"
    assert agent.last_violations == []


def test_model_and_embedding_responses_cross_the_boundary(shared) -> None:
    agent, lane = shared
    lane.records.clear()
    tools = lane.tools(model=FakeModel())
    out = note(agent.on_event(ev(2, "model"), tools))
    assert out == {
        "types": ["ModelResponse", "ModelResponse", "EmbeddingResponse"],
        "texts": ["echo:hi", "echo:dict form"],
        "model": "fake-test",
        "vectors": [[2.0, 1.0], [1.0, 1.0]],
    }
    assert [r["tool"] for r in lane.records] == ["model_complete", "model_complete", "embed"]
    assert all("meter" in r for r in lane.records)
    assert lane.records[0]["args"]["request"]["purpose"] == "loop"
    assert tools.meter()["model_calls"] == 2 and tools.meter()["embedding_calls"] == 1


def test_budget_exceeded_propagates_as_itself(shared) -> None:
    agent, lane = shared
    lane.records.clear()
    tools = lane.tools(budget=StepBudget(max_tool_calls_per_event=3))
    pid = agent.pid
    with pytest.raises(BudgetExceeded, match="tool-call budget of 3"):
        agent.on_event(ev(3, "budget"), tools)
    assert tools.exhausted
    assert [r["status"] for r in lane.records] == ["ok", "ok", "ok", "budget_exceeded"]
    assert agent.pid == pid and agent.drain_notices() == []  # not a crash: the process carries on


def test_caught_budget_exceeded_still_exhausts_the_step(shared) -> None:
    agent, lane = shared
    tools = lane.tools(budget=StepBudget(max_tool_calls_per_event=2))
    out = note(agent.on_event(ev(4, "budget-caught"), tools))
    assert out["caught"] == "tool-call budget of 2 per event exhausted"
    assert out["calls"] == 2 and out["exhausted"] is True
    assert out["remaining"]["tool_calls"] == 0
    assert tools.exhausted  # the runner records budget_exceeded from this


def test_budget_queries_do_not_count_as_tool_calls(shared) -> None:
    agent, lane = shared
    tools = lane.tools(budget=StepBudget(max_tool_calls_per_event=5))
    out = note(agent.on_event(ev(5, "budget-info"), tools))
    assert out["before"] == 5 and out["after"] == 4
    assert out["budget"]["tool_calls"] == 4
    assert tools.calls_made == 1


def test_toolbox_is_closed_after_the_call(shared) -> None:
    agent, lane = shared
    agent.on_event(ev(6, "keep-tools"), lane.tools())
    out = note(agent.on_event(ev(7, "use-stale"), lane.tools()))
    assert out["list_files"] == ["ToolBoxClosed", "list_files: this ToolBox belongs to a finished step"]
    assert out["budget_remaining"] == "ToolBoxClosed"


# ----------------------------------------------------------------- exceptions
def test_child_exceptions_keep_type_name_message_and_traceback(shared) -> None:
    agent, lane = shared
    pid = agent.pid
    with pytest.raises(ContestantError) as info:
        agent.on_event(ev(8, "raise"), lane.tools())
    exc = info.value
    assert type(exc).__name__ == "ValueError" and str(exc) == "boom 42"
    assert not isinstance(exc, ValueError)  # a stand-in, not the harness's own class
    assert "ValueError: boom 42" in exc.child_traceback and "do_raise" in exc.child_traceback
    with pytest.raises(ContestantError) as info:
        agent.on_event(ev(9, "custom-raise"), lane.tools())
    assert type(info.value).__name__ == "TabCustomError" and str(info.value) == "custom failure"
    with pytest.raises(ContestantError) as info:
        agent.on_event(ev(10, "exit"), lane.tools())
    assert type(info.value).__name__ == "SystemExit" and str(info.value) == "5"
    assert agent.pid == pid and agent.drain_notices() == []


def test_invalid_responses_are_reported_not_crashes(shared) -> None:
    agent, lane = shared
    pid = agent.pid
    with pytest.raises(InvalidContestantResponse, match="on_event must return AgentResponse, got dict") as info:
        agent.on_event(ev(11, "invalid"), lane.tools())
    assert isinstance(info.value, TypeError)
    with pytest.raises(InvalidContestantResponse, match="actions must be a list of Action objects"):
        agent.on_event(ev(12, "bad-actions"), lane.tools())
    assert agent.pid == pid
    assert note(agent.on_event(ev(13, "state"), lane.tools()))["restart_count"] == 0


def test_malformed_return_values_are_invalid_responses() -> None:
    parse = process._parse_response
    for bad in (None, [], {"actions": "x", "usage": {}}, {"actions": [{"type": "launch"}], "usage": {}},
                {"actions": [], "usage": {"model_calls": -1}}, {"actions": [], "usage": {"bogus": 1}},
                {"actions": [{"type": "reopen"}], "usage": {}}):
        with pytest.raises(InvalidContestantResponse):
            parse(bad)


# ---------------------------------------------------------- timeout and crash
def test_timeout_kills_the_process_and_restart_resumes_from_state(tmp_path: Path) -> None:
    lane = make_lane(tmp_path / "lane", budget=StepBudget(wall_clock_s_per_event=1))
    agent = make_agent()
    try:
        agent.setup(lane.ctx)
        pid = agent.pid
        assert pid is not None
        started = time.monotonic()
        with pytest.raises(StepTimeout, match="wall-clock budget of 1s"):
            agent.on_event(ev(1, "sleep"), lane.tools())
        assert time.monotonic() - started < 10
        assert agent.pid is None and gone(pid)
        assert agent.drain_notices() == [
            {"event": "spawned", "restart_count": 0},
            {"event": "timeout", "method": "on_event", "limit_s": 1.0},
        ]
        out = note(agent.on_event(ev(2, "state"), lane.tools()))
        assert out["restart_count"] == 1 and out["setups"] == [1]
        assert out["ckpt"] == "before-timeout"  # written to the state dir before the kill
        assert out["setup_log"] == "0\n1\n"
        assert out["pid"] != pid
        assert agent.context is not None and agent.context.restart_count == 1
        assert agent.drain_notices() == [
            {"event": "restarted", "restart_count": 1},
            {"event": "spawned", "restart_count": 1},
        ]
    finally:
        agent.teardown()
    assert agent.drain_notices() == [{"event": "exited", "exit_code": 0}]


def test_crash_is_reported_with_exit_code_and_restarted(tmp_path: Path) -> None:
    lane = make_lane(tmp_path / "lane")
    agent = make_agent()
    try:
        agent.setup(lane.ctx)
        pid = agent.pid
        with pytest.raises(ContestantCrashed) as info:
            agent.on_event(ev(1, "crash"), lane.tools())
        assert info.value.exit_code == 3
        assert not isinstance(info.value, ContestantProtocolError)
        assert gone(pid)
        assert agent.drain_notices()[-1] == {"event": "crashed", "method": "on_event", "exit_code": 3}
        out = note(agent.on_event(ev(2, "state"), lane.tools()))
        assert out["restart_count"] == 1 and out["crash"] == "about-to-crash"
        with pytest.raises(ContestantCrashed):
            agent.on_event(ev(3, "crash"), lane.tools())
        out = note(agent.on_event(ev(4, "state"), lane.tools()))
        assert out["restart_count"] == 2 and out["setup_log"] == "0\n1\n2\n"
    finally:
        agent.teardown()
    assert agent.log_dir is not None
    assert (agent.log_dir / "stdout.log").read_text().count("crash-marker") == 2  # appended across restarts


def test_forged_wire_messages_kill_the_process(tmp_path: Path) -> None:
    lane = make_lane(tmp_path / "lane")
    agent = make_agent()
    try:
        agent.setup(lane.ctx)
        pid = agent.pid
        with pytest.raises(ContestantProtocolError):
            agent.on_event(ev(1, "forge"), lane.tools())
        assert gone(pid)
        assert agent.drain_notices()[-1] == {"event": "protocol_error", "method": "on_event"}
        assert note(agent.on_event(ev(2, "state"), lane.tools()))["restart_count"] == 1
    finally:
        agent.teardown()


def test_teardown_reaps_the_process_and_logs_are_captured(tmp_path: Path) -> None:
    lane = make_lane(tmp_path / "lane")
    agent = make_agent()
    agent.setup(lane.ctx)
    out = note(agent.on_event(ev(7, "print"), lane.tools()))
    pid = out["pid"]
    assert pid == agent.pid
    agent.teardown()
    assert agent.pid is None and gone(pid)
    assert (lane.ctx.state_dir / "teardown.txt").read_text() == "done"
    assert agent.log_dir == lane.root / "logs"
    stdout = (agent.log_dir / "stdout.log").read_text()
    assert "stdout-marker-7" in stdout and "teardown-marker" in stdout
    assert "stderr-marker-7" in (agent.log_dir / "stderr.log").read_text()
    agent.teardown()  # idempotent
    agent.close()
    with pytest.raises(RuntimeError):
        agent.on_event(ev(8, "state"), lane.tools())
    # After the process is gone the bundle can be removed by ordinary cleanup.
    shutil.rmtree(lane.root / "bundle")


def test_teardown_has_a_wall_clock_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(process, "CONTROL_TIMEOUT_S", 1.0)
    lane = make_lane(tmp_path / "lane")
    agent = make_agent(entry="tab_test_contestants.scripted:HangsInTeardown")
    agent.setup(lane.ctx)
    pid = agent.pid
    with pytest.raises(StepTimeout):
        agent.teardown()
    assert agent.pid is None and gone(pid)


@pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="needs /proc to count descriptors")
def test_lifecycle_leaks_no_file_descriptors(tmp_path: Path) -> None:
    def open_fds() -> int:
        return len(os.listdir("/proc/self/fd"))

    lane = make_lane(tmp_path / "lane")
    agent = make_agent()
    agent.describe()
    before = open_fds()
    agent.setup(lane.ctx)
    with pytest.raises(ContestantCrashed):
        agent.on_event(ev(1, "crash"), lane.tools())
    agent.on_event(ev(2, "state"), lane.tools())
    agent.teardown()
    assert open_fds() == before


def test_garbage_collected_agent_leaves_no_process(tmp_path: Path) -> None:
    lane = make_lane(tmp_path / "lane")
    agent = make_agent()
    agent.setup(lane.ctx)
    pid = agent.pid
    del agent
    gc.collect()
    assert gone(pid)


def test_startup_and_setup_failures_leave_no_process(tmp_path: Path) -> None:
    cases = [
        ("tab_test_contestants.broken:RaisesInInit", "RuntimeError", "cannot start"),
        ("tab_test_contestants.broken:NotAnAgent", "TypeError", "did not construct a harness.agent.Agent"),
        ("tab_test_contestants.broken:FailsInSetup", "OSError", "state directory unusable"),
        ("tab_test_contestants.missing:Agent", "ModuleNotFoundError", "tab_test_contestants.missing"),
    ]
    for i, (entry, type_name, message) in enumerate(cases):
        lane = make_lane(tmp_path / f"lane{i}")
        agent = make_agent(entry=entry)
        with pytest.raises(ContestantError) as info:
            agent.setup(lane.ctx)
        assert type(info.value).__name__ == type_name and message in str(info.value)
        assert agent.pid is None
        agent.teardown()
    with pytest.raises(ContestantError, match="cannot start"):
        make_agent(entry="tab_test_contestants.broken:RaisesInInit").describe()
    with pytest.raises(ContestantError, match="cannot be sent to the harness") as info:
        make_agent(entry="tab_test_contestants.broken:UnsendableDescribe").describe()
    assert type(info.value).__name__ == "TypeError"
    with pytest.raises(InvalidContestantResponse, match=r"describe\(\) must return a dict"):
        make_agent(entry="tab_test_contestants.broken:ListDescribe").describe()


def test_calls_require_setup(tmp_path: Path) -> None:
    lane = make_lane(tmp_path / "lane")
    agent = make_agent()
    with pytest.raises(RuntimeError, match="setup"):
        agent.on_event(ev(1, "state"), lane.tools())
    agent.setup(lane.ctx)
    try:
        with pytest.raises(RuntimeError, match="already"):
            agent.setup(lane.ctx)
    finally:
        agent.teardown()


# ------------------------------------------------------------------ isolation
def test_escape_attempts_from_inside_the_contestant_are_refused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("TAB_PROBE_SECRET", "secret")
    monkeypatch.setenv("PYTHONPATH", str(SRC_ROOT))
    outside = tmp_path / "outside.txt"
    lane = make_lane(tmp_path / "lane")
    agent = make_agent(config={"repo_root": str(REPO_ROOT), "outside_path": str(outside)})
    agent.setup(lane.ctx)
    try:
        out = note(agent.on_event(ev(1, "probe"), lane.tools()))
        refused = list(agent.last_violations)  # the refusals reported for this call
    finally:
        agent.teardown()
    results = out["results"]
    for module in ("harness.runner", "harness.scenario", "harness.tools", "harness.guard", "harness.process",
                   "evaluation"):
        assert results[f"import {module}"] == "ModuleNotFoundError", module
    for probe in ("read labels", "list repo", "read environ", "write outside", "socket", "subprocess", "ctypes",
                  "signal parent"):
        assert results[probe] == "TripwireViolation", (probe, results[probe])
    assert results["smuggle repo onto sys.path"] == "ModuleNotFoundError"
    assert results["write state"] == "allowed" and results["read bundle"] == "allowed"
    assert not outside.exists()
    assert (lane.ctx.state_dir / "probe-ok.txt").read_text() == "ok"
    # Environment, argv and sys.path carry no credentials, proxies or repository paths.
    assert out["secrets"] == []
    assert "PYTHONPATH" not in out["env_keys"]
    assert out["repo_in_sys_path"] == [] and out["repo_in_argv"] == [] and out["repo_in_environ"] == []
    state = str(lane.ctx.state_dir.resolve())
    assert out["cwd"] == state
    assert out["home"].startswith(state) and out["tmpdir"].startswith(state)
    assert out["pythonhashseed"] == "0" and out["tz"] == "UTC" and out["path"] == "/usr/bin:/bin"
    assert out["argv"] == ["tab-worker"]
    # Every refusal is reported to the harness for the call that caused it.
    for prefix in ("open: read outside", "os.listdir: read outside", "open: write outside",
                   "socket.__new__: network access", "subprocess.Popen: starting processes", "ctypes.dlopen: ctypes",
                   "os.kill: signalling other processes"):
        assert any(v.startswith(prefix) for v in refused), (prefix, refused)
    assert sum(v.startswith("open: read outside") for v in refused) == 2  # labels.json and /proc/self/environ
    assert not any(str(REPO_ROOT) in v for v in refused)  # refusal records are path-free


def test_hash_seed_is_fixed_across_processes(shared, tmp_path: Path) -> None:
    agent, lane = shared
    first = note(agent.on_event(ev(20, "hash"), lane.tools()))
    other_lane = make_lane(tmp_path / "lane")
    other = make_agent("other")
    other.setup(other_lane.ctx)
    try:
        second = note(other.on_event(ev(20, "hash"), other_lane.tools()))
    finally:
        other.teardown()
    assert first == second
    assert first["hash_randomization"] == 0


def test_works_inside_a_guarded_agent_call(tmp_path: Path) -> None:
    """The runner calls agents under ``harness.guard``; the proxy's own process work must not trip it."""
    lane = make_lane(tmp_path / "lane")
    agent = make_agent("guarded")
    with guard.armed([REPO_ROOT / "world", lane.root / "workspace"]):
        guard.register_lane("guarded", lane.ctx.state_dir)

        def call(fn):
            with guard.agent_call("guarded", lane.ctx.state_dir, guard.lane_env(lane.ctx.state_dir)) as collected:
                result = fn()
            return result, collected

        description, v0 = call(agent.describe)
        _, v1 = call(lambda: agent.setup(lane.ctx))
        resp, v2 = call(lambda: agent.on_event(ev(1, "state"), lane.tools()))
        _, v3 = call(agent.teardown)
    assert description["isolation"] == "process"
    assert note(resp)["restart_count"] == 0
    assert v0 == v1 == v2 == v3 == []
