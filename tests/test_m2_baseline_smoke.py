"""Milestone 2 machinery check: the baseline presets run end-to-end on smoke_v1.

The deterministic ``fake`` model drives the shared contestant runtime, so these
tests check machinery (process boundary, history and command tools, retrieval,
metering, replay, reproducibility). They say nothing about how well the
baseline performs, and nothing here may be tuned to smoke_v1's answers.
"""

from __future__ import annotations

import json

import pytest

from conftest import SMOKE_MANIFEST
from harness.agent import ModelSettings
from harness.agents import create_agent
from harness.contestants import BASELINE_SMOKE_SET
from harness.replay import load_blob, replay_run
from harness.runner import OUTPUT_FILES, RunConfig, run
from harness.scenario import load_scenario
from harness.trace import read_jsonl

FAKE = ModelSettings(provider="fake", name="fake-v1", embedding_provider="hash", embedding_model="hash-ngram-v1",
                     embedding_dims=384)


@pytest.fixture(scope="module")
def smoke_scenario():
    return load_scenario(SMOKE_MANIFEST)


@pytest.fixture(scope="module")
def baseline_run(smoke_scenario, tmp_path_factory):
    runs = tmp_path_factory.mktemp("m2_runs")
    agents = [create_agent(kind) for kind in BASELINE_SMOKE_SET]
    return run(smoke_scenario, agents, RunConfig(runs_dir=runs, model=FAKE))


def _trace(result):
    return read_jsonl(result.run_dir / "trace.jsonl")


def test_every_preset_completes_in_its_own_process(baseline_run):
    assert baseline_run.status == "completed"
    meta = json.loads((baseline_run.run_dir / "metadata.json").read_text())
    assert meta["isolation"] == {k: "process" for k in BASELINE_SMOKE_SET}
    for name in BASELINE_SMOKE_SET:
        agent = baseline_run.scores["agents"][name]
        assert agent["step_status"] == {"ok": 10}, (name, agent["step_status"])
        assert (baseline_run.run_dir / "final_state" / name / "logs").is_dir()
    for name in OUTPUT_FILES:
        assert (baseline_run.run_dir / name).is_file()
    specs = {a["name"]: a for a in meta["agents"]}
    assert {specs[k]["config"]["top_k"] for k in ("baseline-k8", "baseline-k32", "baseline-k64")} == {8, 32, 64}
    assert specs["baseline-full"]["config"]["mode"] == "full"


def test_usage_is_metered_and_model_settings_are_identical(baseline_run):
    for name in BASELINE_SMOKE_SET:
        eff = baseline_run.scores["agents"][name]["efficiency"]
        assert eff["model_calls"] > 0 and eff["model_input_tokens"] > 0 and eff["model_output_tokens"] > 0, name
        assert eff["tool_calls"] > 0, name
        assert eff["cost_known"] is True and eff["cost_usd"] == 0.0
    meters = [r["meter"] for r in _trace(baseline_run) if r["type"] == "tool_call" and r.get("tool") == "model_complete"
              and r["status"] == "ok"]
    assert {(m["provider"], m["model"]) for m in meters} == {("fake", "fake-v1")}
    by_agent = {r["agent"] for r in _trace(baseline_run) if r["type"] == "tool_call" and r.get("tool") == "model_complete"}
    assert by_agent == set(BASELINE_SMOKE_SET)


def test_history_and_command_tools_are_exercised_without_future_states(baseline_run):
    blobs = baseline_run.run_dir / "blobs"
    calls = [r for r in _trace(baseline_run) if r["type"] == "tool_call"]
    tools_used = {r["tool"] for r in calls}
    assert {"history", "diff", "run_command", "model_complete"} <= tools_used
    for r in calls:
        if r["tool"] == "history" and r["status"] == "ok":
            states = load_blob(blobs, r["result_sha256"])
            assert [s["seq"] for s in states] == list(range(r["seq"] + 1))
        if r["tool"] in ("read_at", "list_at") and r["status"] == "ok":
            assert r["args"]["seq"] <= r["seq"]
        if r["tool"] == "diff" and r["status"] == "ok":
            assert max(r["args"]["seq_a"], r["args"]["seq_b"]) <= r["seq"]


def test_baseline_run_replays_exactly(baseline_run):
    _, report = replay_run(baseline_run.run_dir)
    assert report["match"], report


def test_smoke_scenario_is_unchanged(smoke_scenario):
    smoke_scenario.verify()
    smoke_scenario.verify_world_states()


def test_a_baseline_configuration_is_reproducible(smoke_scenario, tmp_path):
    fingerprints = []
    for i in range(2):
        result = run(smoke_scenario, [create_agent("baseline-k8")], RunConfig(runs_dir=tmp_path / f"r{i}", model=FAKE))
        assert result.status == "completed"
        fingerprints.append(result.fingerprint)
    assert fingerprints[0] == fingerprints[1]
