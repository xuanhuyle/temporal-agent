"""The model loop of the shared contestant runtime (contestant code).

:func:`run_event` drives one step: it sends the conversation to the run's
model through ``tools.model_complete``, parses each reply
(``contestant_runtime.protocol``), executes tool calls, and feeds the
observations back until the model gives a final answer or the step's turns
or model budget run out. The loop is memory-agnostic and identical for every
contestant; only the system prompt's catalogue of memory tools and the
memory sections of the first message differ.

Budget handling (milestone-2 design section 8):

- before every model call the loop reads ``tools.budget_remaining()``. When
  at most one model call is left (after the calls reserved for the memory
  system) or the turn limit is reached, the request asks for a final answer
  only, and a tool call in reply is not executed;
- a workspace, history or command call is not attempted when its budget is
  exhausted; the model gets a ``status=budget`` observation instead;
- the request size is estimated with the harness's documented rule
  (``ceil(utf8_bytes / 4)`` plus 4 per message) times a safety factor. When
  the remaining input-token budget could not pay for this request and one more
  of the same size, the transcript is compacted hard; if that is still not
  enough, the request asks for a final answer only. The step ends without a
  final answer only when even that request does not fit;
- ``BudgetExceeded`` is never caught: if it is raised anyway the harness
  records the step as ``budget_exceeded``.

Tool failures (``ToolError``, ``AccessDenied``) become observations. The
transcript is bounded: above ``transcript_chars`` the oldest exchanges are
abbreviated (never the first message, never the most recent exchanges).

Besides the harness's environment tools the runtime offers one tool of its
own, identically to every contestant: ``read_lines(path, start, end,
seq=None)`` returns numbered lines of a workspace file (or of a past state
with ``seq``) through one ``read_file`` / ``read_at`` call, so it costs one
harness tool call. When a ``read_file`` / ``read_at`` observation is cut at
``observation_chars``, the cut is made at line boundaries and the observation
names the omitted lines and the ``read_lines`` call that reads them.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from harness.agent import (
    HISTORICAL_STATE_KEYS,
    Action,
    HistoricalState,
    NoteAction,
    ReopenAction,
    canonical_target,
)
from harness.errors import AccessDenied, ToolError
from harness.llm import ModelMessage, ModelRequest, ModelResponse
from harness.tool_specs import COUNTED_FAMILIES, TOOL_SPECS, ArgSpec, bind_args, check_arg

from contestant_runtime.memory import LocalTool
from contestant_runtime.protocol import (
    CatalogueEntry,
    Final,
    ProtocolError,
    ToolCall,
    parse_reply,
    render_observation,
    truncate_text,
)

__all__ = [
    "ENV_TOOLS",
    "RUNTIME_TOOLS",
    "OFFERED_TOOLS",
    "LoopConfig",
    "LoopResult",
    "env_catalogue",
    "run_event",
    "convert_actions",
    "format_tool_result",
    "estimate_request_tokens",
]

# The environment tools offered to the model: every counted tool of the
# harness table (workspace, history, command), never the model family.
ENV_TOOLS: tuple[str, ...] = tuple(n for n, s in TOOL_SPECS.items() if s.family in COUNTED_FAMILIES)

# Tools the runtime itself provides on top of the environment tools, the same
# for every contestant. Each is implemented with environment tool calls and
# costs what those calls cost.
READ_LINES_ARGS: tuple[ArgSpec, ...] = (ArgSpec("path", "str"), ArgSpec("start", "int"), ArgSpec("end", "int"),
                                        ArgSpec("seq", "opt_int", None))
READ_LINES_DOC = (
    "Numbered lines start..end (1-based, inclusive) of a file in your current workspace, or of the file as it "
    "was after event seq when seq is given. Use it to read the part of a file that an observation left out; "
    "it costs one tool call, like read_file."
)
RUNTIME_TOOLS: tuple[str, ...] = ("read_lines",)
OFFERED_TOOLS: tuple[str, ...] = ENV_TOOLS + RUNTIME_TOOLS
FILE_READ_TOOLS = ("read_file", "read_at")

FINAL_ONLY_TEXT = (
    "<<final-only>> No more tool calls are possible in this event. Reply now with your final "
    'answer: {"final": {"actions": [...], "memory": "..."}}'
)
FORMAT_HINT = (
    'Reply with exactly one JSON object: {"tool": "NAME", "args": {...}} or '
    '{"final": {"actions": [...], "memory": "..."}}.'
)
UNLIMITED = 10**12
MAX_TEXT_CHARS = 4000
MAX_EVIDENCE = 32
MAX_EVIDENCE_CHARS = 128


def env_catalogue() -> list[CatalogueEntry]:
    """Catalogue of the tools every contestant gets: the environment tools, then the runtime's own tools."""
    out = [CatalogueEntry(n, TOOL_SPECS[n].args, TOOL_SPECS[n].doc) for n in ENV_TOOLS]
    out.append(CatalogueEntry("read_lines", READ_LINES_ARGS, READ_LINES_DOC))
    return out


@dataclass(frozen=True)
class LoopConfig:
    """Loop limits. Part of every contestant's recorded configuration.

    - ``max_turns``: model calls in the loop for one step (one more is allowed
      once if the model ignores a final-only request);
    - ``observation_chars``: size cap of one observation (head and tail kept;
      a cut file read names the omitted lines and how to read them);
    - ``transcript_chars``: above this, the oldest exchanges are abbreviated;
    - ``max_protocol_retries``: consecutive unparseable replies tolerated;
    - ``max_actions``: actions kept from a final answer;
    - ``memory_chars``: size cap of the final answer's memory text;
    - ``max_output_tokens``: optional per-call output cap (the run's setting is the ceiling);
    - ``keep_recent_exchanges``: exchanges never abbreviated by ordinary compaction;
    - ``token_safety``: multiplier on the request-size estimate for budget checks;
    - ``min_output_tokens``: below this many remaining output tokens no call is made.
    """

    max_turns: int = 20
    observation_chars: int = 24000
    transcript_chars: int = 120_000
    max_protocol_retries: int = 2
    max_actions: int = 32
    memory_chars: int = 6000
    max_output_tokens: int | None = None
    keep_recent_exchanges: int = 2
    token_safety: float = 1.25
    min_output_tokens: int = 256

    def __post_init__(self) -> None:
        for name in ("max_turns", "observation_chars", "transcript_chars", "max_actions", "memory_chars",
                     "min_output_tokens"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("max_protocol_retries", "keep_recent_exchanges"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        mot = self.max_output_tokens
        if mot is not None and (isinstance(mot, bool) or not isinstance(mot, int) or mot < 1):
            raise ValueError("max_output_tokens must be a positive integer or None")
        ts = self.token_safety
        if isinstance(ts, bool) or not isinstance(ts, (int, float)) or not math.isfinite(ts) or ts < 1:
            raise ValueError("token_safety must be a number >= 1")


@dataclass
class LoopResult:
    actions: list[Action] = field(default_factory=list)
    memory: str = ""
    final: bool = False
    stop_reason: str = ""
    turns: int = 0
    protocol_errors: int = 0
    tool_log: list[dict[str, str]] = field(default_factory=list)
    workspace_writes: dict[str, str | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------- budget
def _utf8_tokens(text: str) -> int:
    return -(-len(text.encode("utf-8", "surrogatepass")) // 4)


def estimate_request_tokens(request: ModelRequest) -> int:
    """The harness's documented estimate: ``ceil(utf8_bytes/4)`` per text plus 4 per message."""
    return _utf8_tokens(request.system) + sum(_utf8_tokens(m.content) + 4 for m in request.messages)


def remaining(tools: Any) -> dict[str, int]:
    """``tools.budget_remaining()`` with absent keys read as unlimited."""
    getter = getattr(tools, "budget_remaining", None)
    raw = getter() if callable(getter) else {}
    out: dict[str, int] = {}
    for key in ("tool_calls", "commands", "model_calls", "model_input_tokens", "model_output_tokens",
                "embedding_tokens"):
        v = raw.get(key) if isinstance(raw, dict) else None
        out[key] = v if isinstance(v, int) and not isinstance(v, bool) else UNLIMITED
    return out


def response_text(resp: Any) -> str:
    if isinstance(resp, ModelResponse):
        return resp.text
    if isinstance(resp, dict):
        return str(resp.get("text", ""))
    return str(getattr(resp, "text", ""))


# ----------------------------------------------------------------- transcript
@dataclass
class _Entry:
    role: str
    content: str
    compact: str
    retrieval: bool = False
    elided: bool = False

    @property
    def current(self) -> str:
        return self.compact if self.elided else self.content


def _compact_reply(text: str, parsed: Any) -> str:
    if isinstance(parsed, ToolCall):
        args = {}
        for k in sorted(parsed.args):
            v = parsed.args[k]
            if isinstance(v, str) and len(v) > 200:
                v = f"<{len(v)} characters elided>"
            args[k] = v
        try:
            return json.dumps({"tool": parsed.name, "args": args}, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            return json.dumps({"tool": parsed.name, "args": "<elided>"})
    head = text.strip()[:200] or "(empty reply)"
    return head + (" [... elided]" if len(text.strip()) > 200 else "")


def _compact_observation(content: str) -> str:
    header = content.split("\n", 1)[0]
    return f"{header}\n[elided to save context: {len(content)} characters; repeat the call if you need it again]"


def _compact(entries: list[_Entry], limit: int, keep_recent: int) -> None:
    """Abbreviate the oldest exchanges until the transcript after the first message fits ``limit``."""
    total = sum(len(e.current) for e in entries[1:])
    protected_from = len(entries) - 2 * keep_recent
    i = 1
    while total > limit and i < protected_from:
        e = entries[i]
        if not e.elided and len(e.compact) < len(e.content):
            total -= len(e.content) - len(e.compact)
            e.elided = True
        i += 1


def _build_request(system: str, entries: list[_Entry], base_retrieval: int, cfg: LoopConfig) -> ModelRequest:
    messages = tuple(ModelMessage(e.role, e.current) for e in entries)
    total = len(system) + sum(len(m.content) for m in messages)
    retrieval = base_retrieval + sum(len(e.current) for e in entries if e.retrieval and not e.elided)
    return ModelRequest(
        system=system,
        messages=messages,
        max_output_tokens=cfg.max_output_tokens,
        purpose="loop",
        retrieval_chars=max(0, min(retrieval, total)),
    )


# ------------------------------------------------------------------ execution
def _normalize_path(path: str) -> str:
    return "/".join(p for p in path.split("/") if p not in ("", "."))


def _fmt_lines(header: str, lines: Sequence[str]) -> str:
    return header + ("\n" + "\n".join(lines) if lines else "")


def format_tool_result(name: str, result: Any) -> str:
    """Plain-text rendering of an environment tool's result for an observation."""
    try:
        if name in ("list_files", "list_at") and isinstance(result, list):
            return _fmt_lines(f"{len(result)} file(s)", [str(p) for p in result])
        if name in ("read_file", "read_at") and isinstance(result, str):
            return result if result else "(empty file)"
        if name == "search" and isinstance(result, dict):
            matches = result.get("matches") or []
            lines = [f"{m.get('path')}:{m.get('line')}: {m.get('text')}" for m in matches if isinstance(m, dict)]
            head = f"{len(lines)} match(es)" + (" (truncated)" if result.get("truncated") else "")
            return _fmt_lines(head, lines)
        if name == "history" and isinstance(result, list):
            lines = []
            for h in result:
                if not isinstance(h, dict):
                    continue
                changed = ", ".join(
                    f"{c.get('path')} ({c.get('op')})" for c in (h.get("changed_paths") or []) if isinstance(c, dict)
                ) or "(none)"
                tree = str(h.get("tree_sha256") or "")[:12]
                lines.append(
                    f"seq={h.get('seq')} event={h.get('event_id') or '-'} time={h.get('timestamp') or '-'} "
                    f"tree={tree} changed: {changed}"
                )
            return _fmt_lines(f"{len(lines)} state(s)", lines)
        if name == "diff" and isinstance(result, dict):
            files = result.get("files") or []
            flines = [f"{f.get('status')}: {f.get('path')}" for f in files if isinstance(f, dict)]
            head = f"diff seq {result.get('seq_a')} -> {result.get('seq_b')}" + (
                f" path {result.get('path')}" if result.get("path") else ""
            )
            text = _fmt_lines(head + f"; {len(flines)} file(s) changed", flines)
            body = str(result.get("diff") or "")
            if body:
                text += "\n\n" + body
            if result.get("truncated"):
                text += "\n[diff truncated by the tool]"
            return text
        if name == "run_command" and isinstance(result, dict):
            head = (
                f"exit_code: {result.get('exit_code')}  timed_out: {str(bool(result.get('timed_out'))).lower()}  "
                f"truncated: {str(bool(result.get('truncated'))).lower()}"
            )
            violations = result.get("violations") or []
            if violations:
                head += "\nrefused operations: " + "; ".join(str(v) for v in violations)
            return head + "\n" + str(result.get("output") or "")
        if result is None:
            return "ok"
        if isinstance(result, str):
            return result
        return json.dumps(result, sort_keys=True, ensure_ascii=False, indent=1, default=str)
    except (TypeError, ValueError, AttributeError):
        return repr(result)


def _read_lines_call(path: str, start: int, end: int, seq: int | None) -> str:
    args = f"path={json.dumps(path, ensure_ascii=False)}, start={start}, end={end}"
    return f"read_lines({args}" + (f", seq={seq})" if seq is not None else ")")


# Characters kept free in a cut file observation for the omission marker.
_MARKER_RESERVE = 400


def file_view(text: str, max_chars: int, path: str, seq: int | None = None) -> str:
    """A file's text cut to about ``max_chars`` at line boundaries (head and tail kept).

    The marker in the middle names the omitted lines and the ``read_lines``
    call that reads them. A text without usable line breaks is cut by
    characters, with a note on how to read it in parts. A text that fits is
    returned unchanged.
    """
    if len(text) <= max_chars:
        return text
    lines = text.splitlines(keepends=True)
    n = len(lines)
    budget = max(0, max_chars - _MARKER_RESERVE)
    head_budget = (budget * 7) // 10
    tail_budget = budget - head_budget
    head = used = 0
    while head < n and used + len(lines[head]) <= head_budget:
        used += len(lines[head])
        head += 1
    tail = used = 0
    while tail < n - head and used + len(lines[n - 1 - tail]) <= tail_budget:
        used += len(lines[n - 1 - tail])
        tail += 1
    first, last = head + 1, n - tail
    if head == 0 or first > last:
        cut = truncate_text(text, budget)
        return (f"{cut}\n[this file has {n} line(s) and {len(text)} characters, more than one observation can "
                f"show; read it in parts with {_read_lines_call(path, 1, min(n, 50), seq)} and so on]")
    omitted = sum(len(x) for x in lines[head:n - tail])
    head_text = "".join(lines[:head])
    if not head_text.endswith("\n"):
        head_text += "\n"
    marker = (f"[... lines {first}-{last} of {n} omitted ({omitted} characters); read them with "
              f"{_read_lines_call(path, first, last, seq)} ...]\n")
    return head_text + marker + "".join(lines[n - tail:])


def _numbered_lines(text: str, path: str, start: int, end: int, seq: int | None, max_chars: int) -> str:
    """The ``read_lines`` observation text: a header and lines ``start..end`` as ``N| text``, within ``max_chars``."""
    lines = text.splitlines()
    n = len(lines)
    where = f"{path} as it was after seq {seq}" if seq is not None else path
    if n == 0:
        return f"{where}: empty file"
    if start > n:
        raise ToolError(f"read_lines: start {start} is past the end of {where} ({n} line(s))")
    end = min(end, n)
    width = len(str(end))
    out: list[str] = []
    size = 0
    last = start - 1
    budget = max(1, max_chars - 300)
    for i in range(start, end + 1):
        row = f"{i:>{width}}| {lines[i - 1]}"
        if out and size + len(row) + 1 > budget:
            break
        out.append(row)
        size += len(row) + 1
        last = i
    header = f"{where}: lines {start}-{last} of {n}"
    text_out = header + "\n" + "\n".join(out)
    if last < end:
        text_out += (f"\n[output limit reached; continue with {_read_lines_call(path, last + 1, end, seq)}]")
    return text_out


_READ_LINES_BINDER = LocalTool("read_lines", READ_LINES_ARGS, READ_LINES_DOC, lambda tools, args: "")
_BUDGET_TEXT = ("The tool-call budget of this event is exhausted: no more workspace, history or command calls "
                "are possible. Give your final answer.")


def _execute_read_lines(tools: Any, call: ToolCall, max_chars: int) -> tuple[str, str]:
    try:
        bound = _READ_LINES_BINDER.bind(call.args)
    except ToolError as exc:
        return "error", str(exc)
    path, start, end, seq = bound["path"], bound["start"], bound["end"], bound["seq"]
    if start < 1 or end < start:
        return "error", "read_lines: start must be >= 1 and end must be >= start"
    if remaining(tools)["tool_calls"] < 1:
        return "budget", _BUDGET_TEXT
    try:
        text = tools.read_file(path) if seq is None else tools.read_at(seq, path)
        if not isinstance(text, str):
            raise ToolError(f"read_lines: unexpected result for {path!r}")
        return "ok", _numbered_lines(text, path, start, end, seq, max_chars)
    except AccessDenied as exc:
        return "denied", str(exc)
    except ToolError as exc:
        return "error", str(exc)


def _execute(
    tools: Any,
    call: ToolCall,
    local: dict[str, LocalTool],
    writes: dict[str, str | None],
    *,
    max_chars: int,
    before_change: Callable[[str, str], None] | None = None,
) -> tuple[str, str, bool, int | None]:
    """Run one tool call. Returns (status, text, is_memory_tool, max_chars override).

    ``max_chars`` is the observation cap; ``before_change(op, path)`` is called
    just before a ``write_file`` / ``delete_file`` is executed.
    """
    if call.name in local:
        lt = local[call.name]
        try:
            bound = lt.bind(call.args)
            return "ok", lt.handler(tools, bound), True, lt.max_chars
        except AccessDenied as exc:
            return "denied", str(exc), True, None
        except ToolError as exc:
            return "error", str(exc), True, None
    if call.name == "read_lines":
        status, text = _execute_read_lines(tools, call, max_chars)
        return status, text, False, None
    if call.name not in ENV_TOOLS:
        offered = ", ".join(list(OFFERED_TOOLS) + sorted(local))
        return "error", f"unknown tool {call.name!r}; available tools: {offered}", False, None
    try:
        bound = bind_args(call.name, (), dict(call.args))
    except TypeError as exc:
        return "error", str(exc), False, None
    for spec in TOOL_SPECS[call.name].args:
        problem = check_arg(call.name, spec, bound[spec.name])
        if problem:
            return "error", problem, False, None
    rem = remaining(tools)
    if rem["tool_calls"] < 1:
        return "budget", _BUDGET_TEXT, False, None
    if call.name == "run_command" and rem["commands"] < 1:
        return "budget", "The command budget of this event is exhausted: run_command is no longer possible.", \
            False, None
    if call.name in ("write_file", "delete_file") and before_change is not None:
        before_change(call.name, _normalize_path(bound["path"]))
    try:
        result = getattr(tools, call.name)(**bound)
    except AccessDenied as exc:
        return "denied", str(exc), False, None
    except ToolError as exc:
        return "error", str(exc), False, None
    if call.name == "write_file":
        writes.pop(_normalize_path(bound["path"]), None)
        writes[_normalize_path(bound["path"])] = bound["content"]
        return "ok", f"wrote {bound['path']} ({len(bound['content'])} characters)", False, None
    if call.name == "delete_file":
        writes.pop(_normalize_path(bound["path"]), None)
        writes[_normalize_path(bound["path"])] = None
        return "ok", f"deleted {bound['path']}", False, None
    text = format_tool_result(call.name, result)
    if call.name in FILE_READ_TOOLS and len(text) > max_chars:
        text = file_view(text, max_chars, bound["path"], bound.get("seq"))
        return "ok", text, False, max(max_chars, len(text))  # already cut: no second, blind cut
    return "ok", text, False, None


# -------------------------------------------------------------------- actions
def _str_list(value: Any, what: str, notes: list[str]) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        notes.append(f"{what} is not a list; ignored")
        return ()
    out: list[str] = []
    for v in value:
        if not isinstance(v, str) or not v.strip():
            notes.append(f"{what} has a non-string item; dropped")
            continue
        v = v.strip()[:MAX_EVIDENCE_CHARS]
        if v not in out:
            out.append(v)
    if len(out) > MAX_EVIDENCE:
        notes.append(f"{what} has more than {MAX_EVIDENCE} items; truncated")
        out = out[:MAX_EVIDENCE]
    return tuple(out)


def convert_actions(raw: Sequence[Any], max_actions: int = 32) -> tuple[list[Action], list[str]]:
    """Turn a final answer's action objects into harness actions; malformed ones are dropped and noted."""
    actions: list[Action] = []
    notes: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        if len(actions) >= max_actions:
            notes.append(f"dropped {len(raw) - i} action(s) above the limit of {max_actions}")
            break
        if not isinstance(item, dict):
            notes.append(f"action {i}: not an object; dropped")
            continue
        kind = item.get("type")
        if kind == "reopen":
            canon = canonical_target(item.get("target"))
            if canon is None:
                notes.append(f"action {i}: reopen target {str(item.get('target'))[:40]!r} is not an id like ADR-0001; dropped")
                continue
            if canon in seen:
                notes.append(f"action {i}: duplicate reopen of {canon}; dropped")
                continue
            rationale = item.get("rationale", "")
            if rationale is None:
                rationale = ""
            if not isinstance(rationale, str):
                notes.append(f"action {i}: rationale is not a string; cleared")
                rationale = ""
            evidence = _str_list(item.get("evidence"), f"action {i}: evidence", notes)
            hs_raw = item.get("historical_state")
            hs: HistoricalState | None = None
            if isinstance(hs_raw, dict):
                extra = sorted(k for k in hs_raw if k not in HISTORICAL_STATE_KEYS)
                if extra:
                    notes.append(f"action {i}: historical_state has unknown key(s) {', '.join(map(str, extra))}; ignored")
                hs = HistoricalState(**{
                    k: _str_list(hs_raw.get(k), f"action {i}: historical_state.{k}", notes)
                    for k in HISTORICAL_STATE_KEYS
                })
            elif hs_raw is not None:
                notes.append(f"action {i}: historical_state is not an object; ignored")
            seen.add(canon)
            actions.append(ReopenAction(target=canon, rationale=rationale[:MAX_TEXT_CHARS], evidence=evidence,
                                        historical_state=hs))
        elif kind == "note":
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                notes.append(f"action {i}: note without text; dropped")
                continue
            actions.append(NoteAction(text=text[:MAX_TEXT_CHARS]))
        else:
            notes.append(f"action {i}: unknown action type {str(kind)[:40]!r}; dropped")
    return actions, notes


# ----------------------------------------------------------------------- loop
def run_event(
    tools: Any,
    *,
    system: str,
    first_message: str,
    local_tools: Sequence[LocalTool] = (),
    config: LoopConfig | None = None,
    retrieval_chars: int = 0,
    reserve_model_calls: int = 0,
    before_workspace_change: Callable[[str, str], None] | None = None,
) -> LoopResult:
    """Run the model loop for one step and return its final answer (or why there is none).

    ``retrieval_chars`` is the number of memory characters in ``first_message``;
    observations of memory tools are added to it per request.
    ``reserve_model_calls`` model calls are left unused for the memory system.
    ``before_workspace_change(op, path)`` is called just before each
    ``write_file`` / ``delete_file`` is executed (``MemorySystem.before_workspace_change``).
    """
    cfg = config or LoopConfig()
    local = {t.name: t for t in local_tools}
    clash = sorted(set(local) & set(OFFERED_TOOLS))
    if clash:
        raise ValueError(f"memory tools may not shadow the shared tools: {', '.join(clash)}")
    entries = [_Entry("user", first_message, first_message)]
    base_retrieval = max(0, min(retrieval_chars, len(first_message)))
    result = LoopResult()
    consecutive_errors = 0
    model_errors = 0
    final_only_announced = False
    input_low = False
    grace_used = False

    def stop(reason: str, note: str) -> LoopResult:
        result.stop_reason = reason
        result.notes.append(note)
        return result

    def announce_final_only() -> None:
        nonlocal final_only_announced
        if final_only_announced:
            return
        last = entries[-1]
        last.content = f"{last.content}\n\n{FINAL_ONLY_TEXT}"
        last.compact = f"{last.compact}\n\n{FINAL_ONLY_TEXT}"
        final_only_announced = True

    def need_tokens(request: ModelRequest) -> float:
        return estimate_request_tokens(request) * cfg.token_safety

    while True:
        rem = remaining(tools)
        calls_left = rem["model_calls"] - reserve_model_calls
        if calls_left < 1:
            return stop("model_budget", "no model calls left for this event; ended without a final answer")
        if rem["model_output_tokens"] < cfg.min_output_tokens:
            return stop("model_budget", "model output-token budget nearly exhausted; ended without a final answer")
        final_only = input_low or calls_left <= 1 or result.turns >= cfg.max_turns - 1
        if final_only:
            announce_final_only()

        _compact(entries, cfg.transcript_chars, cfg.keep_recent_exchanges)
        request = _build_request(system, entries, base_retrieval, cfg)
        budget_in = rem["model_input_tokens"]
        need = need_tokens(request)
        # A tool call is worth making only if the budget can also pay for the request after it
        # (at least as large as this one, unless compacted). Otherwise compact hard and, if that
        # is not enough, ask for the final answer now.
        if need > budget_in or (not final_only and 2 * need > budget_in):
            _compact(entries, 0, 1 if len(entries) > 2 else 0)
            request = _build_request(system, entries, base_retrieval, cfg)
            need = need_tokens(request)
            if not final_only and 2 * need > budget_in:
                input_low = final_only = True
                announce_final_only()
                result.notes.append("model input-token budget running low; final answer requested")
                request = _build_request(system, entries, base_retrieval, cfg)
                need = need_tokens(request)
            if need > budget_in:
                return stop("input_budget", "model input-token budget too small for the next request; "
                                            "ended without a final answer")

        try:
            response = tools.model_complete(request)
        except ToolError as exc:  # provider failure: retry once, then give up on this step
            model_errors += 1
            if model_errors > 1:
                return stop("model_error", f"model call failed: {str(exc)[:200]}; ended without a final answer")
            continue
        result.turns += 1
        text = response_text(response)
        parsed = parse_reply(text)
        reply_content = text if text.strip() else "(empty reply)"
        entries.append(_Entry("assistant", reply_content, _compact_reply(text, parsed)))

        if isinstance(parsed, Final):
            actions, notes = convert_actions(parsed.actions, cfg.max_actions)
            result.actions = actions
            result.notes.extend(notes)
            result.memory = parsed.memory.strip()[: cfg.memory_chars]
            result.final = True
            result.stop_reason = "final"
            return result

        if isinstance(parsed, ProtocolError):
            result.protocol_errors += 1
            consecutive_errors += 1
            result.tool_log.append({"tool": "protocol", "status": "error"})

        if final_only:
            if grace_used or calls_left < 2:
                reason = "protocol_errors" if isinstance(parsed, ProtocolError) else "turns_exhausted"
                return stop(reason, "no final answer when one was required; ended without a final answer")
            grace_used = True
            what = parsed.message if isinstance(parsed, ProtocolError) else f"tool call {parsed.name!r} not executed"
            obs = render_observation("protocol", "error", f"{what}. A final answer is required now. {FINAL_ONLY_TEXT}",
                                     cfg.observation_chars)
            entries.append(_Entry("user", obs, obs))
            continue

        if isinstance(parsed, ProtocolError):
            if consecutive_errors > cfg.max_protocol_retries:
                return stop("protocol_errors", f"{consecutive_errors} consecutive unparseable replies; "
                                               "ended without a final answer")
            msg = parsed.message
            stop_reason = getattr(response, "stop_reason", None)
            if stop_reason == "max_tokens":
                msg += " (the reply was cut off at the output-token limit; keep replies shorter)"
            obs = render_observation("protocol", "error", f"{msg}. {FORMAT_HINT}", cfg.observation_chars)
            entries.append(_Entry("user", obs, _compact_observation(obs)))
            continue

        consecutive_errors = 0
        status, out, is_memory, max_chars = _execute(tools, parsed, local, result.workspace_writes,
                                                     max_chars=cfg.observation_chars,
                                                     before_change=before_workspace_change)
        result.tool_log.append({"tool": parsed.name, "status": status})
        obs = render_observation(parsed.name, status, out, max_chars or cfg.observation_chars)
        entries.append(_Entry("user", obs, _compact_observation(obs), retrieval=is_memory and status == "ok"))
