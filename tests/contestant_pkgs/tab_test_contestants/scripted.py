"""A scripted contestant driven by event subjects (``do_<subject>``), plus escape probes.

Every handler reports what it observed through ``NoteAction`` texts (JSON), so
the test in the harness process can assert on what happened in here.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from typing import Any

from harness.agent import (
    Agent,
    AgentContext,
    AgentEvent,
    AgentResponse,
    HistoricalState,
    NoteAction,
    ReopenAction,
    Usage,
)
from harness.errors import AccessDenied, BudgetExceeded, ToolBoxClosed, ToolError
from harness.llm import ModelMessage, ModelRequest


class TabCustomError(Exception):
    """A contestant-defined exception type (its name must survive the process boundary)."""


def _note(obj: Any) -> NoteAction:
    return NoteAction(json.dumps(obj, sort_keys=True))


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


class ScriptedAgent(Agent):
    kind = "scripted"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name)
        self.config = dict(config or {})
        self.setups: list[int] = []
        self.kept_tools: Any = None
        self.start_files: list[str] | None = None

    def describe(self) -> dict[str, Any]:
        return {"kind": self.kind, "role": self.role, "config": {"k": self.config.get("k"), "reported_by": "child"}}

    def setup(self, context: AgentContext) -> None:
        super().setup(context)
        self.setups.append(context.restart_count)
        with open("setup.log", "a", encoding="utf-8") as fh:  # cwd is the state dir
            fh.write(f"{context.restart_count}\n")

    def on_start(self, tools: Any) -> None:
        self.start_files = tools.list_files()

    def teardown(self) -> None:
        with open("teardown.txt", "w", encoding="utf-8") as fh:
            fh.write("done")
        print("teardown-marker")

    def on_event(self, event: AgentEvent, tools: Any) -> AgentResponse:
        handler = getattr(self, "do_" + event.subject.replace("-", "_"), None)
        if handler is None:
            return AgentResponse()
        return handler(event, tools)

    # ------------------------------------------------------------- tools
    def do_tools(self, event: AgentEvent, tools: Any) -> AgentResponse:
        out: dict[str, Any] = {"start_files": self.start_files}
        out["files"] = tools.list_files()
        out["readme"] = tools.read_file("README.md")
        tools.write_file("notes/x.md", "hello from the contestant process\n")
        out["via_call"] = tools.call("read_file", "notes/x.md")
        out["search"] = tools.search("hello", prefix="notes")["matches"][0]["path"]
        try:
            tools.read_file("../x")
        except AccessDenied as exc:
            out["traversal"] = ["AccessDenied", str(exc)]
        try:
            tools.read_file({1, 2})  # not JSON: must still reach the harness and fail its type check
        except ToolError as exc:
            out["wrong_type"] = [type(exc).__name__, str(exc)]
        try:
            tools.read_file(pathx="a")
        except TypeError as exc:
            out["bad_kwarg"] = str(exc)
        try:
            tools.call("no_such_tool")
        except ToolError as exc:
            out["unknown_tool"] = str(exc)
        try:
            tools.history()
        except ToolError as exc:
            out["history"] = [type(exc).__name__, str(exc)]
        reopen = ReopenAction(
            target="ADR-0001",
            rationale="the vendor changed its API",
            evidence=(event.event_id,),
            historical_state=HistoricalState(known_then=("seed",), known_now_about_then=(event.event_id,)),
        )
        return AgentResponse(actions=[reopen, _note(out)], usage=Usage(model_calls=1, model_input_tokens=5))

    def do_budget(self, event: AgentEvent, tools: Any) -> AgentResponse:
        while True:
            tools.list_files()

    def do_budget_caught(self, event: AgentEvent, tools: Any) -> AgentResponse:
        calls = 0
        try:
            while True:
                tools.list_files()
                calls += 1
        except BudgetExceeded as exc:
            caught = str(exc)
        return AgentResponse(actions=[_note({"caught": caught, "calls": calls, "exhausted": tools.exhausted,
                                              "remaining": tools.budget_remaining()})])

    def do_budget_info(self, event: AgentEvent, tools: Any) -> AgentResponse:
        before = tools.calls_remaining
        tools.list_files()
        return AgentResponse(actions=[_note({"before": before, "after": tools.calls_remaining,
                                              "budget": tools.budget_remaining()})])

    def do_model(self, event: AgentEvent, tools: Any) -> AgentResponse:
        first = tools.model_complete(ModelRequest(system="sys", messages=(ModelMessage("user", "hi"),), purpose="loop"))
        second = tools.model_complete({"system": "", "messages": [{"role": "user", "content": "dict form"}]})
        emb = tools.embed(["ab", "c"], purpose="index")
        return AgentResponse(actions=[_note({
            "types": [type(first).__name__, type(second).__name__, type(emb).__name__],
            "texts": [first.text, second.text],
            "model": first.model,
            "vectors": [list(v) for v in emb.vectors],
        })])

    def do_keep_tools(self, event: AgentEvent, tools: Any) -> AgentResponse:
        self.kept_tools = tools
        return AgentResponse()

    def do_use_stale(self, event: AgentEvent, tools: Any) -> AgentResponse:
        out: dict[str, Any] = {}
        try:
            self.kept_tools.list_files()
        except ToolBoxClosed as exc:
            out["list_files"] = [type(exc).__name__, str(exc)]
        try:
            self.kept_tools.budget_remaining()
        except ToolBoxClosed as exc:
            out["budget_remaining"] = type(exc).__name__
        return AgentResponse(actions=[_note(out)])

    # ------------------------------------------------------------ failures
    def do_raise(self, event: AgentEvent, tools: Any) -> AgentResponse:
        raise ValueError("boom 42")

    def do_custom_raise(self, event: AgentEvent, tools: Any) -> AgentResponse:
        raise TabCustomError("custom failure")

    def do_exit(self, event: AgentEvent, tools: Any) -> AgentResponse:
        sys.exit(5)  # SystemExit is reported like any other exception; the process survives

    def do_invalid(self, event: AgentEvent, tools: Any) -> Any:
        return {"not": "a response"}

    def do_bad_actions(self, event: AgentEvent, tools: Any) -> AgentResponse:
        return AgentResponse(actions=["reopen ADR-0001"])  # type: ignore[list-item]

    def do_sleep(self, event: AgentEvent, tools: Any) -> AgentResponse:
        with open("ckpt.txt", "w", encoding="utf-8") as fh:
            fh.write("before-timeout")
        time.sleep(60)
        return AgentResponse()

    def do_cmd(self, event: AgentEvent, tools: Any) -> AgentResponse:
        """A command that outlives the step's remaining wall clock (its limit comes from the deadline)."""
        time.sleep(float(self.config.get("cmd_delay", 0)))
        out = tools.run_command('python -c "import time; time.sleep(30)"')
        return AgentResponse(actions=[_note({"timed_out": out["timed_out"]})])

    def do_crash(self, event: AgentEvent, tools: Any) -> AgentResponse:
        with open("crash.txt", "w", encoding="utf-8") as fh:
            fh.write("about-to-crash")
        print("crash-marker", flush=True)
        os._exit(3)

    def do_forge(self, event: AgentEvent, tools: Any) -> AgentResponse:
        """Write a bogus message to every descriptor that accepts it (one of them is the wire)."""
        for fd in range(3, 64):
            try:
                os.write(fd, b'{"op":"bogus"}\n')
            except OSError:
                pass
        time.sleep(30)
        return AgentResponse()

    # --------------------------------------------------------- observation
    def do_state(self, event: AgentEvent, tools: Any) -> AgentResponse:
        assert self.context is not None
        return AgentResponse(actions=[_note({
            "restart_count": self.context.restart_count,
            "setups": self.setups,
            "ckpt": _read("ckpt.txt"),
            "crash": _read("crash.txt"),
            "setup_log": _read("setup.log"),
            "pid": os.getpid(),
        })])

    def do_print(self, event: AgentEvent, tools: Any) -> AgentResponse:
        print(f"stdout-marker-{event.seq}")
        print(f"stderr-marker-{event.seq}", file=sys.stderr)
        return AgentResponse(actions=[_note({"pid": os.getpid()})])

    def do_hash(self, event: AgentEvent, tools: Any) -> AgentResponse:
        words = {f"word-{i}" for i in range(40)}
        return AgentResponse(actions=[_note({
            "order": list(words),
            "hash": hash("temporal"),
            "hash_randomization": sys.flags.hash_randomization,
        })])

    def do_probe(self, event: AgentEvent, tools: Any) -> AgentResponse:
        """Try to reach the benchmark from inside the contestant process."""
        repo = self.config["repo_root"]
        outside = self.config["outside_path"]
        results: dict[str, str] = {}

        def attempt(label: str, fn: Any) -> None:
            try:
                fn()
                results[label] = "allowed"
            except BaseException as exc:  # noqa: BLE001 - the probe reports every outcome
                results[label] = type(exc).__name__

        env = dict(os.environ)

        def mentions(values: Any) -> list[str]:
            return [v for v in values if repo in v]

        def labels() -> None:
            with open(os.path.join(repo, "world", "ground_truth", "smoke_v1", "labels.json"), "rb") as fh:
                fh.read()

        def environ() -> None:
            with open("/proc/self/environ", "rb") as fh:
                fh.read()

        def write_outside() -> None:
            with open(outside, "w", encoding="utf-8") as fh:
                fh.write("escaped")

        def write_state() -> None:
            with open("probe-ok.txt", "w", encoding="utf-8") as fh:
                fh.write("ok")

        def read_bundle() -> None:
            import harness.agent

            with open(harness.agent.__file__, "rb") as fh:
                fh.read()

        def sock() -> None:
            import socket

            socket.socket(socket.AF_INET, socket.SOCK_STREAM).close()

        def proc() -> None:
            import subprocess

            subprocess.run(["/bin/true"], check=False)

        def native() -> None:
            import ctypes

            ctypes.CDLL("libc.so.6")

        def smuggle() -> None:
            sys.path.insert(0, os.path.join(repo, "src"))
            try:
                importlib.import_module("evaluation")
            finally:
                sys.path.pop(0)

        for module in ("harness.runner", "harness.scenario", "harness.tools", "harness.guard",
                       "harness.process", "evaluation"):
            attempt(f"import {module}", lambda m=module: importlib.import_module(m))
        attempt("read labels", labels)
        attempt("list repo", lambda: os.listdir(repo))
        attempt("read environ", environ)
        attempt("write outside", write_outside)
        attempt("write state", write_state)
        attempt("read bundle", read_bundle)
        attempt("socket", sock)
        attempt("subprocess", proc)
        attempt("ctypes", native)
        attempt("signal parent", lambda: os.kill(os.getppid(), 0))
        attempt("smuggle repo onto sys.path", smuggle)
        report = {
            "results": results,
            "env_keys": sorted(env),
            "secrets": [k for k in ("ANTHROPIC_API_KEY", "HTTPS_PROXY", "https_proxy", "TAB_PROBE_SECRET") if k in env],
            "repo_in_sys_path": mentions(sys.path),
            "repo_in_argv": mentions(sys.argv) + mentions(getattr(sys, "orig_argv", [])),
            "repo_in_environ": mentions(env.values()),
            "cwd": os.getcwd(),
            "home": env.get("HOME"),
            "tmpdir": env.get("TMPDIR"),
            "pythonhashseed": env.get("PYTHONHASHSEED"),
            "tz": env.get("TZ"),
            "path": env.get("PATH"),
            "argv": sys.argv,
        }
        return AgentResponse(actions=[_note(report)])


class HangsInTeardown(ScriptedAgent):
    def teardown(self) -> None:
        time.sleep(60)
