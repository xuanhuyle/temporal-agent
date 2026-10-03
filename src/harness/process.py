"""Harness-side proxy for a contestant running in its own process (protocol amendment A4).

:class:`ProcessAgent` implements the ordinary ``harness.agent.Agent``
interface, so the runner drives it like any in-process agent. Every agent call
is forwarded over pipes (``harness.wire``) to a contestant process started
from ``harness/worker.py``. While a call is in progress, the proxy executes
the contestant's tool requests on the step's real ``ToolBox``, so budgets,
recording and metering are exactly as for in-process agents.

Lane layout (the runner creates ``state/`` and ``workspace/``)::

    <lane>/state/       the agent's private, persistent state dir (cwd of the process)
    <lane>/workspace/   reached only through the ToolBox, never by the process
    <lane>/bundle/      read-only copy of the contestant-side code (see build_bundle)
    <lane>/logs/        stdout.log, stderr.log (appended across restarts)

Wall clock: ``on_start``/``on_event`` get ``budget.wall_clock_s_per_event``;
``setup``/``teardown``/``describe`` get :data:`CONTROL_TIMEOUT_S`. On expiry the
process group is killed and :class:`StepTimeout` is raised; on an unexpected
exit :class:`ContestantCrashed`. Before the next call a fresh process is
started and ``setup`` re-run with ``restart_count + 1``, so the agent resumes
from its persistent state.

See ``docs/milestone-2-design.md`` §6 for what this boundary does and does
not protect. It is not an OS sandbox.
"""

from __future__ import annotations

import dataclasses
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Sequence, TypeVar

import harness
from harness import guard
from harness.agent import (
    Agent,
    AgentContext,
    AgentEvent,
    AgentResponse,
    InvalidAction,
    ModelSettings,
    StepBudget,
    Usage,
    action_from_dict,
)
from harness.canonical import canonical_json, copy_tree, tree_hash
from harness.errors import ERROR_TYPES, BudgetExceeded, ToolError
from harness.llm import EmbeddingResponse, ModelResponse
from harness.wire import WIRE_VERSION, FrameReader, WireError, WireTimeout, encode
from harness.worker import stdlib_roots

__all__ = [
    "ProcessAgent",
    "StepTimeout",
    "ContestantCrashed",
    "ContestantProtocolError",
    "ContestantError",
    "InvalidContestantResponse",
    "build_bundle",
    "BUNDLE_HARNESS_MODULES",
    "CONTROL_TIMEOUT_S",
]

SRC_ROOT = Path(harness.__file__).resolve().parents[1]

# The only harness modules a contestant process gets (docs/milestone-2-design.md §1).
BUNDLE_HARNESS_MODULES = ("__init__", "agent", "errors", "llm", "tool_specs", "wire", "tripwire", "worker")
# Package names that would shadow or smuggle in benchmark code.
RESERVED_PACKAGE_NAMES = frozenset({"harness", "evaluation"})

CONTROL_TIMEOUT_S = 120.0  # setup / teardown / describe (and a restart's setup)
SHUTDOWN_GRACE_S = 5.0  # how long a process may take to exit after "shutdown"
_POLL_S = 0.005


# ----------------------------------------------------------------- exceptions
class StepTimeout(BaseException):
    """The call's wall-clock budget ran out; the contestant process group was killed.

    A ``BaseException`` (like ``BudgetExceeded``) so that it is never mistaken
    for an ordinary agent error.
    """


class ContestantCrashed(Exception):
    """The contestant process exited (or broke the protocol) in the middle of a call."""

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class ContestantProtocolError(ContestantCrashed):
    """The contestant process sent something that is not a valid ``tab.wire/1`` message; it was killed."""


class ContestantError(Exception):
    """Base of exceptions re-raised from the contestant process.

    The concrete class is created on the fly and named after the child's
    exception type (``ValueError``, ``TripwireViolation``, ...); ``str(exc)``
    is the child's message and ``child_traceback`` its traceback text.
    """

    child_traceback: str = ""


class InvalidContestantResponse(TypeError):
    """``on_event`` in the contestant process returned something other than a valid ``AgentResponse``."""


_ERROR_CLASSES: dict[str, type[ContestantError]] = {}


def _contestant_error_class(type_name: object) -> type[ContestantError]:
    name = type_name if isinstance(type_name, str) and type_name.isidentifier() and len(type_name) <= 128 else ""
    if not name:
        return ContestantError
    cls = _ERROR_CLASSES.get(name)
    if cls is None:
        cls = type(name, (ContestantError,), {"__module__": __name__, "__qualname__": name})
        _ERROR_CLASSES[name] = cls
    return cls


def _child_exception(msg: dict[str, Any]) -> BaseException:
    type_name = msg.get("type")
    message = msg.get("message")
    message = message if isinstance(message, str) else str(message)
    if type_name == "BudgetExceeded":
        return BudgetExceeded(message)
    exc = _contestant_error_class(type_name)(message)
    tb = msg.get("traceback")
    exc.child_traceback = tb if isinstance(tb, str) else ""
    return exc


# --------------------------------------------------------------------- bundle
def _resolve_packages(packages: Sequence[str | Path]) -> list[tuple[str, Path]]:
    """``(name, directory)`` for each contestant package; names under ``src/`` or explicit directories."""
    if isinstance(packages, (str, Path)):
        raise TypeError("packages must be a sequence of package names or directories")
    out: dict[str, Path] = {}
    for item in packages:
        if isinstance(item, Path):
            path = item.resolve()
            name = path.name
        elif isinstance(item, str):
            if not item.isidentifier():
                raise ValueError(f"invalid contestant package name: {item!r}")
            name, path = item, SRC_ROOT / item
        else:
            raise TypeError(f"contestant package must be a name or a Path, got {type(item).__name__}")
        if not name.isidentifier():
            raise ValueError(f"contestant package directory is not a valid package name: {name!r}")
        if name in RESERVED_PACKAGE_NAMES:
            raise ValueError(f"{name!r} cannot be bundled as a contestant package")
        if name in out:
            raise ValueError(f"contestant package {name!r} given twice")
        if not path.is_dir():
            raise ValueError(f"contestant package {name!r} not found")
        out[name] = path
    return sorted(out.items())


def _set_tree_mode(root: Path, *, writable: bool) -> None:
    """Make a tree read-only (files 0444, dirs 0555) or give directories back their write bit."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=not writable):
        current = Path(dirpath)
        if not writable:
            for f in filenames:
                p = current / f
                if not p.is_symlink():
                    os.chmod(p, 0o444)
        for d in dirnames:
            p = current / d
            if not p.is_symlink():
                os.chmod(p, 0o755 if writable else 0o555)
    os.chmod(root, 0o755 if writable else 0o555)


def _remove_tree(root: Path) -> None:
    if root.exists():
        try:
            _set_tree_mode(root, writable=True)
        except OSError:
            pass
        shutil.rmtree(root, ignore_errors=True)


def build_bundle(dest: Path, packages: Sequence[str | Path]) -> str:
    """Copy the contestant-side code into ``dest`` (which must not exist), read-only; return its tree hash.

    ``dest/harness/`` gets exactly :data:`BUNDLE_HARNESS_MODULES`; each package
    is copied to ``dest/<name>/`` (regular files only, without bytecode caches).
    No other harness module and nothing from ``evaluation`` is included.
    """
    resolved = _resolve_packages(packages)
    dest = Path(dest)
    dest.mkdir(parents=True)
    hdir = dest / "harness"
    hdir.mkdir()
    for module in BUNDLE_HARNESS_MODULES:
        shutil.copyfile(SRC_ROOT / "harness" / f"{module}.py", hdir / f"{module}.py")
    for name, path in resolved:
        copy_tree(path, dest / name, regular_only=True)
    _set_tree_mode(dest, writable=False)
    return tree_hash(dest)


# ---------------------------------------------------------------------- child
class _ChannelTimeout(Exception):
    pass


class _ChannelClosed(Exception):
    pass


class _ChannelProtocol(Exception):
    pass


class _Child:
    """One running contestant process and the harness end of its pipes."""

    def __init__(self, proc: subprocess.Popen, wfd: int, rfd: int) -> None:
        self.proc = proc
        self.pid = proc.pid
        self._wfd = wfd
        self._rfd = rfd
        os.set_blocking(wfd, False)  # writes honour the deadline even if the child stops reading
        self._reader = FrameReader(rfd)
        self.reaped = False

    def send(self, obj: Any, deadline: float) -> None:
        data = memoryview(encode(obj))
        while data:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _ChannelTimeout()
            _, writable, _ = select.select([], [self._wfd], [], remaining)
            if not writable:
                raise _ChannelTimeout()
            try:
                n = os.write(self._wfd, data)
            except BlockingIOError:
                continue
            except OSError:
                raise _ChannelClosed() from None
            data = data[n:]

    def read(self, deadline: float) -> dict[str, Any]:
        try:
            return self._reader.read(deadline)
        except WireTimeout:
            raise _ChannelTimeout() from None
        except WireError:
            # FrameReader marks end-of-file before reporting it; anything else is a malformed message.
            if getattr(self._reader, "_eof", False):
                raise _ChannelClosed() from None
            raise _ChannelProtocol() from None
        except OSError:
            raise _ChannelClosed() from None

    def _exited(self) -> bool:
        """Whether the process has exited, without reaping it (its pid and group id stay reserved)."""
        if not hasattr(os, "waitid"):  # pragma: no cover - platforms without waitid: kill after the grace period
            return False
        try:
            return os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
        except ChildProcessError:
            return True

    def terminate(self, grace_s: float = 0.0) -> int:
        """Wait up to ``grace_s`` for a voluntary exit, kill the whole process group, reap; return the exit code."""
        if self.reaped:
            return self.proc.returncode
        end = time.monotonic() + grace_s
        while grace_s > 0 and not self._exited() and time.monotonic() < end:
            time.sleep(_POLL_S)
        # The leader is not reaped yet, so its process-group id cannot have been reused.
        try:
            os.killpg(self.pid, signal.SIGKILL)
        except OSError:
            pass
        code = self.proc.wait()
        self.reaped = True
        for fd in (self._wfd, self._rfd):
            try:
                os.close(fd)
            except OSError:
                pass
        return code


def _child_env(state_dir: Path) -> dict[str, str]:
    """The contestant's environment, built from scratch: no credentials, proxies or PYTHONPATH."""
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",  # logs stay complete when the process is killed
    }
    lane_env = guard.lane_env(state_dir)
    for key, value in lane_env.items():
        if key not in ("PWD", "OLDPWD"):
            Path(value).mkdir(parents=True, exist_ok=True)
    env.update(lane_env)
    return env


def _context_payload(ctx: AgentContext) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in dataclasses.fields(ctx):
        value = getattr(ctx, f.name)
        if isinstance(value, Path):
            value = str(value)
        elif isinstance(value, (StepBudget, ModelSettings)):
            value = value.to_dict()
        out[f.name] = value
    return out


def _error_type(exc: ToolError) -> str:
    for cls in type(exc).__mro__:
        if cls.__name__ in ERROR_TYPES and ERROR_TYPES[cls.__name__] is cls:
            return cls.__name__
    return "ToolError"


def _service_tool(msg: dict[str, Any], tools: Any) -> dict[str, Any]:
    """Execute one ``tool`` request on the step's real ToolBox and build the ``tool_result``."""
    rid = msg.get("id")

    def error(kind: str, message: str) -> dict[str, Any]:
        return {"op": "tool_result", "id": rid, "ok": False, "error": {"type": kind, "message": message}}

    name, args = msg.get("name"), msg.get("args")
    if tools is None:
        return error("ToolBoxClosed", "no tools are available during this call")
    if not isinstance(name, str) or not isinstance(args, dict):
        return error("ToolError", "malformed tool request")
    try:
        value = tools.call(name, **args)
    except BudgetExceeded as exc:
        return error("BudgetExceeded", str(exc))
    except ToolError as exc:
        return error(_error_type(exc), str(exc))
    except TypeError as exc:  # arguments that do not bind (the worker binds them first; only a forged request gets here)
        return error("ToolError", f"{name}: {exc}")
    if isinstance(value, (ModelResponse, EmbeddingResponse)):
        value = value.to_dict()
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return error("ToolError", f"{name}: result is not JSON-serializable")
    return {"op": "tool_result", "id": rid, "ok": True, "value": value}


def _service_budget(msg: dict[str, Any], tools: Any) -> dict[str, Any]:
    value = tools.budget_remaining() if tools is not None else {}
    return {"op": "budget_result", "id": msg.get("id"), "value": value}


def _exchange(
    child: _Child,
    method: str,
    payload: dict[str, Any],
    tools: Any,
    deadline: float,
    limit_s: float,
    violations: list[str],
) -> Any:
    """Run one call to completion; returns the child's value or raises its exception.

    If the call does not complete normally (timeout, exit, protocol error,
    or any exception in the harness while servicing it) the child is killed
    before the exception propagates, so a half-finished call never leaks
    into the next one.
    """
    completed = False
    try:
        child.send({"op": "call", "method": method, "payload": payload}, deadline)
        while True:
            msg = child.read(deadline)
            op = msg.get("op")
            if op == "tool":
                child.send(_service_tool(msg, tools), deadline)
            elif op == "budget":
                child.send(_service_budget(msg, tools), deadline)
            elif op in ("return", "raise"):
                reported = msg.get("violations")
                if isinstance(reported, list):
                    violations.extend(str(v) for v in reported)
                completed = True
                if op == "raise":
                    raise _child_exception(msg)
                return msg.get("value")
            else:
                raise _ChannelProtocol()
    except _ChannelTimeout:
        child.terminate()
        raise StepTimeout(
            f"{method} exceeded its wall-clock budget of {limit_s:g}s; the contestant process was killed"
        ) from None
    except _ChannelClosed:
        code = child.terminate(SHUTDOWN_GRACE_S)
        raise ContestantCrashed(
            f"contestant process exited unexpectedly during {method} (exit code {code})", code
        ) from None
    except _ChannelProtocol:
        code = child.terminate()
        raise ContestantProtocolError(
            f"contestant process broke the wire protocol during {method}; it was killed", code
        ) from None
    finally:
        if not completed and not child.reaped:
            child.terminate()


def _shutdown(child: _Child) -> int:
    """Ask an idle child to exit, then reap its whole process group; returns the exit code."""
    if child.reaped:
        return child.proc.returncode
    try:
        child.send({"op": "shutdown"}, time.monotonic() + SHUTDOWN_GRACE_S)
    except (_ChannelTimeout, _ChannelClosed):
        return child.terminate()
    return child.terminate(SHUTDOWN_GRACE_S)


_T = TypeVar("_T")


def _harness_side(fn: Callable[..., _T]) -> Callable[..., _T]:
    """Proxy work is harness work: it may start processes and touch the lane even inside a guarded agent call."""

    def wrapper(*args: Any, **kwargs: Any) -> _T:
        with guard.bypass():
            return fn(*args, **kwargs)

    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    wrapper.__doc__ = fn.__doc__
    return wrapper


# ---------------------------------------------------------------------- agent
class ProcessAgent(Agent):
    """Harness-side proxy for a contestant that runs in its own process.

    - ``entry``: ``"package.module:Class"``; the class is constructed in the
      child as ``Class(name=name, config=config)`` and must be a
      ``harness.agent.Agent``. Its package must be one of ``packages``.
    - ``config``: JSON-serializable configuration passed to the constructor.
    - ``packages``: contestant packages to bundle, as names of packages
      under the repository's ``src/`` or as package directories.

    ``last_violations`` holds the tripwire refusals the child reported during
    the most recent public call (including a restart's ``setup``).
    """

    isolation = "process"

    def __init__(
        self,
        name: str,
        *,
        kind: str,
        entry: str,
        config: dict[str, Any],
        packages: Sequence[str | Path],
        role: str = "contestant",
    ) -> None:
        super().__init__(name)
        self.kind = kind
        self.role = role
        if not isinstance(config, dict):
            raise TypeError("config must be a dict")
        canonical_json(config)  # must cross the wire
        self.config = config
        self._packages = _resolve_packages(packages)
        module, sep, cls = entry.partition(":")
        parts = module.split(".")
        if not sep or not cls.isidentifier() or not all(p.isidentifier() for p in parts):
            raise ValueError(f"entry must look like 'package.module:Class', got {entry!r}")
        if parts[0] not in dict(self._packages):
            raise ValueError(f"entry {entry!r} is not inside a bundled contestant package")
        self.entry = entry
        self.last_violations: list[str] = []
        self._description: dict[str, Any] | None = None
        self._bundle_sha256: str | None = None
        self._ctx: AgentContext | None = None
        self._lane: Path | None = None
        self._child: _Child | None = None
        self._needs_restart = False
        self._restarts = 0
        self._notices: list[dict[str, Any]] = []

    # ---------------------------------------------------------- properties
    @property
    def log_dir(self) -> Path | None:
        """``<lane>/logs`` (``stdout.log``, ``stderr.log``) once ``setup`` has run."""
        return None if self._lane is None else self._lane / "logs"

    @property
    def bundle_dir(self) -> Path | None:
        return None if self._lane is None else self._lane / "bundle"

    @property
    def pid(self) -> int | None:
        """The running contestant process, if any (never recorded in traces)."""
        return None if self._child is None else self._child.pid

    def drain_notices(self) -> list[dict[str, Any]]:
        """Lifecycle records since the last drain (pid- and path-free, deterministic)."""
        out, self._notices = self._notices, []
        return out

    # ------------------------------------------------------------ spawning
    def _spawn(self, state_dir: Path, bundle: Path, log_dir: Path, deadline: float, violations: list[str]) -> _Child:
        log_dir.mkdir(parents=True, exist_ok=True)
        env = _child_env(state_dir)
        p2c_r, p2c_w = os.pipe()
        c2p_r, c2p_w = os.pipe()
        argv = [sys.executable, "-S", "-s", "-B", "-P", str(bundle / "harness" / "worker.py"), str(p2c_r), str(c2p_w)]
        try:
            with open(log_dir / "stdout.log", "ab") as out, open(log_dir / "stderr.log", "ab") as err:
                proc = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    cwd=state_dir,
                    env=env,
                    start_new_session=True,
                    close_fds=True,
                    pass_fds=(p2c_r, c2p_w),
                )
        except BaseException:
            for fd in (p2c_r, p2c_w, c2p_r, c2p_w):
                os.close(fd)
            raise
        os.close(p2c_r)
        os.close(c2p_w)
        child = _Child(proc, wfd=p2c_w, rfd=c2p_r)
        init = {
            "op": "init",
            "wire": WIRE_VERSION,
            "entry": self.entry,
            "name": self.name,
            "config": self.config,
            "read_roots": [str(bundle.resolve())] + stdlib_roots(),
            "write_roots": [str(state_dir.resolve())],
        }
        ready = False
        try:
            child.send(init, deadline)
            msg = child.read(deadline)
            if msg.get("op") == "raise":
                reported = msg.get("violations")
                if isinstance(reported, list):
                    violations.extend(str(v) for v in reported)
                child.terminate(SHUTDOWN_GRACE_S)
                raise _child_exception(msg)
            if msg.get("op") != "ready" or msg.get("wire") != WIRE_VERSION:
                raise _ChannelProtocol()
            ready = True
            return child
        except _ChannelTimeout:
            child.terminate()
            raise StepTimeout(f"contestant process did not start within {CONTROL_TIMEOUT_S:g}s") from None
        except _ChannelClosed:
            code = child.terminate(SHUTDOWN_GRACE_S)
            raise ContestantCrashed(f"contestant process exited during startup (exit code {code})", code) from None
        except _ChannelProtocol:
            code = child.terminate()
            raise ContestantProtocolError("contestant process broke the wire protocol during startup", code) from None
        finally:
            if not ready and not child.reaped:
                child.terminate()

    def _start_lane(self, ctx: AgentContext) -> None:
        """Spawn the lane's process and run ``setup``; on failure no process is left running."""
        assert self._lane is not None
        deadline = time.monotonic() + CONTROL_TIMEOUT_S
        self._needs_restart = True  # until setup has succeeded
        child = self._spawn(ctx.state_dir, self._lane / "bundle", self._lane / "logs", deadline, self.last_violations)
        self._child = child
        self._notices.append({"event": "spawned", "restart_count": ctx.restart_count})
        try:
            self._call(child, "setup", _context_payload(ctx), None, deadline, CONTROL_TIMEOUT_S)
        except BaseException:
            self._kill()
            raise
        self._needs_restart = False

    def _call(
        self, child: _Child, method: str, payload: dict[str, Any], tools: Any, deadline: float, limit_s: float
    ) -> Any:
        """``_exchange`` plus lane bookkeeping when the process is lost."""
        try:
            return _exchange(child, method, payload, tools, deadline, limit_s, self.last_violations)
        except StepTimeout:
            self._lost({"event": "timeout", "method": method, "limit_s": limit_s})
            raise
        except ContestantProtocolError:
            self._lost({"event": "protocol_error", "method": method})
            raise
        except ContestantCrashed as exc:
            self._lost({"event": "crashed", "method": method, "exit_code": exc.exit_code})
            raise
        except BaseException:
            if child.reaped:  # killed by _exchange (e.g. Ctrl-C or a harness fault mid-call)
                self._lost({"event": "killed", "method": method})
            raise

    def _lost(self, notice: dict[str, Any]) -> None:
        self._notices.append(notice)
        self._child = None
        self._needs_restart = True

    def _kill(self) -> None:
        if self._child is not None:
            self._child.terminate()
            self._child = None

    def _ensure_child(self) -> _Child:
        if self._child is not None:
            return self._child
        if self._ctx is None:
            raise RuntimeError("setup() has not been called")
        if not self._needs_restart:
            raise RuntimeError("the contestant process has been shut down")
        self._restarts += 1
        ctx = dataclasses.replace(self._ctx, restart_count=self._ctx.restart_count + self._restarts)
        self._notices.append({"event": "restarted", "restart_count": ctx.restart_count})
        self.context = ctx
        self._start_lane(ctx)
        assert self._child is not None
        return self._child

    # ----------------------------------------------------------- interface
    @_harness_side
    def describe(self) -> dict[str, Any]:
        """``{kind, role, config, isolation, entry, bundle_sha256}``; ``config`` as the contestant reports it.

        Runs ``describe()`` in a short-lived process with its own temporary
        state dir and bundle; works before ``setup``. The result is cached.
        """
        if self._description is None:
            scratch = Path(tempfile.mkdtemp(prefix="tab-describe-"))
            try:
                state = scratch / "state"
                state.mkdir()
                sha = build_bundle(scratch / "bundle", [p for _, p in self._packages])
                deadline = time.monotonic() + CONTROL_TIMEOUT_S
                violations: list[str] = []
                child = self._spawn(state, scratch / "bundle", scratch / "logs", deadline, violations)
                try:
                    value = _exchange(child, "describe", {}, None, deadline, CONTROL_TIMEOUT_S, violations)
                finally:
                    _shutdown(child)
            finally:
                _remove_tree(scratch)
            if not isinstance(value, dict):
                raise InvalidContestantResponse(f"describe() must return a dict, got {type(value).__name__}")
            config = value.get("config", {})
            if not isinstance(config, dict):
                raise InvalidContestantResponse("describe()['config'] must be a dict")
            if self._bundle_sha256 is None:
                self._bundle_sha256 = sha
            self._description = {
                "kind": self.kind,
                "role": self.role,
                "config": config,
                "isolation": self.isolation,
                "entry": self.entry,
                "bundle_sha256": sha,
            }
        return {**self._description, "config": dict(self._description["config"])}

    @_harness_side
    def setup(self, context: AgentContext) -> None:
        if self._ctx is not None:
            raise RuntimeError("setup() has already been called on this ProcessAgent")
        super().setup(context)
        self.last_violations = []
        self._ctx = context
        self._lane = Path(context.state_dir).parent
        sha = build_bundle(self._lane / "bundle", [p for _, p in self._packages])
        if self._bundle_sha256 is not None and sha != self._bundle_sha256:
            raise RuntimeError("contestant code changed between describe() and setup()")
        self._bundle_sha256 = sha
        self._start_lane(context)

    @_harness_side
    def on_start(self, tools: Any) -> None:
        self.last_violations = []
        child = self._ensure_child()
        limit = self._step_limit()
        self._call(child, "on_start", {}, tools, time.monotonic() + limit, limit)

    @_harness_side
    def on_event(self, event: AgentEvent, tools: Any) -> AgentResponse:
        self.last_violations = []
        child = self._ensure_child()
        limit = self._step_limit()
        value = self._call(child, "on_event", {"event": event.to_dict()}, tools, time.monotonic() + limit, limit)
        return _parse_response(value)

    @_harness_side
    def teardown(self) -> None:
        """Run the contestant's ``teardown`` if its process is alive, then shut it down and reap it."""
        self.last_violations = []
        child = self._child
        try:
            if child is not None:
                try:
                    self._call(child, "teardown", {}, None, time.monotonic() + CONTROL_TIMEOUT_S, CONTROL_TIMEOUT_S)
                finally:
                    if self._child is not None:  # still running, whether teardown returned or raised
                        code = _shutdown(self._child)
                        self._child = None
                        self._notices.append({"event": "exited", "exit_code": code})
        finally:
            self.close()

    def close(self) -> None:
        """Kill the contestant process group if it is still running (idempotent)."""
        with guard.bypass():
            self._kill()
            self._needs_restart = False
            if self._lane is not None and (self._lane / "bundle").exists():
                # The process is gone; let ordinary cleanup of the lane remove the bundle.
                try:
                    _set_tree_mode(self._lane / "bundle", writable=True)
                except OSError:
                    pass

    def __del__(self) -> None:
        try:
            if getattr(self, "_child", None) is not None:
                self._kill()
        except Exception:  # noqa: BLE001 - best effort during garbage collection
            pass

    def _step_limit(self) -> float:
        assert self._ctx is not None
        return float(self._ctx.budget.wall_clock_s_per_event)


def _parse_response(value: Any) -> AgentResponse:
    if isinstance(value, dict) and "invalid" in value:
        raise InvalidContestantResponse(str(value["invalid"]))
    if not isinstance(value, dict) or not isinstance(value.get("actions"), list) or not isinstance(value.get("usage"), dict):
        raise InvalidContestantResponse("on_event returned a malformed response")
    try:
        actions = [action_from_dict(a) for a in value["actions"]]
        usage = Usage(**value["usage"])
    except (InvalidAction, KeyError, TypeError, AttributeError) as exc:
        raise InvalidContestantResponse(f"on_event returned an invalid response: {exc}") from None
    return AgentResponse(actions=actions, usage=usage)
