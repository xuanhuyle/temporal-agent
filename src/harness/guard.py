"""In-process tripwire against accidental out-of-band filesystem and process access.

While a run is armed, a process-wide Python audit hook checks every file and
process operation made by *agent code*:

- agent code is the harness thread while it is inside an agent call
  (``setup``/``on_start``/``on_event``/``teardown``/``describe``), and every
  thread started (directly or transitively) from agent code; such threads are
  attributed to the agent that started them;
- agent code may not read, list, or write anything under a denied root:
  evaluator ground truth, the event stream (future events), scenario
  manifests, run outputs (current and default run directories), every agent
  workspace (workspaces are reached through the traced ToolBox only), other
  agents' private state, and evaluator scratch space;
- agent code may *write* only inside its own private state directory
  (``HOME``, ``TMPDIR`` and ``XDG_*`` point inside it during agent calls), so
  memory cannot persist across runs and contaminate a later run;
- agent code may not start processes (``subprocess``, ``os.system``, ``fork``,
  ``posix_spawn``, ``multiprocessing`` spawn/forkserver via ``fork_exec``).

Harness work (tool implementations, recording) runs with the guard bypassed
on the harness thread only. Directory file descriptors are resolved through
``/proc/self/fd`` so ``dir_fd``-relative walks are checked too.

This prevents *accidental* access (e.g. a memory indexer walking the
repository, a cache under ``~/.cache``). It is not a security sandbox against
deliberately hostile code in the same process (ctypes, gc introspection,
threads started through ``_thread`` directly, ...); process-level isolation is
planned before real contestants run.
"""

from __future__ import annotations

import _posixsubprocess  # type: ignore[import-not-found]
import os
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence

_installed = False
_install_lock = threading.Lock()
_local = threading.local()  # .lane (str | None), .bypass (bool)


class GuardViolation(PermissionError):
    """Agent code touched a protected path, wrote outside its state, or tried to start a process."""


# Audit events: name -> (number of leading path args, is_write)
_PATH_EVENTS: dict[str, tuple[int, bool]] = {
    "open": (1, False),  # write intent decided from mode/flags below
    "os.listdir": (1, False),
    "os.scandir": (1, False),
    "os.chdir": (1, False),
    "os.listxattr": (1, False),
    "os.getxattr": (1, False),
    "glob.glob": (1, False),
    "glob.glob/2": (1, False),
    "pathlib.Path.glob": (1, False),
    "pathlib.Path.rglob": (1, False),
    "sqlite3.connect": (1, True),
    "os.mkdir": (1, True),
    "os.remove": (1, True),
    "os.rmdir": (1, True),
    "os.rename": (2, True),
    "os.truncate": (1, True),
    "os.utime": (1, True),
    "os.chmod": (1, True),
    "os.chown": (1, True),
    "os.chflags": (1, True),
    "os.symlink": (2, True),
    "os.link": (2, True),
    "os.setxattr": (1, True),
    "os.removexattr": (1, True),
    "shutil.copyfile": (2, True),
    "shutil.copymode": (2, True),
    "shutil.copystat": (2, True),
    "shutil.copytree": (2, True),
    "shutil.rmtree": (1, True),
    "shutil.move": (2, True),
    "shutil.make_archive": (1, True),
    "shutil.unpack_archive": (2, True),
}
_PROCESS_EVENTS = {
    "subprocess.Popen",
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "os.fork",
    "os.forkpty",
    "pty.spawn",
}
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_ENV_KEYS = ("HOME", "TMPDIR", "TEMP", "TMP", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME")


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


@dataclass
class _RunPolicy:
    harness_ident: int
    denied: tuple[str, ...]
    states: dict[str, str] = field(default_factory=dict)
    violations: dict[str, list[str]] = field(default_factory=dict)

    def record(self, lane: str, what: str) -> None:
        self.violations.setdefault(lane, []).append(what)


_policy: _RunPolicy | None = None


def _resolve(raw: object) -> str | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        try:
            return os.readlink(f"/proc/self/fd/{raw}")
        except OSError:
            return None
    try:
        return os.path.realpath(os.fsdecode(raw))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_bytecode_cache(path: str) -> bool:
    return path.endswith((".pyc", ".pyc.tmp")) or f"{os.sep}__pycache__" in path


def _current_lane(policy: _RunPolicy) -> str | None:
    """The agent a call is attributed to, or None for harness work."""
    if getattr(_local, "bypass", False):
        return None
    lane = getattr(_local, "lane", None)
    if lane is not None:
        return lane
    owner = getattr(threading.current_thread(), "_tab_owner", None)
    if owner is not None and owner[0] is policy:
        return owner[1]
    if threading.get_ident() == policy.harness_ident:
        return None
    # A thread of unknown origin (or left over from an earlier run) while a run is armed: most restrictive.
    return "<unattributed>"


def _check_path(policy: _RunPolicy, lane: str, event: str, raw: object, write: bool) -> None:
    path = _resolve(raw)
    if path is None:
        return
    state = policy.states.get(lane)
    if state is not None and _within(path, state):
        return
    if any(_within(path, d) for d in policy.denied):
        policy.record(lane, event)
        raise GuardViolation(f"{event}: direct access to a protected path is not allowed; use the ToolBox")
    if write and not _is_bytecode_cache(path):
        policy.record(lane, event)
        raise GuardViolation(f"{event}: agents may only write inside their private state directory")


def _hook(event: str, args: tuple) -> None:
    policy = _policy
    if policy is None:
        return
    if event in _PROCESS_EVENTS or event in _PATH_EVENTS:
        lane = _current_lane(policy)
        if lane is None:
            return
        if event in _PROCESS_EVENTS:
            policy.record(lane, event)
            raise GuardViolation(f"{event}: starting processes is not allowed during agent calls")
        n, write = _PATH_EVENTS[event]
        if event == "open":
            mode, flags = (args[1] if len(args) > 1 else None), (args[2] if len(args) > 2 else 0)
            write = bool((isinstance(mode, str) and any(c in mode for c in "wax+")) or (flags or 0) & _WRITE_FLAGS)
        for raw in args[:n]:
            _check_path(policy, lane, event, raw, write)


_original_start = threading.Thread.start
_original_fork_exec = _posixsubprocess.fork_exec


def _attributed_start(self: threading.Thread) -> None:
    policy = _policy
    if policy is not None:
        lane = _current_lane(policy)
        if lane is not None:
            self._tab_owner = (policy, lane)  # type: ignore[attr-defined]
    return _original_start(self)


def _guarded_fork_exec(*args, **kwargs):  # type: ignore[no-untyped-def]
    policy = _policy
    if policy is not None:
        lane = _current_lane(policy)
        if lane is not None:
            policy.record(lane, "_posixsubprocess.fork_exec")
            raise GuardViolation("starting processes is not allowed during agent calls")
    return _original_fork_exec(*args, **kwargs)


def install() -> None:
    global _installed
    with _install_lock:
        if not _installed:
            sys.addaudithook(_hook)
            threading.Thread.start = _attributed_start  # type: ignore[method-assign]
            _posixsubprocess.fork_exec = _guarded_fork_exec
            _installed = True


@contextmanager
def armed(denied: Sequence[Path]) -> Iterator[_RunPolicy]:
    """Arm the guard for a whole run (from the first agent call to after teardown)."""
    global _policy
    install()
    if _policy is not None:
        raise RuntimeError("a guarded run is already in progress in this process")
    _policy = _RunPolicy(
        harness_ident=threading.get_ident(), denied=tuple(sorted({os.path.realpath(p) for p in denied}))
    )
    try:
        yield _policy
    finally:
        _policy = None


def register_lane(lane: str, state_dir: Path) -> None:
    assert _policy is not None, "guard is not armed"
    _policy.states[lane] = os.path.realpath(state_dir)


def lane_env(state_dir: Path) -> dict[str, str]:
    """Environment overrides that keep an agent's caches and temp files in its state dir."""
    home = Path(state_dir) / ".home"
    tmp = Path(state_dir) / ".tmp"
    return {
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "TEMP": str(tmp),
        "TMP": str(tmp),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
    }


@contextmanager
def agent_call(lane: str, cwd: Path, env: dict[str, str] | None = None) -> Iterator[list[str]]:
    """Run agent code for ``lane``: cwd and environment redirected, guard enforced.

    Yields the list that will hold the violations recorded for this lane during
    the call (including from its background threads); it is filled in on exit,
    whether or not the call raised.
    """
    import tempfile

    assert _policy is not None, "guard is not armed"
    policy = _policy
    before = len(policy.violations.get(lane, []))
    previous_lane = getattr(_local, "lane", None)
    previous_cwd = os.getcwd()
    previous_env = {k: os.environ.get(k) for k in _ENV_KEYS}
    previous_tempdir = tempfile.tempdir
    for value in (env or {}).values():
        Path(value).mkdir(parents=True, exist_ok=True)
    os.environ.update(env or {})
    if env and "TMPDIR" in env:
        tempfile.tempdir = env["TMPDIR"]
    os.chdir(cwd)
    _local.lane = lane
    collected: list[str] = []
    try:
        yield collected
    finally:
        _local.lane = previous_lane
        os.chdir(previous_cwd)
        tempfile.tempdir = previous_tempdir
        for k, v in previous_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        collected.extend(policy.violations.get(lane, [])[before:])


@contextmanager
def bypass() -> Iterator[None]:
    """Harness work done on an agent's behalf (tool calls) on the harness thread."""
    previous = getattr(_local, "bypass", False)
    _local.bypass = True
    try:
        yield
    finally:
        _local.bypass = previous


def live_agent_threads() -> dict[str, int]:
    """Threads started by agent code during the armed run that are still alive, per lane."""
    out: dict[str, int] = {}
    policy = _policy
    if policy is None:
        return out
    for t in threading.enumerate():
        owner = getattr(t, "_tab_owner", None)
        if owner is not None and owner[0] is policy and t.is_alive():
            out[owner[1]] = out.get(owner[1], 0) + 1
    return out
