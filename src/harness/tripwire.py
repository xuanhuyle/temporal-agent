"""Allowlist tripwire for a whole child process (contestant workers and commands).

``install()`` adds a permanent audit hook to the *current* process:

- **reads** (``open`` for reading, directory listings, globbing) are allowed
  only under ``read_roots`` or ``write_roots``;
- **writes** (``open`` for writing, mkdir/remove/rename/chmod/..., sqlite files)
  only under ``write_roots``;
- **network**: socket creation, connect, bind and name resolution are refused
  unless ``allow_network``;
- **processes**: ``subprocess``, ``os.system``/``exec*``/``spawn*``/``fork``,
  ``posix_spawn`` and ``multiprocessing`` are refused unless ``allow_processes``;
- **signals**: signalling any process other than this one is refused;
- **ctypes**: loading libraries and raw memory access are refused unless
  ``allow_ctypes``.

Every refusal raises :class:`TripwireViolation` (a ``PermissionError``) and is
recorded; ``violations()`` returns the record.

This is a tripwire, not a sandbox. It runs inside the process it watches. It
stops accidental access and casual attempts, such as an indexer walking the
filesystem, a library opening a network connection, or a stray subprocess.
It cannot stop code that is deliberately hostile and attacks the
interpreter itself, for example by modifying the hook's closure through
``gc``, or through a C extension that does not raise audit events. See
``docs/milestone-2-design.md`` for what the process boundary does and does
not guarantee.

This module imports only the standard library; it is copied into contestant
processes and command bootstraps.
"""

from __future__ import annotations

import _posixsubprocess  # type: ignore[import-not-found]
import os
import sys
from typing import Callable, Iterable

__all__ = ["TripwireViolation", "install", "violations", "installed"]


class TripwireViolation(PermissionError):
    """The process tried something outside its allowlist."""


_state: dict[str, object] = {"installed": False, "violations": []}

_READ_EVENTS = {
    "os.listdir": 1,
    "os.scandir": 1,
    "os.listxattr": 1,
    "os.getxattr": 1,
    "glob.glob": 1,
    "glob.glob/2": 1,
    "pathlib.Path.glob": 1,
    "pathlib.Path.rglob": 1,
    "os.chdir": 1,
}
_WRITE_EVENTS = {
    "os.mkdir": 1,
    "os.remove": 1,
    "os.rmdir": 1,
    "os.rename": 2,
    "os.truncate": 1,
    "os.utime": 1,
    "os.chmod": 1,
    "os.chown": 1,
    "os.chflags": 1,
    "os.symlink": 2,
    "os.link": 2,
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
    "sqlite3.connect": 1,
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
_NETWORK_EVENTS = {
    "socket.__new__",
    "socket.connect",
    "socket.bind",
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyaddr",
    "socket.gethostbyname_ex",
    "socket.sendto",
    "socket.sendmsg",
}
_CTYPES_EVENTS = {
    "ctypes.dlopen",
    "ctypes.dlsym",
    "ctypes.dlsym/handle",
    "ctypes.cdata",
    "ctypes.cdata/buffer",
    "ctypes.call_function",
    "ctypes.create_string_buffer",
    "ctypes.create_unicode_buffer",
    "ctypes.string_at",
    "ctypes.wstring_at",
    "ctypes.set_errno",
    "ctypes.get_errno",
}
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_ALWAYS_READABLE = ("/dev/null", "/dev/urandom", "/dev/random", "/dev/zero")
_ALWAYS_WRITABLE = ("/dev/null",)


def installed() -> bool:
    return bool(_state["installed"])


def violations() -> list[str]:
    return list(_state["violations"])  # type: ignore[arg-type]


def _norm(roots: Iterable[str]) -> tuple[str, ...]:
    out = []
    for r in roots:
        if r:
            out.append(os.path.realpath(r))
    return tuple(sorted(set(out)))


def install(
    read_roots: Iterable[str],
    write_roots: Iterable[str],
    *,
    allow_network: bool = False,
    allow_processes: bool = False,
    allow_ctypes: bool = False,
    report: Callable[[str], None] | None = None,
) -> None:
    """Install the tripwire for the rest of this process's life (idempotent: only the first call counts)."""
    if _state["installed"]:
        return
    reads = _norm(read_roots) + tuple(_ALWAYS_READABLE)
    writes = _norm(write_roots)
    record: list[str] = _state["violations"]  # type: ignore[assignment]
    realpath, fsdecode, readlink, getpid = os.path.realpath, os.fsdecode, os.readlink, os.getpid
    sep = os.sep

    def within(path: str, roots: tuple[str, ...]) -> bool:
        for r in roots:
            if path == r or path.startswith(r.rstrip(sep) + sep):
                return True
        return False

    def resolve(raw: object) -> str | None:
        if raw is None or isinstance(raw, bool):
            return None
        if isinstance(raw, int):
            return None  # an fd this process already opened (opening it was checked)
        try:
            return realpath(fsdecode(raw))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def refuse(event: str, detail: str) -> None:
        msg = f"{event}: {detail}"
        record.append(msg)
        if report is not None:
            try:
                report(msg)
            except Exception:  # noqa: BLE001 - reporting must never mask the refusal
                pass
        raise TripwireViolation(f"{event}: not allowed in this process ({detail})")

    def check(event: str, raw: object, write: bool) -> None:
        path = resolve(raw)
        if path is None:
            return
        if write:
            if within(path, writes) or path in _ALWAYS_WRITABLE:
                return
            if path.endswith((".pyc", ".pyc.tmp")) or f"{sep}__pycache__" in path:
                return  # bytecode caches (normally disabled with -B)
            refuse(event, "write outside the allowed directories")
        else:
            if within(path, reads) or within(path, writes):
                return
            refuse(event, "read outside the allowed directories")

    def hook(event: str, args: tuple) -> None:
        if event == "open":
            raw = args[0] if args else None
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else 0
            write = bool((isinstance(mode, str) and any(c in mode for c in "wax+")) or (flags or 0) & _WRITE_FLAGS)
            check(event, raw, write)
            return
        n = _READ_EVENTS.get(event)
        if n is not None:
            for raw in args[:n]:
                check(event, raw, False)
            return
        n = _WRITE_EVENTS.get(event)
        if n is not None:
            if event == "sqlite3.connect" and args and args[0] in (":memory:", b":memory:", ""):
                return
            for raw in args[:n]:
                check(event, raw, True)
            return
        if event in _PROCESS_EVENTS and not allow_processes:
            refuse(event, "starting processes")
        if event in _NETWORK_EVENTS and not allow_network:
            refuse(event, "network access")
        if event in _CTYPES_EVENTS and not allow_ctypes:
            refuse(event, "ctypes")
        if event in ("os.kill", "os.killpg") and args:
            if event == "os.killpg" or args[0] != getpid():
                refuse(event, "signalling other processes")

    original_fork_exec = _posixsubprocess.fork_exec

    def guarded_fork_exec(*a, **k):  # type: ignore[no-untyped-def]
        if not allow_processes:
            refuse("_posixsubprocess.fork_exec", "starting processes")
        return original_fork_exec(*a, **k)

    sys.addaudithook(hook)
    _posixsubprocess.fork_exec = guarded_fork_exec
    _state["installed"] = True
    del readlink
