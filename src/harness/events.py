"""Versioned chronological event format (``tab.event/1``) and strict loader.

Harness-internal: events carry full payloads for world changes, including
those of *future* events, so contestants only ever see :class:`AgentEvent`
views produced one step at a time by the runner.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from harness.agent import AgentEvent, ChangedPath
from harness.canonical import sha256_bytes
from harness.workspace import AccessDenied, validate_relpath

EVENT_SCHEMA_VERSION = "tab.event/1"
CHANNELS = ("ticket", "chat", "email", "commit", "changelog", "notice", "support")
EVENT_ID_RE = re.compile(r"^evt-[0-9]{4}$")
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_EVENT_KEYS = {
    "schema_version",
    "event_id",
    "seq",
    "timestamp",
    "channel",
    "author",
    "subject",
    "body",
    "world_changes",
}
_OP_KEYS = {
    "write_file": ({"op", "path"}, {"content", "source", "expect_sha256"}),
    "delete_file": ({"op", "path"}, {"expect_sha256"}),
}


class EventValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WorldChange:
    op: str
    path: str
    data: bytes | None = None
    source: str | None = None
    expect_sha256: str | None = None

    def summary(self) -> dict[str, Any]:
        """Trace-friendly description (content hashed, not inlined)."""
        return {
            "op": self.op,
            "path": self.path,
            "source": self.source,
            "content_sha256": None if self.data is None else sha256_bytes(self.data),
            "expect_sha256": self.expect_sha256,
        }


@dataclass(frozen=True)
class Event:
    schema_version: str
    event_id: str
    seq: int
    timestamp: str
    channel: str
    author: str
    subject: str
    body: str
    world_changes: tuple[WorldChange, ...]

    def agent_view(self) -> AgentEvent:
        changed = tuple(sorted({ChangedPath(op=c.op, path=c.path) for c in self.world_changes},
                               key=lambda c: (c.path, c.op)))
        return AgentEvent(
            schema_version=self.schema_version,
            event_id=self.event_id,
            seq=self.seq,
            timestamp=self.timestamp,
            channel=self.channel,
            author=self.author,
            subject=self.subject,
            body=self.body,
            changed_paths=changed,
        )


def _fail(where: str, msg: str) -> None:
    raise EventValidationError(f"{where}: {msg}")


def _require_str(obj: dict, key: str, where: str, *, allow_empty: bool = False) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or (not allow_empty and not v.strip()):
        _fail(where, f"'{key}' must be a non-empty string")
    return v


def _parse_change(raw: Any, where: str, payload_root: Path) -> WorldChange:
    if not isinstance(raw, dict):
        _fail(where, "world change must be an object")
    op = raw.get("op")
    if op not in _OP_KEYS:
        _fail(where, f"unknown op {op!r}")
    required, optional = _OP_KEYS[op]
    keys = set(raw)
    if not required <= keys:
        _fail(where, f"missing keys {sorted(required - keys)}")
    if keys - required - optional:
        _fail(where, f"unknown keys {sorted(keys - required - optional)}")
    try:
        parts = validate_relpath(raw["path"])
    except AccessDenied as exc:
        _fail(where, f"bad path: {exc}")
    path = "/".join(parts)
    expect = raw.get("expect_sha256")
    if expect is not None and (not isinstance(expect, str) or not SHA256_RE.match(expect)):
        _fail(where, "expect_sha256 must be a lowercase hex sha256")
    if op == "delete_file":
        return WorldChange(op=op, path=path, expect_sha256=expect)
    has_content, has_source = "content" in raw, "source" in raw
    if has_content == has_source:
        _fail(where, "write_file needs exactly one of 'content' or 'source'")
    if has_content:
        if not isinstance(raw["content"], str):
            _fail(where, "'content' must be a string")
        return WorldChange(op=op, path=path, data=raw["content"].encode("utf-8"), expect_sha256=expect)
    source = raw["source"]
    try:
        src_parts = validate_relpath(source)
    except AccessDenied as exc:
        _fail(where, f"bad source: {exc}")
    if src_parts[0] != "payloads":
        _fail(where, "source must live under payloads/")
    src = payload_root.parent.joinpath(*src_parts)
    if src.is_symlink() or not src.is_file():
        _fail(where, f"source file missing: {source}")
    resolved = src.resolve()
    if payload_root.resolve() not in resolved.parents:
        _fail(where, f"source escapes payloads/: {source}")
    return WorldChange(
        op=op, path=path, data=resolved.read_bytes(), source="/".join(src_parts), expect_sha256=expect
    )


def parse_event(raw: Any, where: str, payload_root: Path) -> Event:
    if not isinstance(raw, dict):
        _fail(where, "event must be a JSON object")
    keys = set(raw)
    if keys != _EVENT_KEYS:
        missing, extra = sorted(_EVENT_KEYS - keys), sorted(keys - _EVENT_KEYS)
        _fail(where, f"keys mismatch (missing={missing}, unknown={extra})")
    if raw["schema_version"] != EVENT_SCHEMA_VERSION:
        _fail(where, f"unsupported schema_version {raw['schema_version']!r}")
    event_id = _require_str(raw, "event_id", where)
    if not EVENT_ID_RE.match(event_id):
        _fail(where, f"bad event_id {event_id!r}")
    seq = raw["seq"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        _fail(where, "seq must be a positive integer")
    ts = _require_str(raw, "timestamp", where)
    if not TIMESTAMP_RE.match(ts):
        _fail(where, f"timestamp must be YYYY-MM-DDTHH:MM:SSZ, got {ts!r}")
    try:
        datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        _fail(where, f"invalid timestamp {ts!r}")
    if raw["channel"] not in CHANNELS:
        _fail(where, f"channel must be one of {CHANNELS}")
    author = _require_str(raw, "author", where)
    subject = _require_str(raw, "subject", where)
    body = _require_str(raw, "body", where)
    changes_raw = raw["world_changes"]
    if not isinstance(changes_raw, list):
        _fail(where, "world_changes must be a list")
    changes = tuple(
        _parse_change(c, f"{where} world_changes[{i}]", payload_root) for i, c in enumerate(changes_raw)
    )
    return Event(
        schema_version=raw["schema_version"],
        event_id=event_id,
        seq=seq,
        timestamp=ts,
        channel=raw["channel"],
        author=author,
        subject=subject,
        body=body,
        world_changes=changes,
    )


def load_events(events_file: Path) -> list[Event]:
    """Load and validate a whole event stream.

    Ordering invariants: ``seq`` equals the 1-based line position, event ids
    are unique, and timestamps never decrease.
    """
    events_file = Path(events_file)
    payload_root = events_file.parent / "payloads"
    text = events_file.read_text(encoding="utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    events: list[Event] = []
    seen_ids: set[str] = set()
    for lineno, line in enumerate(lines, start=1):
        where = f"{events_file.name}:{lineno}"
        if not line.strip():
            _fail(where, "blank lines are not allowed")
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            _fail(where, f"invalid JSON: {exc}")
        ev = parse_event(raw, where, payload_root)
        if ev.seq != len(events) + 1:
            _fail(where, f"seq {ev.seq} out of order (expected {len(events) + 1})")
        if ev.event_id in seen_ids:
            _fail(where, f"duplicate event_id {ev.event_id}")
        if events and ev.timestamp < events[-1].timestamp:
            _fail(where, "timestamps must be non-decreasing")
        seen_ids.add(ev.event_id)
        events.append(ev)
    if not events:
        raise EventValidationError(f"{events_file.name}: no events")
    return events
