"""Deterministic application of events to an isolated world copy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from harness.canonical import copy_tree, tree_hash
from harness.events import Event
from harness.workspace import Workspace


@dataclass
class ApplyResult:
    ops: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ops": self.ops, "conflicts": self.conflicts}


def apply_event(event: Event, ws: Workspace) -> ApplyResult:
    """Apply an event's world changes to ``ws`` in order.

    The world is authoritative: a failed precondition (``expect_sha256``) or a
    delete of a missing file is recorded as a conflict but never aborts, so
    every contestant's world stays on the scripted track.
    """
    result = ApplyResult()
    for change in event.world_changes:
        before = ws.file_sha256(change.path)
        if change.expect_sha256 is not None and before != change.expect_sha256:
            result.conflicts.append(
                {"path": change.path, "reason": "precondition", "expected": change.expect_sha256, "actual": before}
            )
        if change.op == "write_file":
            assert change.data is not None
            ws.write_bytes(change.path, change.data)
        elif change.op == "delete_file":
            if before is None:
                result.conflicts.append({"path": change.path, "reason": "missing", "expected": None, "actual": None})
            else:
                ws.delete(change.path)
        else:  # pragma: no cover - rejected by the loader
            raise ValueError(f"unknown op {change.op}")
        result.ops.append({**change.summary(), "pre_sha256": before})
    return result


def world_only_hashes(seed_dir: Path, events: Iterable[Event], scratch: Path) -> list[str]:
    """Tree hash after each event when no agent touches the world."""
    root = Path(scratch) / "world"
    copy_tree(seed_dir, root)
    ws = Workspace(root)
    hashes = []
    for ev in events:
        apply_event(ev, ws)
        hashes.append(tree_hash(root))
    return hashes
