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
  zero exit code;
- :mod:`harness.tripwire` is installed after pytest is imported and before
  the snapshot is put on ``sys.path``. The child imports a private read-only
  copy written next to the bootstrap, never the benchmark's source tree.
  Reads are allowed only under the snapshot, the hidden-test directory, the
  evaluator's ini directory, the JUnit output directory, the private
  ``HOME``/``TMPDIR``, this interpreter's stdlib and site-packages and
  ``/usr/share/zoneinfo``. Writes are allowed only under the JUnit output
  directory and the private ``HOME``/``TMPDIR``. Network, processes and
  ctypes are refused. Workspace code therefore cannot casually read the
  ground truth or the rest of the repository, write outside the checker's
  scratch directories, or reach the network.

Hidden tests import workspace modules, so workspace code *does* run during
collection, while the hidden test files exist and are readable. Once pytest
has collected them, the child asks the evaluator (over a private pipe) to
delete them and waits until they are gone. This only stops test-phase code
from finding the files by path later. It does not stop collection-time code
from reading them.

The hygiene run of the workspace's own suite uses the same tripwire, without
the hidden-test directory.

This resists *accidental* interference by workspace files (conftest hooks,
``addopts``, plugins, shadowed modules, early exits) and casual attempts to
read or write outside the allowlist. It is not a sandbox and does not resist
*deliberate* forgery: workspace code runs inside the test process and could,
for instance, rewrite the report from an ``atexit`` hook or attack the
in-process hook itself. That still requires an OS sandbox for the test
process (see docs/milestone-1-design.md §10 and ``harness.tripwire``).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from evaluation.ground_truth import GroundTruth, RemediationAlternative
from harness import tripwire as _tripwire_module

PYTEST_TIMEOUT_S = 180
# -P: don't put cwd/script dir on sys.path; -s: no user site; -B: no bytecode.
# (Not -I/-E: the environment below is constructed from scratch and must apply.)
_PY_FLAGS = ("-P", "-s", "-B")
_TRIPWIRE_COPY = "_tab_tripwire.py"

# Prologue shared by both bootstraps. ``_guard`` is called after ``import pytest``
# and before the snapshot is put on sys.path.
_GUARD = """\
import os
import sys


def _guard(boot_dir, read_roots, write_roots):
    import linecache
    import sysconfig

    sys.path.insert(0, boot_dir)
    try:
        import _tab_tripwire
    finally:
        sys.path.remove(boot_dir)
        sys.path_importer_cache.pop(boot_dir, None)
    # Cache the tripwire's source now: a traceback through it must not read boot_dir later.
    linecache.getlines(_tab_tripwire.__file__)
    paths = sysconfig.get_paths()
    reads = list(read_roots) + ["/usr/share/zoneinfo"]
    reads += [paths[k] for k in ("stdlib", "platstdlib", "purelib", "platlib") if paths.get(k)]
    _tab_tripwire.install(reads, write_roots)
    del sys.modules["_tab_tripwire"]
    real = [os.path.realpath(r) for r in reads + list(write_roots)]

    def allowed(entry):
        if not entry:
            return False
        p = os.path.realpath(entry)
        return any(p == r or p.startswith(r.rstrip(os.sep) + os.sep) for r in real)

    # Entries outside the allowlist could only fail with PermissionError on import.
    sys.path[:] = [p for p in sys.path if allowed(p)]
    sys.path_importer_cache.clear()


"""

_BOOTSTRAP = _GUARD + """\
import pytest
boot, snapshot, ini, rootdir, junit, home, req_fd, ack_fd = sys.argv[1:9]
hidden = sys.argv[9:]
del sys.argv[1:]
req_fd, ack_fd = int(req_fd), int(ack_fd)


class _UnlinkAfterCollection:
    # Once collected, the hidden test files are deleted by the evaluator (the tripwire forbids
    # writes here), so test-phase code cannot find them by path. Workspace modules imported by
    # the hidden tests have already run during collection.
    @staticmethod
    def pytest_collection_finish(session):
        os.write(req_fd, b"u")
        os.read(ack_fd, 1)


out = os.path.dirname(junit)
_guard(boot, [snapshot, rootdir, os.path.dirname(ini), out], [out, home])
sys.path.append(snapshot)
sys.exit(pytest.main(["-c", ini, "--rootdir", rootdir, "-p", "no:cacheprovider", "-q",
                      "--junitxml", junit, "--noconftest", *hidden], plugins=[_UnlinkAfterCollection()]))
"""
_HYGIENE_BOOTSTRAP = _GUARD + """\
import pytest
boot, snapshot, junit, home = sys.argv[1:5]
targets = sys.argv[5:]
del sys.argv[1:]
out = os.path.dirname(junit)
_guard(boot, [snapshot, out], [out, home])
sys.path.append(snapshot)
sys.exit(pytest.main(["--rootdir", snapshot, "-p", "no:cacheprovider", "-q", "--junitxml", junit, *targets]))
"""


def _scratch(tmp: Path) -> tuple[Path, Path, Path]:
    """Create ``(boot, out, home)`` under ``tmp``. The child can write only to ``out`` and ``home``.

    ``boot`` holds a read-only copy of the tripwire, so the child imports
    nothing from the benchmark's source tree.
    """
    boot, out, home = tmp / "boot", tmp / "out", tmp / "home"
    for d in (boot, out, home):
        d.mkdir()
    copy = boot / _TRIPWIRE_COPY
    copy.write_bytes(
        Path(_tripwire_module.__file__).read_bytes()
        + b"\n__tracebackhide__ = True  # appended by evaluation.checks for pytest reports\n"
    )
    os.chmod(copy, 0o444)
    return boot, out, home


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


def _run(cmd: list[str], cwd: Path, home: Path, pass_fds: tuple[int, ...] = ()) -> int | None:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=_env(home),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PYTEST_TIMEOUT_S,
            pass_fds=pass_fds,
        )
    except subprocess.TimeoutExpired:
        return None
    return proc.returncode


def _serve_unlink(req_r: int, ack_w: int, paths: list[str]) -> None:
    """When the child asks (once, after collection), delete ``paths`` and acknowledge."""
    try:
        if os.read(req_r, 1):
            for path in paths:
                if os.path.isfile(path):
                    os.unlink(path)
            os.write(ack_w, b"k")
    except OSError:
        pass  # the child is gone; the temporary directory is removed anyway


def _run_hidden_child(args: list[str], hidden: list[str], cwd: Path, home: Path) -> int | None:
    """Run the hidden-test bootstrap with ``args``, serving its post-collection unlink request."""
    req_r, req_w = os.pipe()
    ack_r, ack_w = os.pipe()
    server = threading.Thread(target=_serve_unlink, args=(req_r, ack_w, hidden), daemon=True)
    try:
        server.start()
        return _run(
            [sys.executable, *_PY_FLAGS, "-c", _BOOTSTRAP, *args, str(req_w), str(ack_r), *hidden],
            cwd=cwd,
            home=home,
            pass_fds=(req_w, ack_r),
        )
    finally:
        os.close(req_w)  # the child has exited: the server's read now sees EOF
        os.close(ack_r)
        server.join()
        os.close(req_r)
        os.close(ack_w)


def run_hidden_pytest(check: dict[str, Any], snapshot: Path, gt: GroundTruth) -> dict[str, Any]:
    expected = sum(gt.hidden_test_counts[rel] for rel in check["files"])
    with tempfile.TemporaryDirectory(prefix="tab-hidden-") as tmp:
        tmp_path = Path(tmp)
        boot, out, home = _scratch(tmp_path)
        hidden_dir = tmp_path / "hidden"
        cfg = tmp_path / "cfg"
        hidden_dir.mkdir()
        cfg.mkdir()
        targets = []
        for rel in check["files"]:
            dest = hidden_dir / Path(rel).name
            dest.write_bytes(gt.file_bytes(rel))
            targets.append(str(dest))
        ini = cfg / "pytest.ini"
        ini.write_text("[pytest]\naddopts =\n", encoding="utf-8")
        junit = out / "junit.xml"
        code = _run_hidden_child(
            [str(boot), str(snapshot), str(ini), str(hidden_dir), str(junit), str(home)], targets, cwd=home, home=home
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
    not tamper-proof. It runs under the same tripwire as hidden tests: reads
    under the snapshot, stdlib and site-packages; writes only to the checker's
    private ``HOME``/``TMPDIR`` (pytest's ``tmp_path`` lives there), not into
    the snapshot.
    """
    with tempfile.TemporaryDirectory(prefix="tab-hygiene-") as tmp:
        existing = [t for t in targets if (snapshot / t).exists()]
        if not existing:
            return {"passed": False, "detail": {"exit_code": None, "reason": "no test directory"}}
        boot, out, home = _scratch(Path(tmp))
        junit = out / "junit.xml"
        code = _run(
            [sys.executable, *_PY_FLAGS, "-c", _HYGIENE_BOOTSTRAP, str(boot), str(snapshot), str(junit), str(home),
             *existing],
            cwd=snapshot,
            home=home,
        )
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
