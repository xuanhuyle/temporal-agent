"""One command runs the smoke scenario end-to-end; outputs are stable across processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT

REQUIRED = ("metadata.json", "events.jsonl", "actions.jsonl", "scores.json", "trace.jsonl")


def _cli(args: list[str], cwd: Path, **env_overrides: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), **env_overrides}
    return subprocess.run([sys.executable, "-m", "harness", *args], capture_output=True, text=True, env=env,
                          cwd=cwd, timeout=600)


def test_smoke_command_runs_end_to_end_and_replays(tmp_path):
    proc = _cli(["smoke", "--runs-dir", str(tmp_path / "runs")], cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    run_dir = Path(out["run_dir"])
    assert out["status"] == "completed" and out["run_id"].startswith("smoke_v1__dummy__")
    for name in REQUIRED:
        assert (run_dir / name).is_file(), name
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["agents"][0]["kind"] == "dummy"
    actions = [json.loads(line) for line in (run_dir / "actions.jsonl").read_text().splitlines()]
    assert len(actions) == 10 and all(set(a["usage"]) >= {"model_input_tokens", "model_output_tokens"} for a in actions)
    scores = json.loads((run_dir / "scores.json").read_text())
    assert scores["agents"]["dummy"]["temporal_governance_recall"]["value"] == 0.0

    replay = _cli(["replay", str(run_dir)], cwd=REPO_ROOT)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)["match"] is True


def test_validate_command(tmp_path):
    proc = _cli(["validate", "--static-only"], cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["problems"] == []


def test_fingerprint_is_stable_across_processes_and_environments(tmp_path):
    fingerprints = []
    for i, (seed, lc) in enumerate((("1", "C.UTF-8"), ("2", "C"))):
        cwd = tmp_path / f"cwd{i}"
        tmp = tmp_path / f"tmp{i}"
        cwd.mkdir()
        tmp.mkdir()
        proc = _cli(
            ["smoke", "--agent", "dummy", "--agent", "keyword", "--runs-dir", str(tmp_path / f"runs{i}")],
            cwd=cwd, PYTHONHASHSEED=seed, TMPDIR=str(tmp), LC_ALL=lc,
        )
        assert proc.returncode == 0, proc.stderr
        fingerprints.append(json.loads(proc.stdout)["fingerprint"])
    assert fingerprints[0] == fingerprints[1]
