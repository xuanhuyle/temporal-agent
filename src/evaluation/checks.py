"""Remediation checks, run after the run on evaluator-only workspace snapshots.

During the run the evaluator only *snapshots* an agent's workspace (regular
files only, fresh inodes) into an evaluator-owned directory at
``evaluate_at_seq``. Checks run after every agent has been torn down, so
nothing agent code does under test can reach the agent afterwards, and the
evaluation schedule is not observable during the run.

Hidden behavioural tests run in an isolated interpreter that agent files
cannot reconfigure:

- ``python -P -s -B`` with an environment built from scratch (no PYTHONPATH,
  no user site, cwd not on ``sys.path``, no bytecode written);
- pytest is imported *before* the snapshot is appended (not prepended) to
  ``sys.path``, so a workspace ``pytest.py``/``json.py`` cannot shadow anything;
- an evaluator-owned ini (``-c``) so workspace ``addopts`` are ignored;
  ``--noconftest``; ``PYTEST_DISABLE_PLUGIN_AUTOLOAD=1``;
- hidden tests are materialized from memory into a fresh directory outside
  the snapshot;
- a pass requires the JUnit report to show exactly the expected number of
  hidden test cases, all passed (no skips, failures, or errors), not just a
  zero exit code.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from evaluation.ground_truth import GroundTruth, RemediationAlternative

PYTEST_TIMEOUT_S = 180
# -P: don't put cwd/script dir on sys.path; -s: no user site; -B: no bytecode.
# (Not -I/-E: the environment below is constructed from scratch and must apply.)
_PY_FLAGS = ("-P", "-s", "-B")

_BOOTSTRAP = """\
import sys
import pytest
snapshot, ini, rootdir, junit = sys.argv[1:5]
sys.path.append(snapshot)
sys.exit(pytest.main(["-c", ini, "--rootdir", rootdir, "-p", "no:cacheprovider", "-q",
                      "--junitxml", junit, *sys.argv[5:]]))
"""
_HYGIENE_BOOTSTRAP = """\
import sys
import pytest
snapshot, junit = sys.argv[1:3]
sys.path.append(snapshot)
sys.exit(pytest.main(["--rootdir", snapshot, "-p", "no:cacheprovider", "-q", "--junitxml", junit,
                      *sys.argv[3:]]))
"""


def _env(home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "HOME": str(home),
        "TMPDIR": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
    }


def _junit_summary(path: Path) -> dict[str, int] | None:
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    counts = {"tests": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for case in root.iter("testcase"):
        counts["tests"] += 1
        tags = {child.tag for child in case}
        if "failure" in tags:
            counts["failed"] += 1
        elif "error" in tags:
            counts["errors"] += 1
        elif "skipped" in tags:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    return counts


def _run(cmd: list[str], cwd: Path, home: Path) -> int | None:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=_env(home),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PYTEST_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return None
    return proc.returncode


def run_hidden_pytest(check: dict[str, Any], snapshot: Path, gt: GroundTruth) -> dict[str, Any]:
    expected = sum(gt.hidden_test_counts[rel] for rel in check["files"])
    with tempfile.TemporaryDirectory(prefix="tab-hidden-") as tmp:
        tmp_path = Path(tmp)
        hidden_dir = tmp_path / "hidden"
        home = tmp_path / "home"
        hidden_dir.mkdir()
        home.mkdir()
        targets = []
        for rel in check["files"]:
            dest = hidden_dir / Path(rel).name
            dest.write_bytes(gt.file_bytes(rel))
            targets.append(str(dest))
        ini = tmp_path / "pytest.ini"
        ini.write_text("[pytest]\naddopts =\n", encoding="utf-8")
        junit = tmp_path / "junit.xml"
        code = _run(
            [sys.executable, *_PY_FLAGS, "-c", _BOOTSTRAP, str(snapshot), str(ini), str(hidden_dir), str(junit),
             "--noconftest", *targets],
            cwd=home,
            home=home,
        )
        summary = _junit_summary(junit)
    passed = (
        code == 0
        and summary is not None
        and summary["tests"] == expected
        and summary["passed"] == expected
    )
    return {
        "type": "hidden_pytest",
        "passed": passed,
        "detail": {"exit_code": code, "timeout": code is None, "expected_tests": expected, "junit": summary},
    }


def run_workspace_tests(snapshot: Path, targets: tuple[str, ...] = ("tests",)) -> dict[str, Any]:
    """Hygiene: does the agent's own test suite pass on its final workspace?

    Uses the workspace's own pytest configuration and conftest files (they are
    part of the suite), so this is reported separately from remediation and is
    not tamper-proof.
    """
    with tempfile.TemporaryDirectory(prefix="tab-hygiene-") as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        junit = Path(tmp) / "junit.xml"
        existing = [t for t in targets if (snapshot / t).exists()]
        if not existing:
            return {"passed": False, "detail": {"exit_code": None, "reason": "no test directory"}}
        code = _run([sys.executable, *_PY_FLAGS, "-c", _HYGIENE_BOOTSTRAP, str(snapshot), str(junit), *existing],
                    cwd=snapshot, home=home)
        summary = _junit_summary(junit)
    return {"passed": code == 0, "detail": {"exit_code": code, "timeout": code is None, "junit": summary}}


def _read(snapshot: Path, rel: str) -> str | None:
    p = snapshot / rel
    if p.is_symlink() or not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _json_pointer(doc: Any, pointer: str) -> Any:
    if pointer == "":
        return doc
    cur = doc
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if token not in cur:
                raise KeyError(pointer)
            cur = cur[token]
        elif isinstance(cur, list):
            if not token.isdigit() or int(token) >= len(cur):
                raise KeyError(pointer)
            cur = cur[int(token)]
        else:
            raise KeyError(pointer)
    return cur


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return False
    if not (isinstance(actual, (int, float)) and isinstance(expected, (int, float))):
        return False
    return {"lt": actual < expected, "le": actual <= expected, "gt": actual > expected, "ge": actual >= expected}[op]


def run_check(check: dict[str, Any], snapshot: Path, gt: GroundTruth) -> dict[str, Any]:
    kind = check["type"]
    if kind == "hidden_pytest":
        return run_hidden_pytest(check, snapshot, gt)
    out: dict[str, Any] = {"type": kind, "path": check["path"]}
    if kind in ("file_exists", "file_absent"):
        p = snapshot / check["path"]
        exists = p.is_file() and not p.is_symlink()
        out["passed"] = exists if kind == "file_exists" else not exists
    elif kind == "file_regex":
        text = _read(snapshot, check["path"])
        matched = text is not None and re.search(check["pattern"], text, re.MULTILINE) is not None
        out["passed"] = (text is not None) and (matched == check["must_match"])
    elif kind == "json_value":
        text = _read(snapshot, check["path"])
        try:
            actual = _json_pointer(json.loads(text), check["pointer"]) if text is not None else None
            out["passed"] = text is not None and _compare(actual, check["op"], check["value"])
        except (json.JSONDecodeError, KeyError):
            out["passed"] = False
    else:  # pragma: no cover - rejected at load time
        raise ValueError(f"unknown check type {kind}")
    return out


def evaluate_alternatives(
    alternatives: tuple[RemediationAlternative, ...], snapshot: Path, gt: GroundTruth
) -> dict[str, Any]:
    """Remediation passes if any alternative passes all of its checks.

    The snapshot is never modified: hidden tests live outside it and test
    processes cannot write bytecode into it.
    """
    results = []
    for alt in alternatives:
        check_results = [run_check(c, snapshot, gt) for c in alt.checks]
        results.append({"id": alt.id, "passed": all(r["passed"] for r in check_results), "checks": check_results})
    return {"passed": any(r["passed"] for r in results), "alternatives": results}
