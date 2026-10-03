"""Scenario validators reject broken scenarios (each rule has a negative case)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import MINI_CANARY, build_mini_repo
from evaluation.validate import ScenarioValidationError, validate_scenario
from harness.scenario import load_scenario


def _events_path(root: Path) -> Path:
    return root / "world" / "events" / "mini_v1" / "events.jsonl"


def _edit_events(root: Path, fn) -> None:
    path = _events_path(root)
    events = [json.loads(line) for line in path.read_text().splitlines()]
    fn(events)
    path.write_text("".join(json.dumps(e) + "\n" for e in events))


def _edit_labels(root: Path, fn) -> None:
    path = root / "world" / "ground_truth" / "mini_v1" / "labels.json"
    labels = json.loads(path.read_text())
    fn(labels)
    path.write_text(json.dumps(labels))


def _validate(root: Path, **kwargs):
    return validate_scenario(load_scenario(root / "scenarios" / "mini" / "mini_v1.json"), **kwargs)


@pytest.fixture
def mini_root(tmp_path):
    root = tmp_path / "repo"
    build_mini_repo(root)
    return root


def test_valid_mini_scenario_passes(mini_root):
    report = _validate(mini_root, run_agents=True, world_suite=True)
    assert report["problems"] == []


def _break_canary_in_seed(root):
    (root / "world" / "seed_repo" / "NOTES.md").write_text(f"copied from somewhere: {MINI_CANARY}\n")


def _break_canary_missing(root):
    p = root / "world" / "ground_truth" / "mini_v1" / "hidden_tests" / "test_hidden_mini.py"
    p.write_text(p.read_text().replace(MINI_CANARY, "no canary here"))


def _break_canary_in_docs(root):
    (root / "docs").mkdir()
    (root / "docs" / "notes.md").write_text(MINI_CANARY)


def _break_hint_wording(root):
    _edit_events(root, lambda ev: ev[0].update(body="We should revisit ADR-0001 soon."))


def _break_trigger_names_target(root):
    _edit_events(root, lambda ev: ev[1].update(body="The vendor shipped API v2, which affects ADR-0001."))


def _break_contestant_vocabulary(root):
    _edit_events(root, lambda ev: ev[2].update(body="Use the Tesseract chronicle for this."))


def _break_clobber(root):
    _edit_events(root, lambda ev: ev[2].update(world_changes=[{"op": "write_file", "path": "config.json",
                                                                "content": "{\"batch_limit\": 1}\n"}]))


def _break_distractor_ratio(root):
    _edit_labels(root, lambda lab: lab["events"]["evt-0003"].update(role="decision_setup"))


def _break_world_suite(root):
    _edit_events(root, lambda ev: ev[0]["world_changes"].append(
        {"op": "write_file", "path": "tests/test_broken.py", "content": "def test_x():\n    assert False\n"}))


def _break_solvability(root):
    (root / "world" / "ground_truth" / "mini_v1" / "reference" / "R1" / "config.json").write_text('{"batch_limit": 1}\n')


@pytest.mark.parametrize(
    "breaker,kwargs,message",
    [
        (_break_canary_in_seed, {}, "canary found outside ground truth: world/seed_repo/NOTES.md"),
        (_break_canary_missing, {}, "without canary"),
        (_break_canary_in_docs, {}, "canary found outside ground truth: docs/notes.md"),
        (_break_hint_wording, {}, "reconsideration verb"),
        (_break_trigger_names_target, {}, "names its affected target"),
        (_break_contestant_vocabulary, {}, "vocabulary"),
        (_break_clobber, {}, "remediation window"),
        (_break_distractor_ratio, {}, "distractors"),
        (_break_world_suite, {"world_suite": True}, "seed test suite fails after evt-0001"),
        (_break_solvability, {"run_agents": True}, "solvability check failed: oracle remediation"),
    ],
)
def test_validators_reject_broken_scenarios(mini_root, breaker, kwargs, message):
    breaker(mini_root)
    options = {"run_agents": False, "world_suite": False, **kwargs}
    with pytest.raises(ScenarioValidationError, match=message):
        _validate(mini_root, **options)
