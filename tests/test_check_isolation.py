"""Evaluator check processes run workspace code under the tripwire (benchmark fix, evaluator 0.3.1).

Hidden tests import workspace modules at collection time, so workspace code
runs while the hidden test files exist. These tests plant a workspace module
that, on import, tries to read the ground truth, list the repository, write
outside the checker's scratch, open a socket, start a process and load a C
library. Each attempt that *succeeds* makes the import raise
``SystemExit('LEAK')``, so a passing hidden test (or hygiene suite) proves that
every attempt was refused.
"""

from __future__ import annotations

import dataclasses
import os
import textwrap
import uuid
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from evaluation import checks
from evaluation.checks import evaluate_alternatives, run_hidden_pytest, run_workspace_tests
from evaluation.ground_truth import load_ground_truth
from harness.canonical import copy_tree

SMOKE_LABELS = REPO_ROOT / "world" / "ground_truth" / "smoke_v1" / "labels.json"

PROBES = '''\
import os as _os
import sys as _sys

_LEAKS = []


def _attempt(name, fn):
    try:
        fn()
    except BaseException:  # refused (PermissionError) or failed otherwise: not a leak
        return
    _LEAKS.append(name)


def _read(path):
    with open(path, "rb") as fh:
        fh.read(1)


def _write(path):
    with open(path, "w") as fh:
        fh.write("leak")


def _socket():
    import socket

    socket.socket(socket.AF_INET, socket.SOCK_STREAM).close()


def _process():
    import subprocess

    subprocess.run(["true"], check=True)


def _ctypes():
    import ctypes

    ctypes.CDLL(None)


_attempt("read smoke labels", lambda: _read({smoke_labels!r}))
_attempt("read scenario labels", lambda: _read({scenario_labels!r}))
_attempt("list repository root", lambda: _os.listdir({repo_root!r}))
_attempt("list scenario root", lambda: _os.listdir({scenario_root!r}))
_attempt("write into repository", lambda: _write({repo_leak!r}))
_attempt("write into /tmp", lambda: _write({tmp_leak!r}))
_attempt("write into the snapshot", lambda: _write(_os.path.join(_os.path.dirname(__file__), "leak.txt")))
_attempt("socket", _socket)
_attempt("subprocess", _process)
_attempt("os.system", lambda: _os.system("true"))
_attempt("ctypes", _ctypes)
if _LEAKS:
    raise SystemExit("LEAK: " + ", ".join(_LEAKS))
'''

APP = '''\
import json
from pathlib import Path


def batch_limit() -> int:
    import os
    import sys

    # Test phase: the hidden test file must be gone by now.
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None) or ""
        if f.endswith("test_hidden_mini.py") and os.path.exists(f):
            raise SystemExit("LEAK: hidden test still on disk during the test phase")
    return json.loads((Path(__file__).parent / "config.json").read_text())["batch_limit"]
'''


def _gt(scenario):
    events = scenario.load_events()
    return load_ground_truth(scenario.ground_truth_dir, {e.event_id: e.seq for e in events})


@pytest.fixture
def leaks():
    """Two paths outside every allowed directory; removed afterwards even if a probe got through."""
    tag = uuid.uuid4().hex
    paths = (REPO_ROOT / f".tab-leak-{tag}", Path("/tmp") / f"tab-leak-{tag}")
    yield paths
    for p in paths:
        if p.exists():
            p.unlink()


def _probing_snapshot(scenario, dest: Path, leaks: tuple[Path, Path]) -> Path:
    """The mini seed with a real fix, whose ``app`` module runs every probe at import time."""
    copy_tree(scenario.seed_dir, dest)
    (dest / "config.json").write_text('{"batch_limit": 25}\n')
    probes = PROBES.format(
        smoke_labels=str(SMOKE_LABELS),
        scenario_labels=str(scenario.ground_truth_dir / "labels.json"),
        repo_root=str(REPO_ROOT),
        scenario_root=str(scenario.ground_truth_dir.parents[2]),
        repo_leak=str(leaks[0]),
        tmp_leak=str(leaks[1]),
    )
    (dest / "app.py").write_text(probes + "\n\n" + APP)
    return dest


def _hidden_check(gt):
    return next(c for c in gt.reconsiderations[0].remediation.acceptable[0].checks if c["type"] == "hidden_pytest")


def test_probes_leak_without_the_tripwire(mini_scenario, tmp_path, leaks):
    """Sanity: in an unguarded interpreter the probes do detect access (so a pass below means refusal)."""
    import subprocess
    import sys

    snap = _probing_snapshot(mini_scenario, tmp_path / "snap", leaks)
    try:
        proc = subprocess.run([sys.executable, "-c", "import app"], cwd=snap, capture_output=True, text=True,
                              timeout=60)
    finally:
        if (snap / "leak.txt").exists():
            (snap / "leak.txt").unlink()
    assert proc.returncode != 0
    assert "LEAK: read smoke labels, read scenario labels, list repository root" in proc.stderr


def test_hidden_test_process_refuses_reads_writes_network_processes_ctypes(mini_scenario, tmp_path, leaks):
    gt = _gt(mini_scenario)
    snap = _probing_snapshot(mini_scenario, tmp_path / "snap", leaks)
    before = sorted(p.name for p in snap.iterdir())
    result = run_hidden_pytest(_hidden_check(gt), snap, gt)
    assert result["passed"] is True, result
    assert result["detail"]["junit"]["passed"] == result["detail"]["expected_tests"] == 1
    assert not leaks[0].exists() and not leaks[1].exists()
    assert sorted(p.name for p in snap.iterdir()) == before  # nothing written into the snapshot


def test_full_remediation_still_passes_with_probing_workspace(mini_scenario, tmp_path, leaks):
    gt = _gt(mini_scenario)
    snap = _probing_snapshot(mini_scenario, tmp_path / "snap", leaks)
    result = evaluate_alternatives(gt.reconsiderations[0].remediation.acceptable, snap, gt)
    assert result["passed"] is True, result
    assert not leaks[0].exists() and not leaks[1].exists()


def test_hidden_files_are_deleted_before_the_test_phase(mini_scenario, tmp_path, leaks, monkeypatch):
    """The probe in ``batch_limit`` fails the check if the evaluator acknowledges without deleting."""
    gt = _gt(mini_scenario)
    snap = _probing_snapshot(mini_scenario, tmp_path / "snap", leaks)
    assert run_hidden_pytest(_hidden_check(gt), snap, gt)["passed"] is True

    def ack_without_deleting(req_r, ack_w, paths):
        try:
            if os.read(req_r, 1):
                os.write(ack_w, b"k")
        except OSError:
            pass

    monkeypatch.setattr(checks, "_serve_unlink", ack_without_deleting)
    result = run_hidden_pytest(_hidden_check(gt), snap, gt)
    assert result["passed"] is False and result["detail"]["junit"]["failed"] == 1


def test_hygiene_process_refuses_reads_writes_network_processes_ctypes(mini_scenario, tmp_path, leaks):
    snap = _probing_snapshot(mini_scenario, tmp_path / "snap", leaks)
    before = sorted(p.name for p in snap.iterdir())
    result = run_workspace_tests(snap)
    assert result["passed"] is True, result
    assert result["detail"]["junit"]["passed"] == result["detail"]["junit"]["tests"] == 1
    assert not leaks[0].exists() and not leaks[1].exists()
    assert sorted(p.name for p in snap.iterdir()) == before


def test_pass_criterion_unchanged_under_the_tripwire(mini_scenario, tmp_path):
    """Exact JUnit count, all passed: an unremediated or miscounted run still fails."""
    gt = _gt(mini_scenario)
    check = _hidden_check(gt)
    snap = tmp_path / "snap"
    copy_tree(mini_scenario.seed_dir, snap)  # batch_limit stays 1
    failed = run_hidden_pytest(check, snap, gt)
    assert failed["passed"] is False and failed["detail"]["junit"]["failed"] == 1
    (snap / "config.json").write_text('{"batch_limit": 25}\n')
    assert run_hidden_pytest(check, snap, gt)["passed"] is True
    inflated = dataclasses.replace(gt, hidden_test_counts={k: v + 1 for k, v in gt.hidden_test_counts.items()})
    miscounted = run_hidden_pytest(check, snap, inflated)
    assert miscounted["passed"] is False and miscounted["detail"]["exit_code"] == 0


def test_honest_tmp_path_use_still_works_in_hygiene(tmp_path):
    """pytest's tmp_path lives under the checker's private TMPDIR, which stays writable."""
    snap = tmp_path / "snap"
    (snap / "tests").mkdir(parents=True)
    (snap / "tests" / "test_tmp.py").write_text(
        textwrap.dedent(
            """\
            import tempfile
            import zoneinfo


            def test_tmp_path(tmp_path):
                (tmp_path / "x.txt").write_text("ok")
                assert (tmp_path / "x.txt").read_text() == "ok"


            def test_tempfile_and_zoneinfo():
                with tempfile.NamedTemporaryFile("w") as fh:
                    fh.write("ok")
                assert zoneinfo.ZoneInfo("Europe/Paris").key == "Europe/Paris"
            """
        )
    )
    result = run_workspace_tests(snap)
    assert result["passed"] is True, result
    assert result["detail"]["junit"]["passed"] == 2


def test_seed_suite_still_passes_as_hygiene(tmp_path):
    copy_tree(REPO_ROOT / "world" / "seed_repo", tmp_path / "seed")
    result = run_workspace_tests(tmp_path / "seed")
    assert result["passed"], result
    assert result["detail"]["junit"]["tests"] >= 50
    assert result["detail"]["junit"]["passed"] == result["detail"]["junit"]["tests"]


def test_checker_child_never_imports_the_benchmark_source_tree(mini_scenario, tmp_path):
    """The child uses a private tripwire copy; the repository's src/ is not readable to it."""
    gt = _gt(mini_scenario)
    snap = tmp_path / "snap"
    copy_tree(mini_scenario.seed_dir, snap)
    (snap / "config.json").write_text('{"batch_limit": 25}\n')
    src = REPO_ROOT / "src"
    (snap / "app.py").write_text(
        "import sys\n"
        f"if any(str(getattr(m, '__file__', '') or '').startswith({str(src) + os.sep!r}) for m in list(sys.modules.values())):\n"
        "    raise SystemExit('LEAK: benchmark module imported')\n"
        "try:\n"
        f"    open({str(src / 'harness' / 'tripwire.py')!r}).close()\n"
        "except PermissionError:\n"
        "    pass\n"
        "else:\n"
        "    raise SystemExit('LEAK: source tree readable')\n"
        + APP
    )
    assert run_hidden_pytest(_hidden_check(gt), snap, gt)["passed"] is True
