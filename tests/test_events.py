"""Event schema validation and chronological ordering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.events import EventValidationError, load_events
from harness.world import apply_event
from harness.workspace import Workspace


def _ev(seq, ts="2026-01-01T00:00:00Z", **over):
    ev = {
        "schema_version": "tab.event/1",
        "event_id": f"evt-{seq:04d}",
        "seq": seq,
        "timestamp": ts,
        "channel": "ticket",
        "author": "A",
        "subject": "S",
        "body": "B",
        "world_changes": [],
    }
    ev.update(over)
    return ev


def _write(tmp_path: Path, events, payloads: dict[str, str] | None = None) -> Path:
    d = tmp_path / "ev"
    d.mkdir(exist_ok=True)
    for rel, text in (payloads or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    f = d / "events.jsonl"
    f.write_text("".join(json.dumps(e) + "\n" for e in events))
    return f


def test_valid_stream_loads_in_order(tmp_path):
    f = _write(tmp_path, [_ev(1), _ev(2, "2026-01-02T00:00:00Z"), _ev(3, "2026-01-02T00:00:00Z")])
    assert [e.seq for e in load_events(f)] == [1, 2, 3]


@pytest.mark.parametrize(
    "events,msg",
    [
        ([_ev(2), _ev(1)], "out of order"),
        ([_ev(1), _ev(3)], "out of order"),
        ([_ev(1), _ev(1)], "out of order"),
        ([_ev(1), _ev(2, event_id="evt-0001")], "duplicate"),
        ([_ev(1, "2026-02-01T00:00:00Z"), _ev(2, "2026-01-01T00:00:00Z")], "non-decreasing"),
        ([_ev(1, "2026-01-01 00:00:00")], "timestamp"),
        ([_ev(1, "2026-13-01T00:00:00Z")], "invalid timestamp"),
        ([_ev(1, channel="telepathy")], "channel"),
        ([_ev(1, schema_version="tab.event/2")], "schema_version"),
        ([_ev(1, event_id="E1")], "bad event_id"),
        ([{**_ev(1), "seq": True}], "seq"),
        ([_ev(1, body="")], "body"),
        ([{**_ev(1), "ground_truth": {"should_trigger": True}}], "unknown"),
        ([{k: v for k, v in _ev(1).items() if k != "author"}], "missing"),
        ([_ev(1, world_changes=[{"op": "write_file", "path": "../x", "content": "x"}])], "bad path"),
        ([_ev(1, world_changes=[{"op": "write_file", "path": "/abs", "content": "x"}])], "bad path"),
        ([_ev(1, world_changes=[{"op": "write_file", "path": "a"}])], "exactly one"),
        ([_ev(1, world_changes=[{"op": "chmod", "path": "a"}])], "unknown op"),
        ([_ev(1, world_changes=[{"op": "write_file", "path": "a", "source": "payloads/missing.txt"}])], "missing"),
        ([_ev(1, world_changes=[{"op": "write_file", "path": "a", "source": "../labels.json"}])], "bad source"),
        ([_ev(1, world_changes=[{"op": "write_file", "path": "a", "source": "events.jsonl"}])], "payloads/"),
        ([_ev(1, world_changes=[{"op": "delete_file", "path": "a", "expect_sha256": "nothex"}])], "expect_sha256"),
    ],
)
def test_invalid_streams_are_rejected(tmp_path, events, msg):
    with pytest.raises(EventValidationError, match=msg):
        load_events(_write(tmp_path, events))


def test_blank_line_rejected(tmp_path):
    f = _write(tmp_path, [_ev(1)])
    f.write_text(f.read_text() + "\n" + json.dumps(_ev(2)) + "\n")
    with pytest.raises(EventValidationError, match="blank"):
        load_events(f)


def test_payload_symlink_escape_rejected(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    f = _write(tmp_path, [_ev(1, world_changes=[{"op": "write_file", "path": "a", "source": "payloads/x.txt"}])],
               payloads={"payloads/.keep": ""})
    (f.parent / "payloads" / "x.txt").symlink_to(outside)
    with pytest.raises(EventValidationError, match="missing"):
        load_events(f)


def test_agent_view_exposes_paths_not_payloads(tmp_path):
    f = _write(
        tmp_path,
        [_ev(1, world_changes=[
            {"op": "write_file", "path": "b.txt", "source": "payloads/evt-0001/b.txt"},
            {"op": "write_file", "path": "a.txt", "content": "inline-payload"},
        ])],
        payloads={"payloads/evt-0001/b.txt": "payload-body"},
    )
    view = load_events(f)[0].agent_view().to_dict()
    assert view["changed_paths"] == [{"op": "write_file", "path": "a.txt"}, {"op": "write_file", "path": "b.txt"}]
    assert "payload-body" not in json.dumps(view) and "inline-payload" not in json.dumps(view)
    assert set(view) == {"schema_version", "event_id", "seq", "timestamp", "channel", "author", "subject", "body",
                         "changed_paths"}


def test_apply_event_records_conflicts_but_applies(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "f.txt").write_text("agent edited")
    f = _write(tmp_path, [_ev(1, world_changes=[
        {"op": "write_file", "path": "f.txt", "content": "world", "expect_sha256": "0" * 64},
        {"op": "delete_file", "path": "gone.txt"},
    ])])
    result = apply_event(load_events(f)[0], Workspace(root))
    assert (root / "f.txt").read_text() == "world"
    assert [c["reason"] for c in result.conflicts] == ["precondition", "missing"]


def test_payload_directory_symlink_escape_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.txt").write_text("not a payload")
    f = _write(tmp_path, [_ev(1, world_changes=[{"op": "write_file", "path": "a", "source": "payloads/linked/x.txt"}])],
               payloads={"payloads/.keep": ""})
    (f.parent / "payloads" / "linked").symlink_to(outside)
    with pytest.raises(EventValidationError, match="escapes payloads"):
        load_events(f)
