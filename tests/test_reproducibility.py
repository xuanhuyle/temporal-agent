"""Determinism, replay, and frozen-scenario integrity."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from harness.agents import create_agent
from harness.replay import ReplayError, replay_run
from harness.runner import RunConfig, run
from harness.scenario import ScenarioIntegrityError, freeze_scenario, load_scenario
from harness.trace import FINGERPRINT_FILES, canonical_records
from scripted_agents import GreedyAgent, IndexingAgent, InvalidResponseAgent, RaisingAgent, ReopenOnTriggerAgent, SetupFailAgent, WriterAgent


def _agents():
    return [
        create_agent("dummy"),
        create_agent("keyword"),
        ReopenOnTriggerAgent("fixer", "evt-0002", "ADR-0001", writes={"config.json": '{"batch_limit": 20}\n'}),
        WriterAgent("writer"),
        RaisingAgent("raiser"),
        GreedyAgent("greedy"),
        InvalidResponseAgent("invalid"),
        SetupFailAgent("broken"),
        IndexingAgent("indexer"),
    ]


def test_identical_inputs_give_identical_outputs(mini_scenario, runs_dir):
    a = run(mini_scenario, _agents(), RunConfig(runs_dir=runs_dir / "a"))
    b = run(mini_scenario, _agents(), RunConfig(runs_dir=runs_dir / "b"))
    assert a.run_id == b.run_id  # deterministic run id
    assert a.fingerprint == b.fingerprint
    for name in FINGERPRINT_FILES:
        assert canonical_records(a.run_dir / name) == canonical_records(b.run_dir / name), name
    fixer = a.scores["agents"]["fixer"]
    assert fixer["temporal_governance_recall"]["value"] == 1.0
    assert fixer["present_remediation_success"]["value"] == 1.0


def test_run_id_depends_on_config(mini_scenario, runs_dir):
    a = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    b = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir, seed=1))
    assert a.run_id.split("__")[-1] != b.run_id.split("__")[-1]


def test_replay_reproduces_run_including_failures(mini_scenario, runs_dir):
    original = run(mini_scenario, _agents(), RunConfig(runs_dir=runs_dir))
    result, report = replay_run(original.run_dir)
    assert report["match"], report
    assert result.run_id == original.run_id + "__replay"
    assert json.loads((result.run_dir / "metadata.json").read_text())["replay_of"] == original.run_id
    assert (result.run_dir / "replay_report.json").is_file()
    # the original directory is untouched
    assert json.loads((original.run_dir / "metadata.json").read_text())["fingerprint"] == original.fingerprint


def test_replay_detects_tampered_records(mini_scenario, runs_dir):
    original = run(mini_scenario, _agents(), RunConfig(runs_dir=runs_dir))
    trace_path = original.run_dir / "trace.jsonl"
    lines = trace_path.read_text().splitlines()
    for i, line in enumerate(lines):
        rec = json.loads(line)
        if rec["type"] == "agent_response" and rec["agent"] == "fixer" and rec["actions"]:
            rec["actions"][0]["target"] = "ADR-0009"
            lines[i] = json.dumps(rec)
    trace_path.write_text("\n".join(lines) + "\n")
    _, report = replay_run(original.run_dir)
    assert not report["match"]
    assert {m["file"] for m in report["mismatches"]} >= {"actions.jsonl", "scores.json"}


def test_replay_refuses_changed_scenario(mini_scenario, runs_dir):
    original = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    (mini_scenario.ground_truth_dir / "labels.json").write_text(
        (mini_scenario.ground_truth_dir / "labels.json").read_text().replace('"notes": ""', '"notes": "edited"', 1)
    )
    with pytest.raises(Exception, match="differs|changed"):
        replay_run(original.run_dir)


def test_replay_refuses_incomplete_runs(mini_scenario, runs_dir):
    original = run(mini_scenario, [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    meta_path = original.run_dir / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["status"] = "failed"
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(ReplayError):
        replay_run(original.run_dir)


@pytest.mark.parametrize("what", ["seed", "events", "ground_truth"])
def test_frozen_scenario_refuses_to_run_after_any_change(mini_scenario, runs_dir, what):
    target = {
        "seed": mini_scenario.seed_dir / "app.py",
        "events": mini_scenario.events_dir / "payloads" / "evt-0002" / "VENDOR.md",
        "ground_truth": mini_scenario.ground_truth_dir / "hidden_tests" / "test_hidden_mini.py",
    }[what]
    target.write_text(target.read_text() + "\n# silently changed\n")
    with pytest.raises(ScenarioIntegrityError, match="new scenario version"):
        run(load_scenario(mini_scenario.manifest_path), [create_agent("dummy")], RunConfig(runs_dir=runs_dir))
    with pytest.raises(ScenarioIntegrityError):
        freeze_scenario(mini_scenario.manifest_path)  # re-freezing changed content is refused


def test_world_state_hashes_are_reproducible(mini_scenario):
    mini_scenario.verify_world_states()
    assert len(mini_scenario.data["world_state_hashes"]) == 3


def _cli_fingerprint(manifest: Path, runs: Path, hashseed: str) -> str:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), "PYTHONHASHSEED": hashseed}
    out = subprocess.run(
        [sys.executable, "-m", "harness", "run", "--scenario", str(manifest), "--agent", "dummy", "--agent",
         "keyword", "--runs-dir", str(runs)],
        capture_output=True, text=True, env=env, cwd=REPO_ROOT, timeout=300,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)["fingerprint"]


def test_fingerprint_independent_of_hash_seed(mini_manifest, tmp_path):
    assert _cli_fingerprint(mini_manifest, tmp_path / "r1", "1") == _cli_fingerprint(mini_manifest, tmp_path / "r2", "2")
