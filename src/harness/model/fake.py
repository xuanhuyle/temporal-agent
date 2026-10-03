"""Deterministic fake completion backend, model ``fake-v1`` (benchmark infrastructure).

It speaks the agent-LLM protocol ``tab.llm-protocol/1`` (milestone-2 design
section 7) so that the whole contestant machinery (loop, tools, memory,
budgets, traces, replay) can run in CI without a provider. Its choices are a
fixed function of the request; its scores mean nothing.

Policy for a loop request (any purpose other than ``query_expansion`` and
``summary``). Let ``k`` be the number of assistant turns in the request:

1. The tools offered are read from the system prompt's single
   ``<<tools: a, b, ...>>`` line.
2. The first user message must start with ``<<start>>`` (reply: a final
   answer with no actions) or ``<<event seq=N id=EVENT_ID>>``. Its header
   lines (up to the first blank line) give ``Subject:`` and ``Changed paths:``.
3. The planned tool calls, in order, each kept only if applicable:
   ``memory_search(<subject>)`` if offered and the subject is non-empty;
   ``history()`` if offered; ``diff(seq-1, seq)`` if offered and the event
   changed paths and ``seq >= 1``; ``run_command("pytest -q -x")`` if offered
   and ``sha256(event_id) % 4 == 0``. Reply ``k`` is planned call ``k``; once
   the plan is exhausted the reply is the final answer. (With every tool
   offered this is exactly "k=0 memory_search, k=1 history, k=2 diff,
   k=3 run_command"; skipping inapplicable steps instead of idling keeps the
   same order without repeated calls.)
4. The final answer reopens every ``ADR-NNNN``/``TCK-NNNN`` id found in
   observation messages (user messages starting ``<<observation``) or memory
   sections (from a line starting ``<<memory`` to the end of that message)
   for which ``sha256(f"{id}|{event_id}") % 7 == 0``, citing the event, and
   adds one note.

The argument name for ``memory_search`` is taken from its catalogue line
(``- memory_search(query, ...): ...``) and defaults to ``query``.

``query_expansion`` returns ``{"queries": [...]}`` with the words of the
first ``Subject:`` line (or of the last user message). ``summary`` returns a
deterministic plain-text digest. Anything unexpected yields a final answer
with no actions: this backend never raises on content.

Usage is the harness estimator's (``harness.model.tokens``). Output is cut
at the first stop sequence (``stop_sequence``) and at ``max_output_tokens``
(``max_tokens``), as a provider would.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from harness.agent import ModelSettings
from harness.llm import ModelRequest
from harness.model.gateway import FAKE_MODEL_ID, RawCompletion
from harness.model.tokens import BYTES_PER_TOKEN, estimate_request_tokens, estimate_tokens

__all__ = ["FakeBackend", "FAKE_MODEL_ID"]

_TOOLS_LINE = re.compile(r"^<<tools:([^\n]*)>>[ \t]*$", re.M)
_CATALOGUE_LINE = re.compile(r"^- ([A-Za-z_][A-Za-z0-9_]*)\(([^)\n]*)\)", re.M)
_EVENT_LINE = re.compile(r"<<event seq=(-?\d+) id=([^\s>]+)>>")
_ID = re.compile(r"\b(?:ADR|TCK)-\d{4}\b")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]*")
_NO_PATHS = frozenset({"", "none", "(none)", "-", "[]", "n/a"})
MAX_EXPANSION_QUERIES = 16


def _h(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest(), 16)


def _dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(", ", ": "))


def _empty_final() -> str:
    return _dump({"final": {"actions": [], "memory": ""}})


def _offered_tools(system: str) -> tuple[set[str], dict[str, str]]:
    names: set[str] = set()
    matches = _TOOLS_LINE.findall(system)
    if matches:
        names = {n.strip() for n in matches[-1].split(",") if n.strip()}
    first_args: dict[str, str] = {}
    for name, args in _CATALOGUE_LINE.findall(system):
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", args)
        if m and name not in first_args:
            first_args[name] = m.group(1)
    return names, first_args


def _header_fields(first: str) -> dict[str, str]:
    """``Name: value`` lines after the ``<<event ...>>`` line, up to the first blank line."""
    fields: dict[str, str] = {}
    lines = first.split("\n")[1:]
    for line in lines:
        if not line.strip():
            break
        key, sep, value = line.partition(":")
        if sep and key.strip() and key.strip() not in fields:
            fields[key.strip()] = value.strip()
    return fields


def _memory_text(content: str) -> str:
    """Everything from the first line starting ``<<memory`` to the end of the message."""
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("<<memory"):
            return "\n".join(lines[i:])
    return ""


def _seen_ids(request: ModelRequest) -> list[str]:
    found: set[str] = set()
    for m in request.messages:
        if m.role != "user":
            continue
        if m.content.startswith("<<observation"):
            found.update(_ID.findall(m.content))
        found.update(_ID.findall(_memory_text(m.content)))
    return sorted(found)


def _first_subject(request: ModelRequest) -> str | None:
    for m in request.messages:
        if m.role != "user":
            continue
        for line in m.content.split("\n"):
            if line.startswith("Subject:"):
                return line[len("Subject:"):].strip()
    return None


def _loop_reply(request: ModelRequest) -> str:
    first = request.messages[0].content
    if first.startswith("<<start>>"):
        return _empty_final()
    m = _EVENT_LINE.match(first)
    if m is None:
        return _empty_final()
    seq, event_id = int(m.group(1)), m.group(2)
    fields = _header_fields(first)
    subject = fields.get("Subject", "")
    changed = fields.get("Changed paths", "").strip().lower() not in _NO_PATHS
    tools, first_args = _offered_tools(request.system)

    plan: list[dict[str, Any]] = []
    if "memory_search" in tools and subject:
        plan.append({"tool": "memory_search", "args": {first_args.get("memory_search", "query"): subject}})
    if "history" in tools:
        plan.append({"tool": "history", "args": {}})
    if "diff" in tools and changed and seq >= 1:
        plan.append({"tool": "diff", "args": {"seq_a": seq - 1, "seq_b": seq}})
    if "run_command" in tools and _h(event_id) % 4 == 0:
        plan.append({"tool": "run_command", "args": {"command": "pytest -q -x"}})

    k = sum(1 for msg in request.messages if msg.role == "assistant")
    if k < len(plan):
        return _dump(plan[k])

    ids = _seen_ids(request)
    reopened = [i for i in ids if _h(f"{i}|{event_id}") % 7 == 0]
    actions: list[dict[str, Any]] = [
        {
            "type": "reopen",
            "target": i,
            "rationale": f"fake-v1 policy selected {i} while processing {event_id}",
            "evidence": [event_id],
            "historical_state": None,
        }
        for i in reopened
    ]
    actions.append(
        {"type": "note", "text": f"fake-v1 processed {event_id}: saw {len(ids)} id(s), reopened {len(reopened)}"}
    )
    memory = f"{event_id}: {subject}" if subject else event_id
    return _dump({"final": {"actions": actions, "memory": memory}})


def _query_expansion(request: ModelRequest) -> str:
    subject = _first_subject(request)
    if subject is None:
        subject = request.messages[-1].content
    words: list[str] = []
    seen: set[str] = set()
    for w in _WORD.findall(subject):
        if w.lower() not in seen:
            seen.add(w.lower())
            words.append(w)
        if len(words) >= MAX_EXPANSION_QUERIES:
            break
    return _dump({"queries": words})


def _summary(request: ModelRequest) -> str:
    digest = hashlib.sha256(
        json.dumps(request.to_dict()["messages"], sort_keys=True, ensure_ascii=True).encode("ascii")
    ).hexdigest()[:16]
    subjects: list[str] = []
    ids: set[str] = set()
    for m in request.messages:
        ids.update(_ID.findall(m.content))
        for line in m.content.split("\n"):
            if line.startswith("Subject:"):
                s = line[len("Subject:"):].strip()
                if s and s not in subjects:
                    subjects.append(s)
    return "\n".join(
        [
            "fake-v1 summary",
            f"digest: {digest}",
            f"messages: {len(request.messages)}",
            f"subjects: {'; '.join(subjects[:8]) if subjects else '(none)'}",
            f"ids: {', '.join(sorted(ids)) if ids else '(none)'}",
        ]
    )


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    data = text.encode("utf-8", "surrogatepass")[: max_tokens * BYTES_PER_TOKEN]
    return data.decode("utf-8", "ignore")


class FakeBackend:
    """Deterministic ``tab.llm-protocol/1`` policy; see the module docstring."""

    name = "fake"
    model = FAKE_MODEL_ID

    def reply_text(self, request: ModelRequest) -> str:
        """The untruncated reply for ``request`` (never raises on content)."""
        try:
            if request.purpose == "query_expansion":
                return _query_expansion(request)
            if request.purpose == "summary":
                return _summary(request)
            return _loop_reply(request)
        except Exception:  # noqa: BLE001 - garbage in must not crash the harness
            return _empty_final()

    def complete(
        self,
        request: ModelRequest,
        settings: ModelSettings,
        *,
        max_output_tokens: int,
        timeout_s: float | None,
        lane: str,
    ) -> RawCompletion:
        text = self.reply_text(request)
        stop_reason = "end_turn"
        cut = [text.find(s) for s in request.stop if s and text.find(s) >= 0]
        if cut:
            text = text[: min(cut)]
            stop_reason = "stop_sequence"
        if estimate_tokens(text) > max_output_tokens:
            text = _truncate_to_tokens(text, max_output_tokens)
            stop_reason = "max_tokens"
        return RawCompletion(
            text=text,
            stop_reason=stop_reason,
            model=FAKE_MODEL_ID,
            input_tokens=estimate_request_tokens(request),
            output_tokens=estimate_tokens(text),
        )
