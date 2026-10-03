"""Message framing between the harness and a contestant process (``tab.wire/1``).

One JSON object per line, ASCII-only (non-ASCII escaped), sorted keys, no NaN.
The exchange is strictly sequential, so it is deterministic: the harness sends
one ``call``; the contestant answers with any number of ``tool`` requests
(each answered with one ``tool_result``) and finally one ``return`` or
``raise``.

Harness -> contestant:
    {"op": "call", "method": "describe"|"setup"|"on_start"|"on_event"|"teardown", "payload": {...}}
    {"op": "tool_result", "id": N, "ok": true, "value": ...}
    {"op": "tool_result", "id": N, "ok": false, "error": {"type": "ToolError"|"AccessDenied"|"ToolBoxClosed"|"BudgetExceeded", "message": str}}
    {"op": "budget_result", "id": N, "value": {...}}
    {"op": "shutdown"}
Contestant -> harness:
    {"op": "ready", "wire": "tab.wire/1", "pid": int}
    {"op": "tool", "id": N, "name": str, "args": {...}}
    {"op": "budget", "id": N}
    {"op": "return", "value": ..., "violations": [str]}
    {"op": "raise", "type": str, "message": str, "traceback": str, "violations": [str]}

This module is copied into contestant processes; it imports only the standard library.
"""

from __future__ import annotations

import json
import os
import select
import time
from typing import Any

WIRE_VERSION = "tab.wire/1"
MAX_MESSAGE_BYTES = 128 * 1024 * 1024


class WireError(Exception):
    """Malformed or oversized message, or the peer closed the channel."""


class WireTimeout(WireError):
    """No complete message arrived before the deadline."""


def encode(obj: Any) -> bytes:
    text = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("ascii") + b"\n"


def decode(line: bytes) -> dict[str, Any]:
    try:
        obj = json.loads(line.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise WireError(f"malformed message: {exc}") from None
    if not isinstance(obj, dict) or not isinstance(obj.get("op"), str):
        raise WireError("message must be an object with an 'op'")
    return obj


def write_message(fd: int, obj: Any) -> None:
    data = encode(obj)
    if len(data) > MAX_MESSAGE_BYTES:
        raise WireError("message too large")
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


class FrameReader:
    """Reads newline-framed messages from a file descriptor, with an optional deadline."""

    def __init__(self, fd: int) -> None:
        self.fd = fd
        self._buf = bytearray()
        self._eof = False

    def read(self, deadline: float | None = None) -> dict[str, Any]:
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                line = bytes(self._buf[:nl])
                del self._buf[: nl + 1]
                return decode(line)
            if len(self._buf) > MAX_MESSAGE_BYTES:
                raise WireError("message too large")
            if self._eof:
                raise WireError("channel closed")
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WireTimeout("deadline exceeded")
                ready, _, _ = select.select([self.fd], [], [], remaining)
                if not ready:
                    raise WireTimeout("deadline exceeded")
            chunk = os.read(self.fd, 1 << 20)
            if not chunk:
                self._eof = True
            else:
                self._buf.extend(chunk)
