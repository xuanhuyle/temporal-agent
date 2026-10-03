"""Exceptions shared by the harness and contestant code (contestant-facing).

Contestants see these classes whether they run in the harness process
(reference agents) or in a separate contestant process (model-backed
contestants), so this module imports nothing.
"""

from __future__ import annotations


class ToolError(Exception):
    """A recoverable tool failure reported back to the agent."""


class AccessDenied(ToolError):
    """The requested path or state is outside what this agent may touch."""


class ToolBoxClosed(ToolError):
    """The step this ToolBox belonged to has ended."""


class BudgetExceeded(BaseException):
    """A per-event budget (tool calls, commands, model calls or tokens) is exhausted. Ends the agent's step.

    A ``BaseException`` so that agent code catching ``Exception`` around tool
    calls cannot accidentally swallow it. Even if it is caught, the step is
    recorded as ``budget_exceeded``.
    """


ERROR_TYPES: dict[str, type[BaseException]] = {
    "ToolError": ToolError,
    "AccessDenied": AccessDenied,
    "ToolBoxClosed": ToolBoxClosed,
    "BudgetExceeded": BudgetExceeded,
}
