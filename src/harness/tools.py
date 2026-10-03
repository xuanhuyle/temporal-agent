"""The tool surface given to every agent, identically (``harness.tool_specs``).

Every call is counted against the per-event budget and reported to the
harness recorder, which writes it to the replay trace and stores results
content-addressed. Tool families:

- workspace tools operate on the agent's own isolated workspace;
- history tools read the shared world timeline (``harness.history``), which
  holds only states up to the event being processed;
- ``run_command`` runs ``pytest``/``python`` in the workspace (``harness.commands``);
- ``model_complete``/``embed`` go to the run's model gateway
  (``harness.model``), which meters usage. They do not count as tool calls;
  they have their own call and token budgets.

A ToolBox is valid for one step only; the runner closes it when the agent's
call returns. Contestants running in a separate process get a proxy with the
same methods (``harness.worker``); the calls are executed here, in the harness.
"""

from __future__ import annotations

import errno
import time
from typing import Any, Callable, Protocol

from harness import guard
from harness.agent import StepBudget
from harness.canonical import canonical_json
from harness.errors import AccessDenied, BudgetExceeded, ToolBoxClosed, ToolError
from harness.llm import EmbeddingResponse, InvalidModelRequest, ModelRequest, ModelResponse
from harness.tool_specs import COUNTED_FAMILIES, TOOL_NAMES, TOOL_SPECS, bind_args, check_arg
from harness.workspace import Workspace

__all__ = [
    "ToolBox",
    "ToolError",
    "AccessDenied",
    "BudgetExceeded",
    "ToolBoxClosed",
    "TOOL_NAMES",
    "HistoryService",
    "CommandService",
    "ModelService",
    "empty_meter",
]

Recorder = Callable[[dict[str, Any]], None]


class HistoryService(Protocol):
    """Read-only world timeline holding only the states revealed so far."""

    def history(self) -> list[dict[str, Any]]: ...
    def list_at(self, seq: int, prefix: str) -> list[str]: ...
    def read_at(self, seq: int, path: str) -> str: ...
    def diff(self, seq_a: int, seq_b: int, path: str | None) -> dict[str, Any]: ...


class CommandService(Protocol):
    """Runs a command in one agent's workspace; returns {exit_code, output, truncated, timed_out, ...}."""

    def run(self, command: str, timeout_s: float) -> dict[str, Any]: ...


class ModelService(Protocol):
    """The run's model gateway. Returns the response plus a metering record."""

    def estimate_input_tokens(self, request: ModelRequest) -> int: ...
    def complete(
        self, request: ModelRequest, *, max_output_tokens: int | None, timeout_s: float | None
    ) -> tuple[ModelResponse, dict[str, Any]]: ...
    def estimate_embedding_tokens(self, texts: list[str]) -> int: ...
    def embed(self, texts: list[str], purpose: str, *, timeout_s: float | None) -> tuple[EmbeddingResponse, dict[str, Any]]: ...


METER_KEYS = (
    "tool_calls",
    "commands",
    "model_calls",
    "model_input_tokens",
    "model_output_tokens",
    "model_cache_read_tokens",
    "model_cache_write_tokens",
    "retrieval_tokens",
    "embedding_calls",
    "embedding_tokens",
    "cost_usd",
    "tool_result_chars",
    "history_result_chars",
    "command_output_chars",
)


def empty_meter() -> dict[str, Any]:
    m: dict[str, Any] = {k: 0 for k in METER_KEYS}
    m["cost_usd"] = 0.0
    m["cost_known"] = True
    return m


def _recordable(value: Any) -> Any:
    """Arguments as recorded in the trace: JSON values as-is, anything else by type name."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else {"unrecordable_type": "float"}
    if isinstance(value, ModelRequest):
        return value.to_dict()
    if isinstance(value, (list, tuple, dict)):
        try:
            canonical_json(value)
        except (TypeError, ValueError):
            return {"unrecordable_type": type(value).__name__}
        return list(value) if isinstance(value, tuple) else value
    return {"unrecordable_type": type(value).__name__}


class ToolBox:
    def __init__(
        self,
        workspace: Workspace,
        budget: StepBudget,
        recorder: Recorder,
        *,
        history: HistoryService | None = None,
        commands: CommandService | None = None,
        model: ModelService | None = None,
        deadline: float | None = None,
    ) -> None:
        self._ws = workspace
        self._budget = budget
        self._record = recorder
        self._history = history
        self._commands = commands
        self._model = model
        self._deadline = deadline
        self._meter = empty_meter()
        self._exhausted = False
        self._closed = False

    # ---------------------------------------------------------------- status
    @property
    def calls_made(self) -> int:
        return self._meter["tool_calls"]

    @property
    def calls_remaining(self) -> int:
        return max(0, self._budget.max_tool_calls_per_event - self._meter["tool_calls"])

    @property
    def exhausted(self) -> bool:
        """True once a call has been refused for lack of budget."""
        return self._exhausted

    def meter(self) -> dict[str, Any]:
        """Harness-metered usage of this step so far."""
        out = dict(self._meter)
        out["cost_usd"] = round(out["cost_usd"], 8)
        return out

    def budget_remaining(self) -> dict[str, int]:
        """Remaining per-event budget (not a tool call; not traced)."""
        b, m = self._budget, self._meter
        return {
            "tool_calls": max(0, b.max_tool_calls_per_event - m["tool_calls"]),
            "commands": max(0, b.max_commands_per_event - m["commands"]),
            "model_calls": max(0, b.max_model_calls_per_event - m["model_calls"]),
            "model_input_tokens": max(0, b.max_model_input_tokens_per_event - m["model_input_tokens"]),
            "model_output_tokens": max(0, b.max_model_output_tokens_per_event - m["model_output_tokens"]),
            "embedding_tokens": max(0, b.max_embedding_tokens_per_event - m["embedding_tokens"]),
        }

    def close(self) -> None:
        self._closed = True

    def _remaining_time(self) -> float | None:
        if self._deadline is None:
            return None
        return max(0.0, self._deadline - time.monotonic())

    # ------------------------------------------------------------- dispatch
    def call(self, tool: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a tool by name (used by the contestant-process proxy and by replay)."""
        if tool not in TOOL_SPECS:
            raise ToolError(f"unknown tool {tool!r}")
        return getattr(self, tool)(*args, **kwargs)

    def _refuse(self, tool: str, recorded: dict[str, Any], message: str) -> None:
        self._exhausted = True
        self._record({"tool": tool, "args": recorded, "status": "budget_exceeded"})
        raise BudgetExceeded(message)

    def _invoke(self, tool: str, args: dict[str, Any], fn: Callable[[], Any]) -> Any:
        if self._closed:
            raise ToolBoxClosed(f"{tool}: this ToolBox belongs to a finished step")
        spec = TOOL_SPECS[tool]
        with guard.bypass():
            recorded = {k: _recordable(v) for k, v in args.items()}
            b, m = self._budget, self._meter
            if spec.family in COUNTED_FAMILIES:
                if m["tool_calls"] >= b.max_tool_calls_per_event:
                    self._refuse(tool, recorded, f"tool-call budget of {b.max_tool_calls_per_event} per event exhausted")
                if spec.family == "command" and m["commands"] >= b.max_commands_per_event:
                    self._refuse(tool, recorded, f"command budget of {b.max_commands_per_event} per event exhausted")
                m["tool_calls"] += 1
                if spec.family == "command":
                    m["commands"] += 1
            meter_rec: dict[str, Any] | None = None
            try:
                for a in spec.args:
                    problem = check_arg(tool, a, args[a.name])
                    if problem:
                        raise ToolError(problem)
                try:
                    result = fn()
                except (ToolError, BudgetExceeded):
                    raise
                except _Refused:
                    raise
                except Exception as exc:  # noqa: BLE001 - OS-level failures become path-free tool errors
                    code = errno.errorcode.get(getattr(exc, "errno", None) or -1, "")
                    raise ToolError(f"{tool}: {type(exc).__name__}{' ' + code if code else ''}") from None
                if isinstance(result, _Metered):
                    meter_rec, result = result.meter, result.value
            except _Refused as refused:
                self._refuse(tool, recorded, refused.message)
            except AccessDenied as exc:
                self._record({"tool": tool, "args": recorded, "status": "denied", "error": str(exc)})
                raise
            except ToolError as exc:
                self._record({"tool": tool, "args": recorded, "status": "error", "error": str(exc)})
                raise
            plain = result.to_dict() if isinstance(result, (ModelResponse, EmbeddingResponse)) else result
            if spec.family in COUNTED_FAMILIES:
                chars = len(canonical_json(plain))
                m["tool_result_chars"] += chars
                if spec.family == "history":
                    m["history_result_chars"] += chars
                elif spec.family == "command":
                    m["command_output_chars"] += chars
            rec: dict[str, Any] = {"tool": tool, "args": recorded, "status": "ok", "result": plain}
            if meter_rec is not None:
                rec["meter"] = meter_rec
            self._record(rec)
            return result

    # ------------------------------------------------------- workspace tools
    def list_files(self, prefix: str = ".") -> list[str]:
        """Sorted relative paths of files under ``prefix``."""
        return self._invoke("list_files", {"prefix": prefix}, lambda: self._ws.list_files(prefix))

    def read_file(self, path: str) -> str:
        """UTF-8 contents of a workspace file."""
        return self._invoke("read_file", {"path": path}, lambda: self._ws.read_text(path))

    def write_file(self, path: str, content: str) -> None:
        """Create or overwrite a workspace file."""
        return self._invoke(
            "write_file", {"path": path, "content": content}, lambda: self._ws.write_text(path, content)
        )

    def delete_file(self, path: str) -> None:
        """Delete a workspace file."""
        return self._invoke("delete_file", {"path": path}, lambda: self._ws.delete(path))

    def search(self, pattern: str, prefix: str = ".") -> dict[str, Any]:
        """Regex search over text files: ``{"matches": [{path, line, text}], "truncated": bool}``."""
        return self._invoke(
            "search", {"pattern": pattern, "prefix": prefix}, lambda: self._ws.search(pattern, prefix)
        )

    # --------------------------------------------------------- history tools
    def _hist(self) -> HistoryService:
        if self._history is None:
            raise ToolError("history is not available in this run")
        return self._history

    def history(self) -> list[dict[str, Any]]:
        """The world timeline so far (states 0..now)."""
        return self._invoke("history", {}, lambda: self._hist().history())

    def list_at(self, seq: int, prefix: str = ".") -> list[str]:
        """Files of the world as it was after event ``seq``."""
        return self._invoke("list_at", {"seq": seq, "prefix": prefix}, lambda: self._hist().list_at(seq, prefix))

    def read_at(self, seq: int, path: str) -> str:
        """A file as it was after event ``seq``."""
        return self._invoke("read_at", {"seq": seq, "path": path}, lambda: self._hist().read_at(seq, path))

    def diff(self, seq_a: int, seq_b: int, path: str | None = None) -> dict[str, Any]:
        """Unified diff between two past world states."""
        return self._invoke(
            "diff", {"seq_a": seq_a, "seq_b": seq_b, "path": path}, lambda: self._hist().diff(seq_a, seq_b, path)
        )

    # --------------------------------------------------------- command tool
    def run_command(self, command: str, timeout_s: int | None = None) -> dict[str, Any]:
        """Run ``pytest ...`` or ``python ...`` (no shell) in the workspace."""

        def go() -> dict[str, Any]:
            if self._commands is None:
                raise ToolError("run_command is not available in this run")
            limit = float(self._budget.command_timeout_s)
            if timeout_s is not None:
                if timeout_s < 1:
                    raise ToolError("run_command: timeout_s must be at least 1")
                limit = min(limit, float(timeout_s))
            remaining = self._remaining_time()
            if remaining is not None:
                limit = min(limit, remaining)
            if limit <= 0:
                raise ToolError("run_command: no wall-clock time left in this step")
            result = dict(self._commands.run(command, limit))
            # Timing is volatile: keep it out of what the agent sees and out of the result hash.
            timing = result.pop("wall_clock_ms", None)
            return _Metered(result, {"wall_clock_ms": timing})

        return self._invoke("run_command", {"command": command, "timeout_s": timeout_s}, go)

    # ----------------------------------------------------------- model tools
    def model_complete(self, request: ModelRequest | dict[str, Any]) -> ModelResponse:
        """Send a request to the run's model (harness-metered)."""

        def go() -> Any:
            if self._model is None:
                raise ToolError("no model is configured for this run")
            try:
                req = request if isinstance(request, ModelRequest) else ModelRequest.from_dict(request)
            except InvalidModelRequest as exc:
                raise ToolError(f"model_complete: invalid request: {exc}") from None
            b, m = self._budget, self._meter
            if m["model_calls"] >= b.max_model_calls_per_event:
                raise _Refused(f"model-call budget of {b.max_model_calls_per_event} per event exhausted")
            remaining_in = b.max_model_input_tokens_per_event - m["model_input_tokens"]
            if self._model.estimate_input_tokens(req) > remaining_in:
                raise _Refused(f"model input-token budget of {b.max_model_input_tokens_per_event} per event exhausted")
            remaining_out = b.max_model_output_tokens_per_event - m["model_output_tokens"]
            if remaining_out < 1:
                raise _Refused(f"model output-token budget of {b.max_model_output_tokens_per_event} per event exhausted")
            cap = remaining_out if req.max_output_tokens is None else min(req.max_output_tokens, remaining_out)
            m["model_calls"] += 1
            response, meter = self._model.complete(req, max_output_tokens=cap, timeout_s=self._remaining_time())
            m["model_input_tokens"] += meter.get("input_tokens", 0)
            m["model_output_tokens"] += meter.get("output_tokens", 0)
            m["model_cache_read_tokens"] += meter.get("cache_read_input_tokens", 0)
            m["model_cache_write_tokens"] += meter.get("cache_creation_input_tokens", 0)
            m["retrieval_tokens"] += meter.get("retrieval_tokens", 0)
            self._add_cost(meter)
            return _Metered(response, meter)

        return self._invoke("model_complete", {"request": request}, go)

    def embed(self, texts: list[str], purpose: str = "") -> EmbeddingResponse:
        """Embed texts with the run's embedding model (harness-metered)."""

        def go() -> Any:
            if self._model is None:
                raise ToolError("no embedding model is configured for this run")
            items = list(texts)
            b, m = self._budget, self._meter
            if m["embedding_tokens"] + self._model.estimate_embedding_tokens(items) > b.max_embedding_tokens_per_event:
                raise _Refused(f"embedding-token budget of {b.max_embedding_tokens_per_event} per event exhausted")
            response, meter = self._model.embed(items, purpose, timeout_s=self._remaining_time())
            m["embedding_calls"] += 1
            m["embedding_tokens"] += meter.get("input_tokens", 0)
            self._add_cost(meter)
            return _Metered(response, meter)

        return self._invoke("embed", {"texts": texts, "purpose": purpose}, go)

    def _add_cost(self, meter: dict[str, Any]) -> None:
        cost = meter.get("cost_usd")
        if cost is None:
            self._meter["cost_known"] = False
        else:
            self._meter["cost_usd"] += float(cost)


class _Metered:
    """A tool result plus the gateway's metering record (internal)."""

    def __init__(self, value: Any, meter: dict[str, Any]) -> None:
        self.value = value
        self.meter = meter


class _Refused(Exception):
    """A model/embedding budget refusal raised inside a tool body (internal)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
