"""Scenario manifests (``tab.scenario/1``): what to run, and proof it is unchanged.

A manifest pins the seed repository, the event stream, and the evaluator's
ground truth by content hash. Once a scenario is ``frozen`` the harness
refuses to run it if any of those hashes change; changing a frozen scenario
requires a new scenario id/version (EXPERIMENT.md §14, CLAUDE.md rule 6).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness.canonical import iter_tree, pretty_json, sha256_json, tree_hash
from harness.events import Event, load_events
from harness.world import world_only_hashes

SCENARIO_SCHEMA_VERSION = "tab.scenario/1"
SCENARIO_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
_KEYS = {
    "schema_version",
    "scenario_id",
    "family",
    "version",
    "status",
    "held_out",
    "description",
    "base_dir",
    "seed_repo",
    "events",
    "ground_truth",
    "difficulty",
    "budgets",
    "content_hashes",
    "world_state_hashes",
}
_DIFFICULTY_KEYS = {"history_length", "distractor_density"}
_LEVELS = {"history_length": ("short", "medium", "long"), "distractor_density": ("low", "medium", "high")}


# Manifest fields that are themselves outputs of freezing; every other field
# (budgets, difficulty labels, paths, ...) is covered by the "manifest" hash.
_SELF_REFERENTIAL_KEYS = ("status", "content_hashes", "world_state_hashes")
CONTENT_HASH_KEYS = ("seed_repo", "events", "ground_truth", "manifest")


class ScenarioError(ValueError):
    pass


class ScenarioIntegrityError(ScenarioError):
    """A frozen scenario's content no longer matches its recorded hashes."""


@dataclass
class Scenario:
    manifest_path: Path
    data: dict[str, Any]

    # ------------------------------------------------------------ properties
    @property
    def scenario_id(self) -> str:
        return self.data["scenario_id"]

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def base_dir(self) -> Path:
        return (self.manifest_path.parent / self.data["base_dir"]).resolve()

    @property
    def seed_dir(self) -> Path:
        return self.base_dir / self.data["seed_repo"]

    @property
    def events_file(self) -> Path:
        return self.base_dir / self.data["events"]

    @property
    def events_dir(self) -> Path:
        return self.events_file.parent

    @property
    def ground_truth_dir(self) -> Path:
        return self.base_dir / self.data["ground_truth"]

    @property
    def difficulty(self) -> dict[str, str]:
        return dict(self.data["difficulty"])

    @property
    def budgets(self) -> dict[str, Any]:
        return dict(self.data["budgets"])

    def protected_paths(self) -> list[Path]:
        """Directories no contestant tool may touch while this scenario runs."""
        paths = {self.events_dir, self.ground_truth_dir, self.manifest_path.parent}
        world = self.base_dir / "world"
        paths.add(world / "ground_truth")
        paths.add(world / "events")
        paths.add(self.base_dir / "scenarios")
        return sorted(p.resolve() for p in paths)

    def public_info(self) -> dict[str, Any]:
        """Scenario facts that may appear in run metadata."""
        return {
            "scenario_id": self.scenario_id,
            "family": self.data["family"],
            "version": self.data["version"],
            "status": self.status,
            "held_out": self.data["held_out"],
            "difficulty": self.difficulty,
            "content_hashes": dict(self.data["content_hashes"]),
        }

    # ----------------------------------------------------------- operations
    def load_events(self) -> list[Event]:
        return load_events(self.events_file)

    def compute_content_hashes(self) -> dict[str, str]:
        on_disk = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {
            "seed_repo": tree_hash(self.seed_dir),
            "events": tree_hash(self.events_dir),
            "ground_truth": tree_hash(self.ground_truth_dir),
            "manifest": sha256_json({k: v for k, v in on_disk.items() if k not in _SELF_REFERENTIAL_KEYS}),
        }

    def compute_world_state_hashes(self) -> list[str]:
        with tempfile.TemporaryDirectory(prefix="tab-freeze-") as tmp:
            return world_only_hashes(self.seed_dir, self.load_events(), Path(tmp))

    def verify(self, *, allow_draft: bool = False) -> dict[str, str]:
        """Check integrity; returns the freshly computed content hashes."""
        actual = self.compute_content_hashes()
        if self.status == "draft":
            if not allow_draft:
                raise ScenarioError(
                    f"scenario {self.scenario_id} is a draft; freeze it or pass allow_draft=True"
                )
            return actual
        recorded = self.data["content_hashes"]
        bad = sorted(k for k in actual if recorded.get(k) != actual[k])
        if bad:
            raise ScenarioIntegrityError(
                f"frozen scenario {self.scenario_id} changed since it was frozen: {', '.join(bad)}. "
                "Create a new scenario version instead of editing a frozen one."
            )
        _check_no_symlinks(self.seed_dir)
        return actual

    def verify_world_states(self) -> None:
        expected = self.data["world_state_hashes"]
        actual = self.compute_world_state_hashes()
        if expected != actual:
            raise ScenarioIntegrityError(
                f"world-only replay of {self.scenario_id} does not match recorded world_state_hashes"
            )


def _check_no_symlinks(root: Path) -> None:
    for rel, full in iter_tree(root):
        if full.is_symlink():
            raise ScenarioError(f"seed repository must not contain symlinks: {rel}")


def _validate_manifest(data: Any, where: str) -> None:
    if not isinstance(data, dict):
        raise ScenarioError(f"{where}: manifest must be an object")
    keys = set(data)
    if keys != _KEYS:
        raise ScenarioError(
            f"{where}: keys mismatch (missing={sorted(_KEYS - keys)}, unknown={sorted(keys - _KEYS)})"
        )
    if data["schema_version"] != SCENARIO_SCHEMA_VERSION:
        raise ScenarioError(f"{where}: unsupported schema_version {data['schema_version']!r}")
    if not isinstance(data["scenario_id"], str) or not SCENARIO_ID_RE.match(data["scenario_id"]):
        raise ScenarioError(f"{where}: bad scenario_id")
    if data["status"] not in ("draft", "frozen"):
        raise ScenarioError(f"{where}: status must be 'draft' or 'frozen'")
    if isinstance(data["version"], bool) or not isinstance(data["version"], int) or data["version"] < 1:
        raise ScenarioError(f"{where}: version must be a positive integer")
    diff = data["difficulty"]
    if not isinstance(diff, dict) or set(diff) != _DIFFICULTY_KEYS:
        raise ScenarioError(f"{where}: difficulty must have keys {sorted(_DIFFICULTY_KEYS)}")
    for k, allowed in _LEVELS.items():
        if diff[k] not in allowed:
            raise ScenarioError(f"{where}: difficulty.{k} must be one of {allowed}")
    budgets = data["budgets"]
    if not isinstance(budgets, dict) or set(budgets) != {"max_tool_calls_per_event"}:
        raise ScenarioError(f"{where}: budgets must have exactly max_tool_calls_per_event")
    n = budgets["max_tool_calls_per_event"]
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ScenarioError(f"{where}: max_tool_calls_per_event must be a positive integer")
    if not isinstance(data["content_hashes"], dict) or not isinstance(data["world_state_hashes"], list):
        raise ScenarioError(f"{where}: content_hashes must be an object and world_state_hashes a list")
    if not isinstance(data["held_out"], bool):
        raise ScenarioError(f"{where}: held_out must be a boolean")
    if data["status"] == "frozen":
        if set(data["content_hashes"]) != set(CONTENT_HASH_KEYS):
            raise ScenarioError(f"{where}: frozen scenario must record all content hashes")
    for key in ("base_dir", "seed_repo", "events", "ground_truth"):
        if not isinstance(data[key], str) or not data[key] or os.path.isabs(data[key]):
            raise ScenarioError(f"{where}: {key} must be a relative path")


def load_scenario(manifest_path: Path) -> Scenario:
    manifest_path = Path(manifest_path).resolve()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioError(f"{manifest_path.name}: invalid JSON: {exc}") from None
    _validate_manifest(data, manifest_path.name)
    scenario = Scenario(manifest_path=manifest_path, data=data)
    for label, p in (
        ("seed_repo", scenario.seed_dir),
        ("events", scenario.events_file),
        ("ground_truth", scenario.ground_truth_dir),
    ):
        if not p.exists():
            raise ScenarioError(f"{manifest_path.name}: {label} path does not exist: {p}")
    return scenario


def freeze_scenario(manifest_path: Path) -> Scenario:
    """Record content and world-state hashes and mark the scenario frozen.

    Re-freezing an already frozen scenario is allowed only if nothing changed.
    """
    scenario = load_scenario(manifest_path)
    hashes = scenario.compute_content_hashes()
    if scenario.status == "frozen":
        scenario.verify()
        scenario.verify_world_states()
        return scenario
    _check_no_symlinks(scenario.seed_dir)
    scenario.data["content_hashes"] = hashes
    scenario.data["world_state_hashes"] = scenario.compute_world_state_hashes()
    scenario.data["status"] = "frozen"
    scenario.manifest_path.write_text(pretty_json(scenario.data), encoding="utf-8")
    return scenario
