"""Ground-truth leakage: contestants must not be able to reach evaluator data.

These tests fail if any contestant tool, path, interface object, or emitted
contestant-visible record can expose ``world/ground_truth`` (or future events).
"""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest

from conftest import MINI_CANARY, REPO_ROOT, SMOKE_MANIFEST
from harness.agent import AgentContext, AgentEvent, StepBudget
from harness.runner import RunConfig, run
from harness.scenario import load_scenario
from harness.trace import read_jsonl
from scripted_agents import ProbeAgent, RecordingAgent

CONTESTANT_MODULE_ROOTS = [
    REPO_ROOT / "src" / "harness" / "agent.py",
    REPO_ROOT / "src" / "harness" / "tools.py",
    REPO_ROOT / "src" / "harness" / "workspace.py",
    REPO_ROOT / "src" / "harness" / "canonical.py",
    REPO_ROOT / "src" / "harness" / "agents",
    REPO_ROOT / "src" / "harness" / "errors.py",
    REPO_ROOT / "src" / "harness" / "llm.py",
    REPO_ROOT / "src" / "harness" / "tool_specs.py",
    REPO_ROOT / "src" / "harness" / "wire.py",
    REPO_ROOT / "src" / "harness" / "tripwire.py",
    REPO_ROOT / "src" / "harness" / "worker.py",
    REPO_ROOT / "src" / "contestant_runtime",
    REPO_ROOT / "src" / "baseline",
    REPO_ROOT / "src" / "tesseract",
]
# What contestant packages may import besides the standard library and each other (protocol v0.2).
CONTESTANT_API = ("harness.agent", "harness.errors", "harness.llm", "harness.tool_specs")
CONTESTANT_PACKAGES = ("contestant_runtime", "baseline", "tesseract")
# Modules copied into a contestant process: standard library and each other only.
BUNDLE_MODULES = ("agent", "errors", "llm", "tool_specs", "wire", "tripwire", "worker")
BIG = StepBudget(max_tool_calls_per_event=100_000)
FORBIDDEN_IMPORTS = ("evaluation", "harness.runner", "harness.scenario", "harness.events", "harness.cli",
                     "harness.replay", "harness.world")


def _probe_targets(scenario) -> list[Path]:
    gt = scenario.ground_truth_dir
    return [
        gt / "labels.json",
        gt,
        *sorted(p for p in gt.rglob("*") if p.is_file()),
        scenario.events_file,
        scenario.events_dir / "payloads",
        scenario.manifest_path,
        REPO_ROOT / "world" / "ground_truth",
    ]


def _assert_no_leak(result, probe: ProbeAgent, canary: str) -> None:
    assert probe.denied > 0
    assert not any(canary in item for item in probe.leaked)
    for name in ("events.jsonl", "actions.jsonl", "trace.jsonl"):
        assert canary not in (result.run_dir / name).read_text(), name
    tool_calls = [r for r in read_jsonl(result.run_dir / "trace.jsonl") if r["type"] == "tool_call"]
    assert tool_calls and all(r["status"] in ("denied", "error", "ok") for r in tool_calls)
    assert result.scores["agents"]["probe"]["step_status"].get("budget_exceeded") is None
    # every call aimed at an evaluator path was denied, never ok
    for r in tool_calls:
        arg = str(r["args"].get("path", r["args"].get("prefix", "")))
        if "ground_truth" in arg or "events" in arg or "scenarios" in arg:
            assert r["status"] in ("denied", "error"), r


def test_probe_cannot_reach_mini_ground_truth(mini_scenario, runs_dir):
    probe = ProbeAgent(_probe_targets(mini_scenario))
    result = run(mini_scenario, [probe], RunConfig(runs_dir=runs_dir, budget=BIG))
    _assert_no_leak(result, probe, MINI_CANARY)


@pytest.mark.skipif(not SMOKE_MANIFEST.exists(), reason="smoke scenario not built")
def test_probe_cannot_reach_smoke_ground_truth(runs_dir):
    scenario = load_scenario(SMOKE_MANIFEST)
    canary = json.loads((scenario.ground_truth_dir / "labels.json").read_text())["canary"]
    probe = ProbeAgent(_probe_targets(scenario))
    result = run(scenario, [probe], RunConfig(runs_dir=runs_dir, budget=BIG))
    _assert_no_leak(result, probe, canary)


def test_probe_with_workspace_symlink_into_ground_truth(mini_scenario, runs_dir, monkeypatch):
    """Even if a symlink to ground truth appeared inside a workspace, tools refuse it."""
    from harness import runner as runner_mod

    real_copy = runner_mod.copy_tree

    def copy_and_plant(src, dst, **kwargs):
        real_copy(src, dst, **kwargs)
        if Path(dst).name == "workspace" and "final_state" not in Path(dst).parts:
            (Path(dst) / "gt_link").symlink_to(mini_scenario.ground_truth_dir)

    monkeypatch.setattr(runner_mod, "copy_tree", copy_and_plant)

    class LinkProbe(ProbeAgent):
        def on_event(self, event, tools):
            for p in ("gt_link/labels.json", "gt_link", "gt_link/hidden_tests/test_hidden_mini.py"):
                self._attempt(tools.read_file, p)
                self._attempt(tools.list_files, p)
            self.leaked.extend(tools.list_files())
            self.leaked.append(repr(tools.search("CANARY")))
            from harness.agent import AgentResponse

            return AgentResponse()

    probe = LinkProbe([])
    run(mini_scenario, [probe], RunConfig(runs_dir=runs_dir, budget=BIG))
    assert probe.denied >= 6
    assert not any(MINI_CANARY in x for x in probe.leaked)
    assert not any(x.startswith("gt_link") for x in probe.leaked if isinstance(x, str))


def test_agent_context_and_events_carry_no_ground_truth(mini_scenario, runs_dir):
    agent = RecordingAgent()
    result = run(mini_scenario, [agent], RunConfig(runs_dir=runs_dir))
    ctx = agent.contexts[0]
    assert {f.name for f in dataclasses.fields(AgentContext)} == {
        "agent_name", "seed", "state_dir", "budget", "model", "instructions", "instructions_version",
        "restart_count"}
    rendered = repr(ctx)
    for forbidden in ("ground_truth", "labels.json", str(mini_scenario.base_dir), "scenarios", "mini_v1"):
        assert forbidden not in rendered
    assert {f.name for f in dataclasses.fields(AgentEvent)} == {
        "schema_version", "event_id", "seq", "timestamp", "channel", "author", "subject", "body", "changed_paths"}
    labels = json.loads((mini_scenario.ground_truth_dir / "labels.json").read_text())
    gt_only_keys = {"role", "should_trigger_reconsideration", "near_miss_of", "affected_targets", "causal_path",
                    "historical_state", "remediation", "pattern", "canary", "reconsiderations"}
    for rec in read_jsonl(result.run_dir / "events.jsonl"):
        delivered = rec["delivered"]
        assert not (set(delivered) & gt_only_keys)
        assert labels["canary"] not in json.dumps(delivered)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_contestant_facing_modules_never_import_evaluator_code():
    files = []
    for root in CONTESTANT_MODULE_ROOTS:
        files += [root] if root.is_file() else sorted(root.rglob("*.py"))
    assert files
    for f in files:
        text = f.read_text()
        for name in _imports(f):
            assert not any(name == m or name.startswith(m + ".") for m in FORBIDDEN_IMPORTS), f"{f}: imports {name}"
        assert "ground_truth" not in text, f"{f} mentions ground_truth"


def _stdlib(name: str) -> bool:
    import sys

    return name.split(".")[0] in sys.stdlib_module_names or name == "__future__"


def test_contestant_packages_import_only_the_contestant_api():
    files = [f for pkg in CONTESTANT_PACKAGES for f in sorted((REPO_ROOT / "src" / pkg).rglob("*.py"))]
    assert files, "no contestant packages found"
    for f in files:
        for name in _imports(f):
            ok = _stdlib(name) or name in CONTESTANT_API or name.split(".")[0] in CONTESTANT_PACKAGES
            assert ok, f"{f.relative_to(REPO_ROOT)} imports {name}"


def _runtime_nodes(tree: ast.AST):
    """All nodes except those under ``if TYPE_CHECKING:`` (never executed)."""
    stack = [tree]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.If) and isinstance(child.test, ast.Name) and child.test.id == "TYPE_CHECKING":
                stack.extend(child.orelse)
                continue
            stack.append(child)


def test_contestant_process_bundle_modules_import_only_each_other():
    allowed = {f"harness.{m}" for m in BUNDLE_MODULES} | {"harness"}
    for m in BUNDLE_MODULES:
        f = REPO_ROOT / "src" / "harness" / f"{m}.py"
        assert f.is_file(), f
        tree = ast.parse(f.read_text())
        for node in _runtime_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for name in names:
                    if getattr(node, "level", 0):
                        continue
                    assert _stdlib(name) or name in allowed, f"{f.name} imports {name}"


def test_ground_truth_reader_is_unique():
    readers = [p for p in (REPO_ROOT / "src").rglob("*.py") if "labels.json" in p.read_text()]
    assert [p.relative_to(REPO_ROOT).as_posix() for p in readers] == ["src/evaluation/ground_truth.py"]
