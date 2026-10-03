"""Append-only JSONL writers and run fingerprints (``tab.trace/1``)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from harness.canonical import canonical_json, pretty_json, sha256_text, strip_volatile

TRACE_SCHEMA_VERSION = "tab.trace/1"

# Keys excluded from fingerprints: an agent's private state may legitimately
# embed its (random, absolute) state_dir path, so it is recorded but not hashed.
FINGERPRINT_EXEMPT_KEYS = ("state_tree",)

# Files whose canonical content defines a run's fingerprint.
FINGERPRINT_FILES = ("events.jsonl", "actions.jsonl", "trace.jsonl", "evaluation.jsonl", "scores.json")


def write_json_atomic(path: Path, obj: Any) -> None:
    """Write pretty JSON via a temp file + fsync + rename, so readers never see a partial file."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(pretty_json(obj))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class JsonlWriter:
    """Writes one canonical JSON object per line, flushed and fsynced per record.

    A crash therefore leaves only complete lines behind.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._fh = open(self.path, "x", encoding="utf-8")
        self.count = 0

    def write(self, record: dict[str, Any]) -> None:
        self._fh.write(canonical_json(record) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self.count += 1

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()


class TraceWriter(JsonlWriter):
    """Trace stream: every record gets a monotonically increasing ``idx``."""

    def emit(self, record_type: str, **fields: Any) -> dict[str, Any]:
        record = {"idx": self.count, "type": record_type, **fields}
        self.write(record)
        return record


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def canonical_records(path: Path, ignore_keys: Iterable[str] = ()) -> list[str]:
    """Canonical, volatile-free lines of a JSONL or JSON file."""
    path = Path(path)
    if path.suffix == ".jsonl":
        records = read_jsonl(path)
    else:
        records = [json.loads(path.read_text(encoding="utf-8"))]
    return [canonical_json(strip_volatile(r, ignore_keys)) for r in records]


def run_fingerprint(run_dir: Path, ignore_keys: Iterable[str] = ()) -> str:
    """sha256 over the canonical, volatile-free content of the fingerprinted files."""
    ignore_keys = tuple(ignore_keys) + FINGERPRINT_EXEMPT_KEYS
    parts = []
    for name in FINGERPRINT_FILES:
        parts.append(name)
        parts.extend(canonical_records(Path(run_dir) / name, ignore_keys))
    return sha256_text("\n".join(parts))
