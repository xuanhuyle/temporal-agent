"""Shared fixtures.

``mini_scenario`` builds a tiny, self-contained scenario (seed repo, 3 events,
ground truth with one reconsideration) in a temporary repository layout so
that harness/evaluator tests do not depend on the smoke scenario's content.
"""

from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path
from typing import Callable

import pytest

from harness.scenario import Scenario, freeze_scenario, load_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_MANIFEST = REPO_ROOT / "scenarios" / "smoke" / "smoke_v1.json"
MINI_CANARY = "TAB-GT-CANARY-mini-0f1e2d3c4b5a6978"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _event(seq: int, ts: str, channel: str, subject: str, body: str, changes: list) -> dict:
    return {
        "schema_version": "tab.event/1",
        "event_id": f"evt-{seq:04d}",
        "seq": seq,
        "timestamp": ts,
        "channel": channel,
        "author": "Sam (Platform)",
        "subject": subject,
        "body": body,
        "world_changes": changes,
    }


def build_mini_repo(root: Path) -> Path:
    """Create a mini benchmark layout under ``root``; returns the (draft) manifest path."""
    seed = root / "world" / "seed_repo"
    _write(seed / "config.json", json.dumps({"batch_limit": 1}, indent=2) + "\n")
    _write(
        seed / "app.py",
        textwrap.dedent(
            '''\
            import json
            from pathlib import Path

            def batch_limit() -> int:
                return json.loads((Path(__file__).parent / "config.json").read_text())["batch_limit"]
            '''
        ),
    )
    _write(
        seed / "docs" / "adr" / "0001-batch-limit.md",
        "# ADR-0001: Batch limit of 1\n\nThe vendor API accepts one record per request, so we send records one at a time.\n",
    )
    _write(seed / "tests" / "test_app.py", "import app\n\ndef test_limit_positive():\n    assert app.batch_limit() >= 1\n")
    _write(seed / "pyproject.toml", '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n')

    events_dir = root / "world" / "events" / "mini_v1"
    _write(events_dir / "payloads" / "evt-0002" / "VENDOR.md", "Vendor API v2: batch endpoint accepts up to 50 records.\n")
    events = [
        _event(1, "2026-01-02T09:00:00Z", "ticket", "Fix README wording", "Please tidy the README.",
               [{"op": "write_file", "path": "README.md", "content": "# Mini app\n"}]),
        _event(2, "2026-01-09T09:00:00Z", "changelog", "Vendor API v2 released", "The vendor shipped API v2 today.",
               [{"op": "write_file", "path": "VENDOR.md", "source": "payloads/evt-0002/VENDOR.md"}]),
        _event(3, "2026-01-10T09:00:00Z", "chat", "Lunch order", "Pizza on Friday?", []),
    ]
    _write(events_dir / "events.jsonl", "".join(json.dumps(e) + "\n" for e in events))

    gt_dir = root / "world" / "ground_truth" / "mini_v1"
    _write(
        gt_dir / "hidden_tests" / "test_hidden_mini.py",
        f"# {MINI_CANARY}\nimport colorsys  # a stdlib module pytest itself never imports\n\nimport app\n\n"
        "def test_batching_enabled():\n    assert colorsys.ONE_THIRD and app.batch_limit() >= 10\n",
    )
    _write(gt_dir / "reference" / "R1" / "config.json", json.dumps({"batch_limit": 50}, indent=2) + "\n")
    _write(gt_dir / "CANARY", MINI_CANARY + "\n")
    labels = {
        "schema_version": "tab.ground_truth/1",
        "scenario_id": "mini_v1",
        "canary": MINI_CANARY,
        "targets": {
            "ADR-0001": {"kind": "decision", "introduced_by": "seed", "decided_on": "2026-01-02", "summary": "batch limit 1"}
        },
        "events": {
            "evt-0001": {"role": "distractor", "should_trigger_reconsideration": False, "near_miss_of": None,
                         "acceptable_reopens": [], "notes": ""},
            "evt-0002": {"role": "trigger", "should_trigger_reconsideration": True, "near_miss_of": None,
                         "acceptable_reopens": [], "notes": ""},
            "evt-0003": {"role": "distractor", "should_trigger_reconsideration": False, "near_miss_of": None,
                         "acceptable_reopens": [], "notes": ""},
        },
        "reconsiderations": [
            {
                "id": "R1",
                "pattern": "E",
                "trigger_event": "evt-0002",
                "affected_targets": ["ADR-0001"],
                "window": {"from_seq": 2, "to_seq": 3},
                "abstention_acceptable": False,
                "evidence_locus": "workspace",
                "causal_path": [
                    {"ref": "evt-0002", "kind": "event", "note": "vendor batch endpoint"},
                    {"ref": "ADR-0001", "kind": "decision", "note": "one record per request"},
                ],
                "historical_state": {
                    "known_then": ["seed"],
                    "true_then": [],
                    "known_now_about_then": ["evt-0002"],
                },
                "remediation": {
                    "evaluate_at_seq": 3,
                    "acceptable": [
                        {
                            "id": "limit_raised",
                            "checks": [
                                {"type": "json_value", "path": "config.json", "pointer": "/batch_limit", "op": "ge", "value": 10},
                                {"type": "hidden_pytest", "files": ["hidden_tests/test_hidden_mini.py"]},
                            ],
                        }
                    ],
                    "reference": [{"op": "write_file", "path": "config.json", "source": "reference/R1/config.json"}],
                },
                "difficulty": {"causal_depth": 1, "temporal_lag": "near", "lag_events": 2, "lag_days": 7, "wording": "natural"},
            }
        ],
    }
    _write(gt_dir / "labels.json", json.dumps(labels, indent=2) + "\n")

    manifest = {
        "schema_version": "tab.scenario/1",
        "scenario_id": "mini_v1",
        "family": "mini",
        "version": 1,
        "status": "draft",
        "held_out": False,
        "description": "Three-event test scenario.",
        "base_dir": "../..",
        "seed_repo": "world/seed_repo",
        "events": "world/events/mini_v1/events.jsonl",
        "ground_truth": "world/ground_truth/mini_v1",
        "difficulty": {"history_length": "short", "distractor_density": "medium"},
        "budgets": {"max_tool_calls_per_event": 20},
        "content_hashes": {},
        "world_state_hashes": [],
    }
    path = root / "scenarios" / "mini" / "mini_v1.json"
    _write(path, json.dumps(manifest, indent=2) + "\n")
    return path


@pytest.fixture
def mini_manifest(tmp_path: Path) -> Path:
    """A frozen mini scenario in its own temporary repository layout."""
    path = build_mini_repo(tmp_path / "repo")
    freeze_scenario(path)
    return path


@pytest.fixture
def mini_scenario(mini_manifest: Path) -> Scenario:
    return load_scenario(mini_manifest)


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runs"
    d.mkdir()
    return d


@pytest.fixture
def smoke_copy(tmp_path: Path) -> Callable[[], Path]:
    """Copy the real repository's world + scenarios to tmp (for tamper tests)."""

    def _copy() -> Path:
        dst = tmp_path / "smoke_repo"
        shutil.copytree(REPO_ROOT / "world", dst / "world", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        shutil.copytree(REPO_ROOT / "scenarios", dst / "scenarios")
        return dst / "scenarios" / "smoke" / "smoke_v1.json"

    return _copy
