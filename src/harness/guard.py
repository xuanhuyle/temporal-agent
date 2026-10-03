"""In-process tripwire against accidental out-of-band filesystem access.

While an agent call (setup/on_start/on_event/teardown) is running, a Python
audit hook refuses:

- opening, listing, creating, renaming or deleting anything under a denied
  root: evaluator ground truth, the event stream (future events), scenario
  manifests, run outputs, every agent workspace (workspaces are reached
  through the traced ToolBox only), and other agents' private state;
- starting subprocesses (which would escape the hook).

ToolBox operations run with the guard suspended. This prevents *accidental*
access (e.g. a memory indexer walking the repository). It is not a security
sandbox against deliberately hostile code in the same process; process-level
isolation is planned before real contestants run.
"""

from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

_state = threading.local()
_installed = False
_install_lock = threading.Lock()

# Audit events whose leading arguments are paths.
_PATH_EVENTS = {
    "open": 1,
    "os.listdir": 1,
    "os.scandir": 1,
    "os.chdir": 1,
    "os.mkdir": 1,
    "os.remove": 1,
    "os.rmdir": 1,
    "os.rename": 2,
    "os.truncate": 1,
    "os.utime": 1,
    "os.chmod": 1,
    "os.chown": 1,
    "os.symlink": 2,
    "os.link": 2,
    "os.chflags": 1,
    "os.listxattr": 1,
    "os.getxattr": 1,
    "os.setxattr": 1,
    "os.removexattr": 1,
    "shutil.copyfile": 2,
    "shutil.copymode": 2,
    "shutil.copystat": 2,
    "shutil.copytree": 2,
    "shutil.rmtree": 1,
    "shutil.move": 2,
    "shutil.make_archive": 1,
    "shutil.unpack_archive": 2,
    "glob.glob": 1,
    "glob.glob/2": 1,
    "pathlib.Path.glob": 1,
    "pathlib.Path.rglob": 1,
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


class GuardViolation(PermissionError):
    """An agent touched a protected path or tried to start a process outside the ToolBox."""


class _Policy:
    def __init__(self, denied: Sequence[Path], allowed: Sequence[Path]) -> None:
        self.denied = tuple(os.path.realpath(p) for p in denied)
        self.allowed = tuple(os.path.realpath(p) for p in allowed)
        self.violations: list[str] = []

    @staticmethod
    def _within(path: str, root: str) -> bool:
        return path == root or path.startswith(root.rstrip(os.sep) + os.sep)

    def check(self, raw: object, event: str) -> None:
        if isinstance(raw, int) or raw is None:
            return
        try:
            path = os.path.realpath(os.fsdecode(raw))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        if any(self._within(path, a) for a in self.allowed):
            return
        if any(self._within(path, d) for d in self.denied):
            self.violations.append(event)
            raise GuardViolation(f"{event}: direct access to a protected path is not allowed; use the ToolBox")


def _hook(event: str, args: tuple) -> None:
    policy: _Policy | None = getattr(_state, "policy", None)
    if policy is None:
        return
    if event in _PROCESS_EVENTS:
        policy.violations.append(event)
        raise GuardViolation(f"{event}: starting processes is not allowed during agent calls")
    n = _PATH_EVENTS.get(event)
    if n:
        for raw in args[:n]:
            policy.check(raw, event)


def install() -> None:
    global _installed
    with _install_lock:
        if not _installed:
            sys.addaudithook(_hook)
            _installed = True


@contextmanager
def agent_call(denied: Sequence[Path], allowed: Sequence[Path], cwd: Path) -> Iterator[_Policy]:
    """Run an agent call with ``cwd`` as working directory and the tripwire armed."""
    install()
    previous_policy = getattr(_state, "policy", None)
    previous_cwd = os.getcwd()
    os.chdir(cwd)
    policy = _Policy(denied, allowed)
    _state.policy = policy
    try:
        yield policy
    finally:
        _state.policy = previous_policy
        os.chdir(previous_cwd)


@contextmanager
def suspended() -> Iterator[None]:
    """Disarm the tripwire for harness work done on an agent's behalf (tool calls)."""
    previous = getattr(_state, "policy", None)
    _state.policy = None
    try:
        yield
    finally:
        _state.policy = previous
