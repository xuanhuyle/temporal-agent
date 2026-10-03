"""Contestant-process main (``tab.wire/1`` peer of ``harness.process.ProcessAgent``).

This file is copied into the contestant bundle and started by the harness as::

    python -S -s -B -P <bundle>/harness/worker.py <read_fd> <write_fd>

with a constructed environment and the agent's ``state_dir`` as working
directory. In order, it:

1. confines ``sys.path`` to the bundle root plus the interpreter's standard
   library (before importing anything from the bundle);
2. reads the ``init`` message
   ``{"op": "init", "wire", "entry": "pkg.module:Class", "name", "config", "read_roots", "write_roots"}``;
3. installs ``harness.tripwire`` (reads under ``read_roots``, writes under
   ``write_roots``; no network, processes or ctypes). Refusals are collected
   and reported with the next ``return``/``raise`` message;
4. imports the entry point, constructs ``cls(name=name, config=config)`` and
   sends ``ready`` (or ``raise`` if any of this fails, then exits).

It then serves ``call`` messages until ``shutdown`` or the end of the
channel. During ``on_start``/``on_event`` the agent receives a
:class:`RemoteTools` whose every call is executed by the harness on the
step's real ``ToolBox`` (same budgets, recording and metering as in-process).

This module imports only the standard library and the contestant-side harness
modules (``agent``, ``errors``, ``llm``, ``tool_specs``, ``wire``, ``tripwire``).
"""

from __future__ import annotations

import os
import sys
import sysconfig


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def stdlib_roots() -> list[str]:
    """The interpreter's standard-library directories (pure and platform-specific)."""
    roots = {os.path.realpath(sysconfig.get_path(key)) for key in ("stdlib", "platstdlib")}
    return sorted(r for r in roots if r)


def _confine_sys_path() -> str:
    """Set ``sys.path`` to the bundle root plus standard-library entries; return the bundle root."""
    bundle = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    roots = stdlib_roots()
    zip_name = f"python{sys.version_info[0]}{sys.version_info[1]}.zip"
    keep = []
    for entry in sys.path:
        if not entry:
            continue  # "" means the working directory: never importable from
        real = os.path.realpath(entry)
        if any(_within(real, r) for r in roots) or os.path.basename(real) == zip_name:
            keep.append(entry)
    sys.path[:] = [bundle] + keep
    sys.path_importer_cache.clear()
    return bundle


if __name__ == "__main__":  # pragma: no cover - runs in the contestant process
    # Must happen before the bundle imports below: nothing outside the bundle
    # and the standard library may become importable.
    _confine_sys_path()

import importlib  # noqa: E402
import json  # noqa: E402
import threading  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, NoReturn  # noqa: E402

from harness import tripwire  # noqa: E402
from harness.agent import (  # noqa: E402
    ACTION_TYPES,
    Agent,
    AgentContext,
    AgentEvent,
    AgentResponse,
    ChangedPath,
    ModelSettings,
    StepBudget,
    Usage,
)
from harness.errors import ERROR_TYPES, BudgetExceeded, ToolBoxClosed, ToolError  # noqa: E402
from harness.llm import EmbeddingResponse, ModelRequest, ModelResponse  # noqa: E402
from harness.tool_specs import TOOL_SPECS, bind_args  # noqa: E402
from harness.wire import WIRE_VERSION, FrameReader, WireError, encode, write_message  # noqa: E402

__all__ = ["RemoteTools", "main", "stdlib_roots"]

EXIT_CHANNEL = 70  # the harness side of the channel misbehaved or went away


class _Channel:
    """The worker's end of the wire; requests are serialized so threads cannot interleave messages."""

    def __init__(self, rfd: int, wfd: int) -> None:
        self._reader = FrameReader(rfd)
        self._wfd = wfd
        self.lock = threading.RLock()
        self._next_id = 0

    def read(self) -> dict[str, Any]:
        return self._reader.read()

    def send(self, obj: Any) -> None:
        write_message(self._wfd, obj)

    def request(self, msg: dict[str, Any], expect: str) -> dict[str, Any]:
        """Send one ``tool``/``budget`` request and return the matching reply (caller holds ``lock``)."""
        self._next_id += 1
        rid = self._next_id
        try:
            self.send({**msg, "id": rid})
            reply = self.read()
        except (OSError, WireError):
            _die()
        if reply.get("op") != expect or reply.get("id") != rid:
            _die()
        return reply


def _die() -> NoReturn:
    """The harness is gone or broke the protocol: there is nobody left to answer to."""
    _flush()
    os._exit(EXIT_CHANNEL)


def _flush() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:  # noqa: BLE001 - best effort at exit
            pass


def _wire_value(value: Any) -> Any:
    """An argument as sent to the harness.

    JSON values pass through (tuples become lists). Anything else is replaced
    by the marker the in-process ToolBox records for it, so the harness still
    counts, traces and rejects the call exactly as it would in-process.
    """
    if isinstance(value, ModelRequest):
        return value.to_dict()
    try:
        json.dumps(value, ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return {"unrecordable_type": type(value).__name__}
    return value


class RemoteTools:
    """The step's ToolBox as seen from the contestant process.

    Has one method per entry of ``harness.tool_specs.TOOL_SPECS`` (same names,
    arguments and defaults as ``harness.tools.ToolBox``), plus :meth:`call`,
    :meth:`budget_remaining` and :attr:`calls_remaining`. Every call is
    executed in the harness. Errors arrive as the ``harness.errors`` classes;
    ``BudgetExceeded`` ends the step unless caught (and is recorded as
    ``budget_exceeded`` even then). Once the agent call that received this
    object has returned, every method raises ``ToolBoxClosed``.
    """

    def __init__(self, channel: _Channel) -> None:
        self._channel = channel
        self._closed = False
        self._exhausted = False

    @property
    def exhausted(self) -> bool:
        """True once a call has been refused for lack of budget."""
        return self._exhausted

    @property
    def calls_remaining(self) -> int:
        return int(self.budget_remaining().get("tool_calls", 0))

    def budget_remaining(self) -> dict[str, int]:
        """Remaining per-event budget (not a tool call; not traced)."""
        reply = self._request({"op": "budget"}, "budget_result", "budget_remaining")
        value = reply.get("value")
        return dict(value) if isinstance(value, dict) else {}

    def call(self, tool: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a tool by name."""
        if tool not in TOOL_SPECS:
            raise ToolError(f"unknown tool {tool!r}")
        bound = bind_args(tool, args, kwargs)
        wire_args = {k: _wire_value(v) for k, v in bound.items()}
        reply = self._request({"op": "tool", "name": tool, "args": wire_args}, "tool_result", tool)
        if reply.get("ok") is True:
            value = reply.get("value")
            if tool == "model_complete":
                return ModelResponse.from_dict(value)
            if tool == "embed":
                return EmbeddingResponse.from_dict(value)
            return value
        error = reply.get("error")
        error = error if isinstance(error, dict) else {}
        cls = ERROR_TYPES.get(str(error.get("type")), ToolError)
        if cls is BudgetExceeded:
            self._exhausted = True
        raise cls(str(error.get("message", "")))

    def _request(self, msg: dict[str, Any], expect: str, what: str) -> dict[str, Any]:
        with self._channel.lock:
            if self._closed:
                raise ToolBoxClosed(f"{what}: this ToolBox belongs to a finished step")
            return self._channel.request(msg, expect)

    def _close(self) -> None:
        with self._channel.lock:
            self._closed = True


def _tool_method(name: str, doc: str) -> Any:
    def method(self: RemoteTools, *args: Any, **kwargs: Any) -> Any:
        return self.call(name, *args, **kwargs)

    method.__name__ = name
    method.__qualname__ = f"RemoteTools.{name}"
    method.__doc__ = doc
    return method


for _spec in TOOL_SPECS.values():
    setattr(RemoteTools, _spec.name, _tool_method(_spec.name, _spec.doc))
del _spec


# ------------------------------------------------------------- call handling
def _take(collected: list[str]) -> list[str]:
    out = list(collected)
    del collected[: len(out)]
    return out


def _raise_message(exc: BaseException) -> dict[str, Any]:
    try:
        message = str(exc)
    except Exception:  # noqa: BLE001 - a hostile __str__ must not take the worker down
        message = f"<unprintable {type(exc).__name__}>"
    try:
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:  # noqa: BLE001
        text = ""
    return {"op": "raise", "type": type(exc).__name__, "message": message, "traceback": text}


def _context_from(payload: dict[str, Any]) -> AgentContext:
    fields = dict(payload)
    fields["state_dir"] = Path(fields["state_dir"])
    fields["budget"] = StepBudget(**fields["budget"])
    fields["model"] = ModelSettings(**fields["model"])
    return AgentContext(**fields)


def _event_from(payload: dict[str, Any]) -> AgentEvent:
    fields = dict(payload["event"])
    fields["changed_paths"] = tuple(ChangedPath(**c) for c in fields.get("changed_paths") or ())
    return AgentEvent(**fields)


def _response_value(resp: Any) -> dict[str, Any]:
    """``on_event``'s result as sent to the harness (same checks as the in-process runner)."""
    if not isinstance(resp, AgentResponse):
        return {"invalid": f"on_event must return AgentResponse, got {type(resp).__name__}"}
    if not isinstance(resp.actions, list) or not all(isinstance(a, ACTION_TYPES) for a in resp.actions):
        return {"invalid": "AgentResponse.actions must be a list of Action objects"}
    if not isinstance(resp.usage, Usage):
        return {"invalid": "AgentResponse.usage must be a Usage"}
    return {"actions": [a.to_dict() for a in resp.actions], "usage": resp.usage.to_dict()}


def _handle_call(agent: Agent, channel: _Channel, msg: dict[str, Any]) -> dict[str, Any]:
    method = msg.get("method")
    payload = msg.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    tools: RemoteTools | None = None
    try:
        if method == "describe":
            value: Any = agent.describe()
        elif method == "setup":
            agent.setup(_context_from(payload))
            value = None
        elif method == "on_start":
            tools = RemoteTools(channel)
            agent.on_start(tools)  # type: ignore[arg-type]
            value = None
        elif method == "on_event":
            event = _event_from(payload)
            tools = RemoteTools(channel)
            value = _response_value(agent.on_event(event, tools))  # type: ignore[arg-type]
        elif method == "teardown":
            agent.teardown()
            value = None
        else:
            raise ValueError(f"unknown method {method!r}")
    except BaseException as exc:  # noqa: BLE001 - every contestant fault (even SystemExit) is reported
        return _raise_message(exc)
    finally:
        if tools is not None:
            tools._close()
    reply = {"op": "return", "value": value}
    try:
        encode(reply)
    except (TypeError, ValueError, RecursionError) as exc:
        return _raise_message(TypeError(f"{method}() returned a value that cannot be sent to the harness: {exc}"))
    return reply


def _construct(init: dict[str, Any]) -> Agent:
    entry = init.get("entry")
    if not isinstance(entry, str) or entry.count(":") != 1:
        raise ValueError("entry must look like 'package.module:Class'")
    module_name, class_name = entry.split(":")
    cls = getattr(importlib.import_module(module_name), class_name)
    agent = cls(name=init.get("name"), config=init.get("config"))
    if not isinstance(agent, Agent):
        raise TypeError(f"{entry} did not construct a harness.agent.Agent (got {type(agent).__name__})")
    return agent


def _limit_core_dumps() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))  # a crash must not drop a core file into the state dir
    except (ImportError, ValueError, OSError):
        pass


def main(argv: list[str]) -> int:
    """Serve one contestant until ``shutdown``; returns the exit code."""
    try:
        rfd, wfd = int(argv[1]), int(argv[2])
    except (IndexError, ValueError):
        return 2
    sys.argv = ["tab-worker"]
    _limit_core_dumps()
    channel = _Channel(rfd, wfd)
    try:
        init = channel.read()
    except (OSError, WireError):
        return EXIT_CHANNEL
    if init.get("op") != "init" or init.get("wire") != WIRE_VERSION:
        return EXIT_CHANNEL

    collected: list[str] = []  # tripwire refusals not yet reported (from any thread)
    read_roots = [str(r) for r in init.get("read_roots") or ()] + stdlib_roots()
    read_roots += [p for p in sys.path[1:] if p.endswith(".zip")]  # the stdlib zip, if the interpreter has one
    write_roots = [str(r) for r in init.get("write_roots") or ()]
    tripwire.install(read_roots, write_roots, report=collected.append)

    try:
        agent = _construct(init)
    except BaseException as exc:  # noqa: BLE001
        reply = _raise_message(exc)
        reply["violations"] = _take(collected)
        try:
            channel.send(reply)
        except (OSError, WireError):
            pass
        return 1
    try:
        channel.send({"op": "ready", "wire": WIRE_VERSION, "pid": os.getpid()})
    except (OSError, WireError):
        return EXIT_CHANNEL

    while True:
        try:
            msg = channel.read()
        except (OSError, WireError):
            return 0  # the harness closed the channel
        op = msg.get("op")
        if op == "shutdown":
            return 0
        if op != "call":
            return EXIT_CHANNEL
        reply = _handle_call(agent, channel, msg)
        reply["violations"] = _take(collected)
        try:
            channel.send(reply)
        except (OSError, WireError):
            return EXIT_CHANNEL


if __name__ == "__main__":  # pragma: no cover - runs in the contestant process
    _code = main(sys.argv)
    _flush()
    # Exit without waiting for threads the contestant may have left running.
    os._exit(_code)
