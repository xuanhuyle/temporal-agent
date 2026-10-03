"""Integrity hardening: guard tripwire, unforgeable checks, failure preservation, stable outputs."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import MINI_CANARY
from evaluation.checks import evaluate_alternatives
from evaluation.ground_truth import load_ground_truth
from harness.agent import Agent, AgentResponse, NoteAction, ReopenAction
from harness.agents import create_agent
from harness.replay import replay_run
from harness.runner import RunConfig, run
from harness.scenario import ScenarioIntegrityError, load_scenario
from harness.trace import read_jsonl
from scripted_agents import _TestAgent


def _gt(scenario):
    events = scenario.load_events()
    return load_ground_truth(scenario.ground_truth_dir, {e.event_id: e.seq for e in events})


# --------------------------------------------------------------------- guard
class DirectAccessAgent(_TestAgent):
    """Tries to bypass the ToolBox with ordinary Python file and process APIs."""

    kind = "direct"

    def __init__(self, name: str, targets: dict[str, Path]) -> None:
        super().__init__(name)
        self.targets = targets
        self.outcomes: dict[str, str] = {}
        self.cwd: Path | None = None

    def _try(self, label, fn):
        try:
            fn()
            self.outcomes[label] = "allowed"
        except PermissionError:
            self.outcomes[label] = "denied"
        except OSError as exc:
            self.outcomes[label] = f"oserror:{type(exc).__name__}"

    def on_event(self, event, tools):
        if event.seq != 1:
            return AgentResponse()
        self.cwd = Path.cwd()
        t = self.targets
        self._try("open_labels", lambda: open(t["labels"]).read())
        self._try("listdir_world", lambda: os.listdir(t["world"]))
        self.found = []
        self._try("walk_repo", lambda: self.found.extend(t["repo"].rglob("labels.json")))
        self._try("open_payload", lambda: open(t["payload"]).read())
        self._try("open_own_workspace", lambda: open(Path(tools._ws.root) / "app.py").read())
        self._try("write_own_workspace", lambda: (Path(tools._ws.root) / "x.txt").write_text("x"))
        self._try("subprocess", lambda: subprocess.run(["true"], check=False))
        self._try("own_state", lambda: (Path.cwd() / "memory.txt").write_text("ok"))
        return AgentResponse(actions=[NoteAction("probed")])


def test_guard_blocks_direct_access_but_allows_private_state(mini_scenario, runs_dir):
    targets = {
        "labels": mini_scenario.ground_truth_dir / "labels.json",
        "world": mini_scenario.base_dir / "world",
        "repo": mini_scenario.base_dir,
        "payload": mini_scenario.events_dir / "payloads" / "evt-0002" / "VENDOR.md",
    }
    agent = DirectAccessAgent("direct", targets)
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, hygiene=False))
    assert agent.outcomes == {
        "open_labels": "denied",
        "listdir_world": "denied",
        "walk_repo": "allowed",  # pathlib skips denied directories silently ...
        "open_payload": "denied",
        "open_own_workspace": "denied",
        "write_own_workspace": "denied",
        "subprocess": "denied",
        "own_state": "allowed",
    }
    assert agent.found == []  # ... so the walk finds nothing
    assert agent.cwd is not None and agent.cwd.name == "state"
    response = next(r for r in read_jsonl(result.run_dir / "trace.jsonl")
                    if r["type"] == "agent_response" and r["seq"] == 1)
    assert len(response["guard_violations"]) >= 7
    assert (result.run_dir / "final_state" / "direct" / "state" / "memory.txt").read_text() == "ok"
    assert Path.cwd() != agent.cwd  # restored after the call
    assert (mini_scenario.ground_truth_dir / "labels.json").read_text()  # guard disarmed outside agent calls


class BytecodeEscapeAgent(_TestAgent):
    """Tries to keep state in bytecode-cache-shaped paths outside its private state directory."""

    kind = "bytecode-escape"

    def __init__(self, name: str, elsewhere: Path) -> None:
        super().__init__(name)
        self.elsewhere = elsewhere
        self.outcomes: dict[str, str] = {}

    def _try(self, label, fn):
        try:
            fn()
            self.outcomes[label] = "allowed"
        except PermissionError:
            self.outcomes[label] = "denied"

    def on_event(self, event, tools):
        if event.seq != 1:
            return AgentResponse()
        lane = self.context.state_dir.parent
        sibling = Path(f"{lane}/../other/__pycache__")
        self._try("tmp_pycache_file", lambda: (self.elsewhere / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"m"))
        self._try("tmp_pycache_mkdir", lambda: os.makedirs(self.elsewhere / "pkg" / "__pycache__"))
        self._try("tmp_bare_pyc", lambda: (self.elsewhere / "memory.pyc").write_bytes(b"m"))
        self._try("lane_sibling_pyc", lambda: open(f"{sibling}/y.pyc", "wb").close())
        self._try("lane_sibling_mkdir", lambda: os.mkdir(f"{lane}/../other/__pycache__/sub"))
        self._try("lane_pycache_mkdir", lambda: os.mkdir(lane / "__pycache__"))
        self._try("workspace_pycache", lambda: os.mkdir(Path(tools._ws.root) / "__pycache__"))
        self._try("own_state_pycache", lambda: (self.context.state_dir / "__pycache__").mkdir())
        return AgentResponse(actions=[NoteAction("probed")])


def test_guard_refuses_bytecode_cache_writes_outside_armed_roots(mini_scenario, runs_dir, tmp_path, monkeypatch):
    """__pycache__/*.pyc paths are not a way out of the private state directory (in-process agents)."""
    systmp = tmp_path / "systmp"  # lanes are created here, so "<lane>/../other" stays inside tmp_path
    (systmp / "other" / "__pycache__").mkdir(parents=True)
    monkeypatch.setattr(tempfile, "tempdir", str(systmp))
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "__pycache__").mkdir(parents=True)
    agent = BytecodeEscapeAgent("bc", elsewhere)
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, hygiene=False))
    assert agent.outcomes == {
        "tmp_pycache_file": "denied",
        "tmp_pycache_mkdir": "denied",
        "tmp_bare_pyc": "denied",
        "lane_sibling_pyc": "denied",
        "lane_sibling_mkdir": "denied",
        "lane_pycache_mkdir": "denied",
        "workspace_pycache": "denied",
        "own_state_pycache": "allowed",
    }
    assert sorted(p.name for p in elsewhere.rglob("*")) == ["__pycache__"]
    assert sorted(p.relative_to(systmp).as_posix() for p in (systmp / "other").rglob("*")) == ["other/__pycache__"]
    response = next(r for r in read_jsonl(result.run_dir / "trace.jsonl")
                    if r["type"] == "agent_response" and r["seq"] == 1)
    assert len(response["guard_violations"]) == 7, response["guard_violations"]


def test_guard_bytecode_roots_are_fixed_at_arm_time(tmp_path, monkeypatch):
    """The import system may cache bytecode under sys.path directories present when the run was armed
    (the harness imports lazily during agent calls), but not under a directory added to sys.path later."""
    import importlib
    import sys
    import sysconfig

    from harness import guard

    early, late, state = tmp_path / "early", tmp_path / "late", tmp_path / "state"
    for d, mod in ((early, "tab_bc_early_mod"), (late, "tab_bc_late_mod")):
        d.mkdir()
        (d / f"{mod}.py").write_text("VALUE = 7\n")
    state.mkdir()
    monkeypatch.setattr(sys, "path", [str(early), *sys.path])
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    for mod in ("tab_bc_early_mod", "tab_bc_late_mod"):
        monkeypatch.delitem(sys.modules, mod, raising=False)
    with guard.armed([tmp_path / "denied"]) as policy:
        assert os.path.realpath(sysconfig.get_paths()["stdlib"]) in policy.bytecode_roots
        assert str(early.resolve()) in policy.bytecode_roots
        assert os.path.realpath(tempfile.gettempdir()) not in policy.bytecode_roots
        assert "/" not in policy.bytecode_roots
        guard.register_lane("bc", state)
        sys.path.insert(0, str(late))
        importlib.invalidate_caches()
        with guard.agent_call("bc", state, guard.lane_env(state)) as collected:
            assert importlib.import_module("tab_bc_early_mod").VALUE == 7
            assert importlib.import_module("tab_bc_late_mod").VALUE == 7  # import works; caching is refused
            with pytest.raises(guard.GuardViolation):
                open(early / "__pycache__" / ".." / ".." / "late" / "__pycache__" / "forced.pyc", "wb")
            with pytest.raises(guard.GuardViolation):
                open(early / "not_a_cache.pyc", "wb")  # under a root, but not in a __pycache__ directory
    assert any(p.suffix == ".pyc" for p in (early / "__pycache__").iterdir())
    assert not (late / "__pycache__").exists() and not (early / "not_a_cache.pyc").exists()
    assert collected and all(v in ("os.mkdir", "open", "os.rename") for v in collected), collected


# ------------------------------------------------------- unforgeable checks
FORGERIES = {
    "root_pytest_shadow": {"pytest.py": "import sys\nsys.exit(0)\n"},
    "conftest_forces_pass": {
        "conftest.py": (
            "import pytest\n"
            "@pytest.hookimpl(hookwrapper=True)\n"
            "def pytest_runtest_makereport(item, call):\n"
            "    outcome = yield\n"
            "    rep = outcome.get_result()\n"
            "    rep.outcome = 'passed'\n"
        )
    },
    "addopts_deselect": {"pyproject.toml": '[tool.pytest.ini_options]\naddopts = "-k nothing"\n'},
    "sitecustomize": {"sitecustomize.py": "import os\nos._exit(0)\n"},
    # Kill the exact-count rule: a skipped hidden test still exits 0.
    "skip_at_import": {"app.py": "import pytest\npytest.skip('nothing to see', allow_module_level=True)\n"},
    "skip_at_runtime": {"app.py": "import pytest\ndef batch_limit():\n    pytest.skip('skipped')\n"},
    "xfail_at_runtime": {"app.py": "import pytest\ndef batch_limit():\n    pytest.xfail('expected')\n"},
    # Kill append-ordering: shadow a stdlib module the hidden test imports but pytest does not.
    "stdlib_shadow": {"colorsys.py": "import app\nONE_THIRD = 1 / 3\napp.batch_limit = lambda: 99\n"},
    "exit_on_import": {"app.py": "import os\nos._exit(0)\n"},
    "json_shadow": {"json.py": "def loads(s):\n    return {'batch_limit': 999}\n"},
}


# root_pytest_shadow, conftest_forces_pass, addopts_deselect and sitecustomize are
# defence in depth: hidden tests live outside the snapshot, so workspace config
# is never discovered even without -c/--noconftest.
@pytest.mark.parametrize("case", sorted(FORGERIES))
def test_remediation_checks_resist_workspace_tampering(mini_scenario, tmp_path, case):
    gt = _gt(mini_scenario)
    alt = gt.reconsiderations[0].remediation.acceptable
    hidden_only = (type(alt[0])(id="hidden", checks=tuple(c for c in alt[0].checks if c["type"] == "hidden_pytest")),)
    snap = tmp_path / "snap"
    from harness.canonical import copy_tree

    copy_tree(mini_scenario.seed_dir, snap)  # unremediated: batch_limit stays 1
    for rel, text in FORGERIES[case].items():
        (snap / rel).parent.mkdir(parents=True, exist_ok=True)
        (snap / rel).write_text(text)
    result = evaluate_alternatives(hidden_only, snap, gt)
    assert result["passed"] is False, result


def test_remediation_checks_pass_for_a_real_fix(mini_scenario, tmp_path):
    gt = _gt(mini_scenario)
    from harness.canonical import copy_tree

    snap = tmp_path / "snap"
    copy_tree(mini_scenario.seed_dir, snap)
    (snap / "config.json").write_text('{"batch_limit": 25}\n')
    result = evaluate_alternatives(gt.reconsiderations[0].remediation.acceptable, snap, gt)
    assert result["passed"] is True
    detail = result["alternatives"][0]["checks"][1]["detail"]
    assert detail["junit"]["passed"] == detail["expected_tests"] == 1
    assert not any(snap.rglob("__pycache__"))  # the snapshot is never written


# ------------------------------------------------------------- filesystem
def test_world_writes_never_go_through_hard_links(mini_scenario, runs_dir, tmp_path, monkeypatch):
    outside = tmp_path / "outside.md"
    outside.write_text("precious")
    from harness import runner as runner_mod

    real_copy = runner_mod.copy_tree

    def copy_and_link(src, dst, **kwargs):
        skipped = real_copy(src, dst, **kwargs)
        if Path(dst).name == "workspace" and "final_state" not in Path(dst).parts:
            os.link(outside, Path(dst) / "README.md")  # event 1 writes README.md
        return skipped

    monkeypatch.setattr(runner_mod, "copy_tree", copy_and_link)
    run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, hygiene=False))
    assert outside.read_text() == "precious"


# ---------------------------------------------------------- toolbox lifecycle
class StashingAgent(_TestAgent):
    kind = "stasher"

    def __init__(self, name="stasher"):
        super().__init__(name)
        self.stashed = None
        self.late_error = None

    def on_event(self, event, tools):
        if event.seq == 1:
            self.stashed = tools
        elif event.seq == 2:
            try:
                self.stashed.write_file("late.txt", "written with an old toolbox")
            except Exception as exc:  # noqa: BLE001
                self.late_error = type(exc).__name__
        return AgentResponse()


def test_toolbox_is_closed_after_its_step(mini_scenario, runs_dir):
    agent = StashingAgent()
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir, hygiene=False))
    assert agent.late_error == "ToolBoxClosed"
    assert not (result.run_dir / "final_state" / "stasher" / "workspace" / "late.txt").exists()


class SwallowingAgent(_TestAgent):
    kind = "swallower"

    def on_event(self, event, tools):
        for _ in range(100):
            try:
                tools.list_files()
            except BaseException:  # noqa: BLE001 - deliberately swallowing everything
                break
        return AgentResponse(actions=[ReopenAction("ADR-0001")] if event.seq == 2 else [])


def test_swallowed_budget_exhaustion_is_still_flagged_and_replayable(mini_scenario, runs_dir):
    result = run(mini_scenario, [SwallowingAgent("swallower")], RunConfig(runs_dir=runs_dir, hygiene=False))
    s = result.scores["agents"]["swallower"]
    assert s["step_status"] == {"budget_exceeded": 3}
    assert s["temporal_governance_recall"]["value"] == 1.0  # returned actions are kept
    _, report = replay_run(result.run_dir)
    assert report["match"], report


# ------------------------------------------------------ failure preservation
def test_failed_run_preserves_state_and_outputs(mini_scenario, runs_dir, monkeypatch):
    from evaluation import scorer
    from scripted_agents import WriterAgent

    real = scorer.Evaluator.observe_step

    def observe(self, agent, seq, actions):
        if seq == 2:
            raise RuntimeError("evaluator bug at step 2")
        return real(self, agent, seq, actions)

    monkeypatch.setattr(scorer.Evaluator, "observe_step", observe)
    with pytest.raises(RuntimeError):
        run(mini_scenario, [WriterAgent("w")], RunConfig(runs_dir=runs_dir, hygiene=False))
    (run_dir,) = list(runs_dir.iterdir())
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["status"] == "failed" and meta["last_completed_seq"] == 1
    assert sorted(p.name for p in (run_dir / "final_state" / "w" / "workspace" / "notes").iterdir()) == ["w-1.md", "w-2.md"]
    assert (run_dir / "final_state" / "w" / "state" / "memory-2.txt").is_file()
    for name in ("trace.jsonl", "events.jsonl", "actions.jsonl", "evaluation.jsonl"):
        read_jsonl(run_dir / name)  # every line parses
    assert (run_dir / "MANIFEST.sha256").is_file()


def test_manifest_lists_every_output(mini_scenario, runs_dir):
    result = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, hygiene=False))
    listing = (result.run_dir / "MANIFEST.sha256").read_text().splitlines()
    listed = {line.split("  ", 1)[1] for line in listing}
    actual = {p.relative_to(result.run_dir).as_posix() for p in result.run_dir.rglob("*") if p.is_file()}
    assert listed == actual - {"MANIFEST.sha256"}


def test_tool_results_and_events_are_stored_as_blobs(mini_scenario, runs_dir):
    from scripted_agents import RecordingAgent

    result = run(mini_scenario, [RecordingAgent()], RunConfig(runs_dir=runs_dir, hygiene=False))
    blobs = result.run_dir / "blobs"
    for rec in read_jsonl(result.run_dir / "trace.jsonl"):
        if rec["type"] == "tool_call" and rec["status"] == "ok":
            assert (blobs / f"{rec['result_sha256']}.json").is_file()
    for rec in read_jsonl(result.run_dir / "events.jsonl"):
        assert json.loads((blobs / f"{rec['delivered_sha256']}.json").read_text()) == rec["delivered"]


def test_out_of_band_mutation_is_detected(mini_scenario, runs_dir, monkeypatch):
    from evaluation import scorer
    from harness import runner as runner_mod

    lanes_seen = []
    real_ws = runner_mod.Workspace

    def capture(root, protected=()):
        ws = real_ws(root, protected)
        lanes_seen.append(ws.root)
        return ws

    monkeypatch.setattr(runner_mod, "Workspace", capture)
    real = scorer.Evaluator.observe_step

    def observe(self, agent, seq, actions):
        if seq == 1:
            (lanes_seen[-1] / "sneaky.txt").write_text("changed outside any tool call")
        return real(self, agent, seq, actions)

    monkeypatch.setattr(scorer.Evaluator, "observe_step", observe)
    result = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, hygiene=False))
    oob = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "out_of_band_mutation"]
    assert [r["seq"] for r in oob] == [2]


def test_scenario_change_during_run_is_an_integrity_failure(mini_scenario, runs_dir, monkeypatch):
    from evaluation import scorer

    real = scorer.Evaluator.observe_step

    def observe(self, agent, seq, actions):
        if seq == 2:
            p = mini_scenario.ground_truth_dir / "hidden_tests" / "test_hidden_mini.py"
            p.write_text(p.read_text() + "\n# tampered\n")
        return real(self, agent, seq, actions)

    monkeypatch.setattr(scorer.Evaluator, "observe_step", observe)
    result = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, hygiene=False))
    assert result.status == "integrity_failed"
    assert json.loads((result.run_dir / "metadata.json").read_text())["fingerprint"] is None


def test_manifest_fields_are_frozen_too(mini_scenario, runs_dir):
    data = json.loads(mini_scenario.manifest_path.read_text())
    data["budgets"]["max_tool_calls_per_event"] = 500
    mini_scenario.manifest_path.write_text(json.dumps(data))
    with pytest.raises(ScenarioIntegrityError, match="manifest"):
        run(load_scenario(mini_scenario.manifest_path), [create_agent("dummy")], RunConfig(runs_dir=runs_dir))


# ------------------------------------------------------------ determinism
class PathErrorAgent(_TestAgent):
    kind = "patherror"

    def on_event(self, event, tools):
        if event.seq == 2:
            raise FileNotFoundError(f"missing cache at {self.context.state_dir / 'cache.db'}")
        return AgentResponse()


def test_errors_are_redacted_and_fingerprints_stable_across_temp_roots(mini_scenario, runs_dir, monkeypatch, tmp_path):
    a = run(mini_scenario, [PathErrorAgent("p")], RunConfig(runs_dir=runs_dir / "a", hygiene=False))
    other_tmp = tmp_path / "other-tmp"
    other_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(other_tmp))
    b = run(mini_scenario, [PathErrorAgent("p")], RunConfig(runs_dir=runs_dir / "b", hygiene=False))
    err = next(r for r in read_jsonl(a.run_dir / "actions.jsonl") if r["seq"] == 2)["error"]
    assert err == "FileNotFoundError: missing cache at <state:p>/cache.db"
    assert a.fingerprint == b.fingerprint
    for name in ("trace.jsonl", "actions.jsonl", "events.jsonl", "evaluation.jsonl", "scores.json"):
        text = (a.run_dir / name).read_text()
        assert str(mini_scenario.base_dir) not in text and tempfile.gettempdir() not in text


def test_dummy_world_trajectory_matches_frozen_world_states(mini_scenario, runs_dir):
    result = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, hygiene=False))
    after = [r["tree_after"] for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "world_event_applied"]
    assert after == mini_scenario.data["world_state_hashes"]


def test_hygiene_reports_workspace_suite(mini_scenario, runs_dir):
    result = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    hygiene = result.scores["agents"]["dummy"]["hygiene"]["workspace_tests_at_end"]
    assert hygiene["passed"] is True and hygiene["detail"]["junit"]["passed"] == 1


def test_canary_never_reaches_contestant_outputs(mini_scenario, runs_dir):
    from scripted_agents import IndexingAgent, RecordingAgent

    result = run(mini_scenario, [IndexingAgent(), RecordingAgent()], RunConfig(runs_dir=runs_dir, hygiene=False))
    for path in result.run_dir.rglob("*"):
        if path.is_file():
            assert MINI_CANARY not in path.read_text(errors="replace"), path


def test_hidden_check_requires_the_expected_number_of_passing_tests(mini_scenario, tmp_path):
    import dataclasses

    from evaluation.checks import run_hidden_pytest
    from harness.canonical import copy_tree

    gt = _gt(mini_scenario)
    snap = tmp_path / "snap"
    copy_tree(mini_scenario.seed_dir, snap)
    (snap / "config.json").write_text('{"batch_limit": 25}\n')
    check = next(c for c in gt.reconsiderations[0].remediation.acceptable[0].checks if c["type"] == "hidden_pytest")
    assert run_hidden_pytest(check, snap, gt)["passed"] is True
    inflated = dataclasses.replace(gt, hidden_test_counts={k: v + 1 for k, v in gt.hidden_test_counts.items()})
    result = run_hidden_pytest(check, snap, inflated)
    assert result["passed"] is False and result["detail"]["exit_code"] == 0
