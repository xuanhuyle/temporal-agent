"""The tool surface given to every contestant, identically.

Every call is counted against the per-event budget and reported to the
harness recorder (which writes it to the replay trace and stores the result
content-addressed). There is deliberately no command-execution tool in
Milestone 1: code executed on behalf of an agent could read evaluator files by
absolute path, and there is no OS sandbox yet.

A ToolBox is valid for one step only; the runner closes it when the agent's
call returns.
"""

from __future__ import annotations

from typing import Any, Callable

from harness import guard
from harness.agent import StepBudget
from harness.workspace import AccessDenied, ToolError, Workspace

__all__ = ["ToolBox", "ToolError", "AccessDenied", "BudgetExceeded", "ToolBoxClosed", "TOOL_NAMES"]

TOOL_NAMES = ("list_files", "read_file", "write_file", "delete_file", "search")


class BudgetExceeded(BaseException):
    """The per-event tool-call budget is exhausted. Ends the agent's step.

    A ``BaseException`` so that agent code catching ``Exception`` around tool
    calls cannot accidentally swallow it. Even if it is caught, the step is
    recorded as ``budget_exceeded``.
    """


class ToolBoxClosed(ToolError):
    """The step this ToolBox belonged to has ended."""


Recorder = Callable[[dict[str, Any]], None]


def _recordable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    return {"unrecordable_type": type(value).__name__}


class ToolBox:
    def __init__(self, workspace: Workspace, budget: StepBudget, recorder: Recorder) -> None:
        self._ws = workspace
        self._budget = budget
        self._record = recorder
        self._calls = 0
        self._exhausted = False
        self._closed = False

    @property
    def calls_made(self) -> int:
        return self._calls

    @property
    def calls_remaining(self) -> int:
        return max(0, self._budget.max_tool_calls_per_event - self._calls)

    @property
    def exhausted(self) -> bool:
        """True once a call has been refused for lack of budget."""
        return self._exhausted

    def close(self) -> None:
        self._closed = True

    def _invoke(self, tool: str, args: dict[str, Any], fn: Callable[[], Any]) -> Any:
        if self._closed:
            raise ToolBoxClosed(f"{tool}: this ToolBox belongs to a finished step")
        with guard.suspended():
            recorded = {k: _recordable(v) for k, v in args.items()}
            if self._calls >= self._budget.max_tool_calls_per_event:
                self._exhausted = True
                self._record({"tool": tool, "args": recorded, "status": "budget_exceeded"})
                raise BudgetExceeded(
                    f"tool-call budget of {self._budget.max_tool_calls_per_event} per event exhausted"
                )
            self._calls += 1
            try:
                bad = [k for k, v in args.items() if not isinstance(v, str)]
                if bad:
                    raise ToolError(f"{tool}: argument(s) {', '.join(bad)} must be strings")
                result = fn()
            except AccessDenied as exc:
                self._record({"tool": tool, "args": recorded, "status": "denied", "error": str(exc)})
                raise
            except ToolError as exc:
                self._record({"tool": tool, "args": recorded, "status": "error", "error": str(exc)})
                raise
            self._record({"tool": tool, "args": recorded, "status": "ok", "result": result})
            return result

    # ------------------------------------------------------------------ tools
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
