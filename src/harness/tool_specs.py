"""The contestant tool surface, declared once (contestant-facing).

Every contestant gets exactly these tools, with these argument types, whether
it runs in the harness process (``harness.tools.ToolBox``) or in a contestant
process (``harness.worker`` proxies each call to the harness). Replay and the
wire protocol use the same table.

Families and budgets (per event, see ``harness.agent.StepBudget``):

- ``workspace``: the agent's own current workspace;
- ``history``: the shared, read-only world timeline (protocol amendment A1);
- ``command``: ``run_command`` (amendment A2); also limited by ``max_commands_per_event``;
- ``model``: harness-metered model and embedding access (amendment A3). These
  do not count as tool calls; they have their own call and token budgets.

``workspace``, ``history`` and ``command`` calls each count as one tool call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED = object()


@dataclass(frozen=True)
class ArgSpec:
    name: str
    type: str  # "str" | "int" | "opt_str" | "opt_int" | "str_list" | "request"
    default: Any = REQUIRED


@dataclass(frozen=True)
class ToolSpec:
    name: str
    family: str
    args: tuple[ArgSpec, ...]
    doc: str


TOOL_SPECS: dict[str, ToolSpec] = {
    s.name: s
    for s in (
        ToolSpec("list_files", "workspace", (ArgSpec("prefix", "str", "."),),
                 "Sorted relative paths of files under prefix in your current workspace."),
        ToolSpec("read_file", "workspace", (ArgSpec("path", "str"),),
                 "UTF-8 contents of a file in your current workspace."),
        ToolSpec("write_file", "workspace", (ArgSpec("path", "str"), ArgSpec("content", "str")),
                 "Create or overwrite a file in your current workspace."),
        ToolSpec("delete_file", "workspace", (ArgSpec("path", "str"),),
                 "Delete a file in your current workspace."),
        ToolSpec("search", "workspace", (ArgSpec("pattern", "str"), ArgSpec("prefix", "str", ".")),
                 "Regex search over text files in your current workspace: {matches: [{path, line, text}], truncated}."),
        ToolSpec("history", "history", (),
                 "The repository's world timeline so far: one entry per state 0..now "
                 "({seq, event_id, timestamp, changed_paths, tree_sha256}); state 0 is the initial repository."),
        ToolSpec("list_at", "history", (ArgSpec("seq", "int"), ArgSpec("prefix", "str", ".")),
                 "Files of the repository as it was after event seq (0 = initial repository)."),
        ToolSpec("read_at", "history", (ArgSpec("seq", "int"), ArgSpec("path", "str")),
                 "A file's contents as it was after event seq (0 = initial repository)."),
        ToolSpec("diff", "history", (ArgSpec("seq_a", "int"), ArgSpec("seq_b", "int"), ArgSpec("path", "opt_str", None)),
                 "Unified diff of the repository between two past states, optionally limited to one path or directory."),
        ToolSpec("run_command", "command", (ArgSpec("command", "str"), ArgSpec("timeout_s", "opt_int", None)),
                 "Run `pytest ...` or `python ...` (no shell) in your workspace: {exit_code, output, truncated, timed_out}."),
        ToolSpec("model_complete", "model", (ArgSpec("request", "request"),),
                 "Send a ModelRequest to the run's model; returns a ModelResponse (harness-metered)."),
        ToolSpec("embed", "model", (ArgSpec("texts", "str_list"), ArgSpec("purpose", "str", "")),
                 "Embed texts with the run's embedding model; returns an EmbeddingResponse (harness-metered)."),
    )
}

TOOL_NAMES = tuple(TOOL_SPECS)
COUNTED_FAMILIES = ("workspace", "history", "command")


def bind_args(tool: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Map positional/keyword arguments onto a tool's declared parameters (defaults filled in).

    Raises ``TypeError`` for unknown tools, unknown or missing arguments, like
    an ordinary Python call would. Type checking happens in the ToolBox so
    that a wrongly typed argument is a traced tool error, not a crash.
    """
    spec = TOOL_SPECS.get(tool)
    if spec is None:
        raise TypeError(f"unknown tool {tool!r}")
    names = [a.name for a in spec.args]
    if len(args) > len(names):
        raise TypeError(f"{tool}() takes {len(names)} argument(s), {len(args)} given")
    bound: dict[str, Any] = dict(zip(names, args))
    for k, v in kwargs.items():
        if k not in names:
            raise TypeError(f"{tool}() got an unexpected argument {k!r}")
        if k in bound:
            raise TypeError(f"{tool}() got multiple values for argument {k!r}")
        bound[k] = v
    for a in spec.args:
        if a.name not in bound:
            if a.default is REQUIRED:
                raise TypeError(f"{tool}() missing required argument {a.name!r}")
            bound[a.name] = a.default
    return bound


def check_arg(tool: str, arg: ArgSpec, value: Any) -> str | None:
    """Return an error message if ``value`` does not match the declared type, else None."""
    def is_str(v: Any) -> bool:
        if not isinstance(v, str):
            return False
        try:
            v.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return True

    def is_int(v: Any) -> bool:
        return isinstance(v, int) and not isinstance(v, bool)

    t = arg.type
    ok = (
        (t == "str" and is_str(value))
        or (t == "int" and is_int(value))
        or (t == "opt_str" and (value is None or is_str(value)))
        or (t == "opt_int" and (value is None or is_int(value)))
        or (t == "str_list" and isinstance(value, (list, tuple)) and all(is_str(v) for v in value))
        or (t == "request")  # validated by ModelRequest.from_dict / isinstance in the ToolBox
    )
    if ok:
        return None
    expected = {"str": "a UTF-8 string", "int": "an integer", "opt_str": "a UTF-8 string or null",
                "opt_int": "an integer or null", "str_list": "a list of UTF-8 strings"}[t]
    return f"{tool}: argument {arg.name} must be {expected}"
