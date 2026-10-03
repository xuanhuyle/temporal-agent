"""The agent-LLM text protocol ``tab.llm-protocol/1`` (contestant code).

Rendering and parsing for the shared contestant runtime (milestone-2 design
section 7). Everything here is a pure function of its inputs, so two runs
with the same inputs send byte-identical requests.

- :func:`render_system_prompt`: harness instructions, the runtime's generic
  maintainer guidance (identical for every contestant), a tool catalogue
  (``- name(args): description``) and exactly one ``<<tools: a, b, ...>>`` line.
- :func:`render_event_message` / :func:`render_start_message`: the first user
  message of a step (``<<event seq=N id=...>>`` or ``<<start>>``), followed
  by memory sections each starting ``<<memory TITLE>>``.
- :func:`render_observation`: ``<<observation tool=NAME status=...>>`` plus
  the (size-capped) result text.
- :func:`parse_reply`: one JSON object, fenced or bare, into
  :class:`ToolCall` | :class:`Final` | :class:`ProtocolError`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from harness.agent import AgentEvent
from harness.tool_specs import REQUIRED, ArgSpec

PROTOCOL_VERSION = "tab.llm-protocol/1"
OBSERVATION_STATUSES = ("ok", "error", "denied", "budget")
TRUNCATION_MARKER = "[... {n} characters truncated ...]"
# Bounded scan for a JSON object in a reply: a garbage reply full of braces
# must not cost quadratic time.
MAX_OBJECT_STARTS = 256

RUNTIME_RULES = """\
## How to respond

Reply with exactly one JSON object and nothing else. You may wrap it in a
```json code block. Two forms are accepted:

1. A tool call: {"tool": "NAME", "args": {"ARG": VALUE, ...}}
   The result comes back in a message that starts with
   <<observation tool=NAME status=ok|error|denied|budget>>. Make one call per reply.
2. Your final answer for the current event:
   {"final": {"actions": [ACTION, ...], "memory": "TEXT"}}
   Each ACTION is one of:
   {"type": "reopen", "target": "ADR-NNNN or TCK-NNNN", "rationale": "why",
    "evidence": ["evt-NNNN", ...],
    "historical_state": {"known_then": [...], "true_then": [...], "known_now_about_then": [...]} or null}
   {"type": "note", "text": "anything you want on record"}
   "memory" is what you want to remember from this event. It is stored in your
   memory and can be found again in later events, so make it self-contained:
   facts learned, decisions taken and their reasons, constraints and
   assumptions you noticed, work left open and what it is waiting for.

Each event has a limited number of turns, tool calls and model calls. When you
are told to give your final answer, reply with the final form.

## How to work

- Read the event carefully: what does it ask of you, and what does it tell you?
- New information can change the premises of earlier decisions or unblock
  earlier work. For every event, ask whether it changes a fact, constraint,
  requirement, dependency or assumption that an earlier decision or a parked
  work item relied on. Use the memory sections below the event, your memory
  tools, the repository (read, search) and its history (history, read_at,
  diff) to find which earlier decisions or work items rest on what changed.
- Verify before acting. Read the decision record or work item and the evidence
  itself. Reopen only when the new information actually undermines the basis
  of the decision or removes what the work was waiting for; a topic merely
  being mentioned is not enough. Unnecessary reopening is penalized, and so is
  missing a reopening that was needed. Most events need no reopening.
- When a reopening is justified and a code or configuration change follows
  from it, make the change in your workspace and run the tests to check it.
- Cite in "evidence" the ids of the events that support your conclusion (the
  current one and earlier ones). In "historical_state" use event ids, or
  "seed" for the initial repository.
- Keep your memory useful: record what could matter later, including what
  might become relevant if circumstances change.
"""


def guidance_sha256() -> str:
    """Hash of the runtime's fixed guidance text (recorded in ``describe()``)."""
    return hashlib.sha256(RUNTIME_RULES.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ catalogue
@dataclass(frozen=True)
class CatalogueEntry:
    """One tool line of the system prompt."""

    name: str
    args: tuple[ArgSpec, ...]
    description: str

    def signature(self) -> str:
        parts = []
        for a in self.args:
            if a.default is REQUIRED:
                parts.append(a.name)
            else:
                parts.append(f"{a.name}={json.dumps(a.default)}")
        return f"{self.name}({', '.join(parts)})"


def render_system_prompt(instructions: str, catalogue: Sequence[CatalogueEntry]) -> str:
    """Harness instructions, runtime rules, tool catalogue, then the single ``<<tools: ...>>`` line."""
    lines = [instructions.rstrip("\n"), "", RUNTIME_RULES.rstrip("\n"), "", "## Tools", ""]
    for entry in catalogue:
        desc = " ".join(entry.description.split())
        lines.append(f"- {entry.signature()}: {desc}")
    lines.append("")
    lines.append(f"<<tools: {', '.join(e.name for e in catalogue)}>>")
    return "\n".join(lines)


# ------------------------------------------------------------------- messages
@dataclass(frozen=True)
class MemorySection:
    """A block of memory shown to the model under ``<<memory TITLE>>``."""

    title: str
    text: str

    def render(self) -> str:
        title = " ".join(self.title.split()) or "section"
        body = self.text.rstrip("\n") if self.text.strip() else "(empty)"
        return f"<<memory {title}>>\n{body}"


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def render_changed_paths(event: AgentEvent) -> str:
    if not event.changed_paths:
        return "(none)"
    return ", ".join(f"{c.path} ({c.op})" for c in event.changed_paths)


def render_event_header(event: AgentEvent) -> str:
    """The header lines and body of an event (no ``<<event>>`` line, no memory)."""
    return "\n".join(
        [
            f"Date: {_one_line(event.timestamp)}",
            f"Channel: {_one_line(event.channel)}",
            f"Author: {_one_line(event.author)}",
            f"Subject: {_one_line(event.subject)}",
            f"Changed paths: {render_changed_paths(event)}",
            "",
            event.body.rstrip("\n") if event.body.strip() else "(no body)",
        ]
    )


def _with_sections(head: str, sections: Sequence[MemorySection]) -> str:
    parts = [head]
    for s in sections:
        parts.append(s.render())
    return "\n\n".join(parts)


def render_event_message(event: AgentEvent, sections: Sequence[MemorySection] = ()) -> str:
    """First user message of an event step."""
    head = f"<<event seq={event.seq} id={_one_line(event.event_id)}>>\n{render_event_header(event)}"
    return _with_sections(head, sections)


START_TEXT = (
    "This is the repository as it is before the first event. Get oriented: read what\n"
    "you need to understand its purpose, its recorded decisions and their reasons, its\n"
    "constraints and any open work. Do not reopen anything now. Reply with a final\n"
    "answer whose memory records what you learned."
)


def render_start_message(sections: Sequence[MemorySection] = ()) -> str:
    """First user message of the seed step (step 0)."""
    return _with_sections(f"<<start>>\n{START_TEXT}", sections)


def truncate_text(text: str, max_chars: int) -> str:
    """Keep the head and tail of ``text`` with a marker in between, at most ~``max_chars`` chars."""
    if max_chars < 1 or len(text) <= max_chars:
        return text
    cut = len(text) - max_chars
    marker = "\n" + TRUNCATION_MARKER.format(n=cut) + "\n"
    head = (max_chars * 7) // 10
    tail = max_chars - head
    return text[:head] + marker + (text[-tail:] if tail > 0 else "")


def render_observation(tool: str, status: str, text: str, max_chars: int) -> str:
    if status not in OBSERVATION_STATUSES:
        raise ValueError(f"unknown observation status {status!r}")
    body = truncate_text(text, max_chars) if text else "(no output)"
    return f"<<observation tool={tool} status={status}>>\n{body}"


# -------------------------------------------------------------------- parsing
@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Final:
    actions: list[Any] = field(default_factory=list)
    memory: str = ""


@dataclass(frozen=True)
class ProtocolError:
    message: str


Reply = ToolCall | Final | ProtocolError

_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_-]*)[ \t]*\r?\n(.*?)```", re.S)
_DECODER = json.JSONDecoder()


def _first_object(text: str) -> dict[str, Any] | None:
    """The first ``{...}`` in ``text`` that decodes as a JSON object (string-aware)."""
    pos = text.find("{")
    tries = 0
    while pos != -1 and tries < MAX_OBJECT_STARTS:
        tries += 1
        try:
            value, _end = _DECODER.raw_decode(text, pos)
        except (json.JSONDecodeError, RecursionError):
            value = None
        if isinstance(value, dict):
            return value
        pos = text.find("{", pos + 1)
    return None


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract one JSON object: a fenced code block (```` ``` ```` or ```` ```json ````) first, else the first bare object."""
    for m in _FENCE.finditer(text):
        tag = m.group(1).lower()
        if tag not in ("", "json"):
            continue
        obj = _first_object(m.group(2))
        if obj is not None:
            return obj
    return _first_object(text)


def parse_reply(text: str) -> Reply:
    """Parse a model reply into a tool call, a final answer, or a protocol error."""
    if not isinstance(text, str) or not text.strip():
        return ProtocolError("empty reply")
    obj = extract_json_object(text)
    if obj is None:
        return ProtocolError("no JSON object found in the reply")
    has_tool, has_final = "tool" in obj, "final" in obj
    if has_tool and has_final:
        return ProtocolError('a reply must contain either "tool" or "final", not both')
    if has_final:
        final = obj["final"]
        if not isinstance(final, dict):
            return ProtocolError('"final" must be an object with "actions" and "memory"')
        actions = final.get("actions", [])
        if actions is None:
            actions = []
        if not isinstance(actions, list):
            return ProtocolError('"final.actions" must be a list')
        memory = final.get("memory", "")
        if memory is None:
            memory = ""
        if not isinstance(memory, str):
            return ProtocolError('"final.memory" must be a string')
        return Final(actions=list(actions), memory=memory)
    if has_tool:
        name = obj["tool"]
        if not isinstance(name, str) or not name.strip():
            return ProtocolError('"tool" must be a non-empty string')
        args = obj.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return ProtocolError('"args" must be an object')
        return ToolCall(name=name.strip(), args=dict(args))
    return ProtocolError('the JSON object must have a "tool" or a "final" key')
