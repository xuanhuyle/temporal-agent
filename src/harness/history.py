"""The shared, read-only world timeline (protocol amendment A1).

:class:`WorldHistory` holds the repository as authored by the world (the seed
plus the world changes of events ``1..k``) after every event revealed so far.
It backs the ``history``, ``list_at``, ``read_at`` and ``diff`` tools, which
every contestant gets identically.

Structural future-blindness: the runner keeps a private world-only copy of
the repository, applies each event to it at the same moment it applies the
event to the agents' workspaces, and only then calls :meth:`WorldHistory.reveal`.
``reveal`` accepts only ``revealed_seq + 1``, so a state that has not been
revealed does not exist in the object. No argument, path trick or error
message can produce it, and an unavailable seq gets the same error wording
whether it is negative, the next event, or absurd.

Only objective repository content is held: file bytes and, per state, the
event id, timestamp and changed paths. It holds no event prose, labels,
scenario identity, or any agent's private state. Agents' own workspace edits
are not part of the world timeline.

Storage is in memory and content-addressed: digest -> bytes, plus one
path -> digest map per state. Byte strings are immutable and are copied on
the way in, so later mutation of a caller's mapping cannot change history.
"""

from __future__ import annotations

import decimal
import difflib
import os
import stat
from pathlib import Path
from typing import Any, Mapping, Sequence

from harness.canonical import IGNORED_DIR_NAMES, IGNORED_SUFFIXES, sha256_bytes, tree_hash_from_files
from harness.errors import AccessDenied, ToolError
from harness.workspace import MAX_FILE_BYTES, validate_relpath

__all__ = ["WorldHistory", "MAX_DIFF_CHARS"]

# Cap on the ``diff`` text returned by one call; beyond it the text is cut and
# ``truncated`` is set. The ``files`` list is always complete.
MAX_DIFF_CHARS = 50_000

HISTORY_ENTRY_KEYS = ("seq", "event_id", "timestamp", "changed_paths", "tree_sha256")


def _format_int(value: int) -> str:
    """Decimal text of any int, including ones above ``sys.get_int_max_str_digits``.

    The unavailable-seq error must have the same form for every integer, so a
    huge seq must not turn into a different (``ValueError``) failure.
    """
    try:
        return str(value)
    except ValueError:
        return str(decimal.Decimal(value))


def _is_ignored_path(parts: Sequence[str]) -> bool:
    """True for runtime by-products that are never world state (``canonical.IGNORED_*``)."""
    return any(p in IGNORED_DIR_NAMES for p in parts[:-1]) or parts[-1].endswith(IGNORED_SUFFIXES)


def _split_lines(text: str) -> list[str]:
    """Split on ``\\n`` only (like git), keeping line ends; a last line may lack one."""
    parts = text.split("\n")
    lines = [p + "\n" for p in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _unified(old: str, new: str, path: str) -> str:
    out: list[str] = []
    for line in difflib.unified_diff(_split_lines(old), _split_lines(new), fromfile=f"a/{path}", tofile=f"b/{path}"):
        if line.endswith("\n"):
            out.append(line)
        else:
            out.append(line + "\n\\ No newline at end of file\n")
    return "".join(out)


def _decode(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


class WorldHistory:
    """The revealed world timeline: states ``0..revealed_seq``, nothing later."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}
        self._states: list[dict[str, str]] = []  # per state: normalized path -> digest
        self._entries: list[dict[str, Any]] = []

    # ---------------------------------------------------------------- status
    @property
    def revealed_seq(self) -> int:
        """The latest revealed state (``-1`` before the first reveal)."""
        return len(self._states) - 1

    # ---------------------------------------------------------------- harness
    def reveal(
        self,
        seq: int,
        files: Mapping[str, bytes],
        *,
        event_id: str | None,
        timestamp: str | None,
        changed_paths: Sequence[Mapping[str, str]],
    ) -> str:
        """Add state ``seq`` (the world after event ``seq``; 0 is the seed). Harness-only.

        ``files`` maps workspace-relative POSIX paths to file contents, as
        produced by :meth:`snapshot_files`. Cache by-products are dropped.
        Returns the state's tree hash, equal to ``canonical.tree_hash`` of an
        equivalent directory of regular files. Raises ``ValueError`` (not a
        tool error: a mistake here is a harness bug) for an out-of-order seq or
        malformed input; nothing is stored in that case.
        """
        if not isinstance(seq, int) or isinstance(seq, bool):
            raise ValueError(f"reveal: seq must be an integer, got {type(seq).__name__}")
        expected = self.revealed_seq + 1
        if seq != expected:
            raise ValueError(f"reveal: expected seq {expected}, got {_format_int(seq)}")
        if seq == 0:
            if event_id is not None or timestamp is not None:
                raise ValueError("reveal: state 0 (the seed) has no event_id or timestamp")
        else:
            if not isinstance(event_id, str) or not event_id:
                raise ValueError("reveal: event_id must be a non-empty string")
            if not isinstance(timestamp, str) or not timestamp:
                raise ValueError("reveal: timestamp must be a non-empty string")
        changes = self._copy_changed_paths(changed_paths)
        if seq == 0 and changes:
            raise ValueError("reveal: state 0 (the seed) has no changed paths")
        snapshot = self._copy_files(files)

        digests: dict[str, str] = {}
        new_blobs: dict[str, bytes] = {}
        for rel in sorted(snapshot):
            data = snapshot[rel]
            digest = sha256_bytes(data)
            digests[rel] = digest
            if digest not in self._blobs:
                new_blobs[digest] = data
        tree_sha = tree_hash_from_files(snapshot)

        # Commit only after every check has passed.
        self._blobs.update(new_blobs)
        self._states.append(digests)
        self._entries.append(
            {
                "seq": seq,
                "event_id": event_id,
                "timestamp": timestamp,
                "changed_paths": changes,
                "tree_sha256": tree_sha,
            }
        )
        return tree_sha

    @staticmethod
    def _copy_changed_paths(changed_paths: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        if isinstance(changed_paths, (str, bytes)) or not isinstance(changed_paths, Sequence):
            raise ValueError("reveal: changed_paths must be a sequence of {op, path} mappings")
        out: list[dict[str, str]] = []
        for item in changed_paths:
            if not isinstance(item, Mapping):
                raise ValueError("reveal: each changed path must be a mapping with op and path")
            op, path = item.get("op"), item.get("path")
            if not isinstance(op, str) or not isinstance(path, str):
                raise ValueError("reveal: changed path op and path must be strings")
            # Only op and path are kept, whatever else the mapping carries.
            out.append({"op": op, "path": path})
        return out

    @staticmethod
    def _copy_files(files: Mapping[str, bytes]) -> dict[str, bytes]:
        if not isinstance(files, Mapping):
            raise ValueError("reveal: files must be a mapping of relative path -> bytes")
        out: dict[str, bytes] = {}
        for rel, data in list(files.items()):
            try:
                parts = validate_relpath(rel)
            except AccessDenied as exc:
                raise ValueError(f"reveal: {exc}") from None
            norm = "/".join(parts)
            if norm != rel:
                raise ValueError(f"reveal: path is not in normalized form: {rel!r}")
            if not isinstance(data, (bytes, bytearray, memoryview)):
                raise ValueError(f"reveal: content of {rel!r} must be bytes")
            if _is_ignored_path(parts):
                continue
            out[norm] = bytes(data)  # a private immutable copy
        names = set(out)
        for rel in out:
            parts = rel.split("/")
            for i in range(1, len(parts)):
                if "/".join(parts[:i]) in names:
                    raise ValueError(f"reveal: {rel!r} lies under a path that is a file")
        return out

    @staticmethod
    def snapshot_files(root: Path) -> dict[str, bytes]:
        """Regular files under ``root`` as ``{relative_posix_path: bytes}``, sorted by path.

        Symlinks (to files or directories) and special files (FIFOs, sockets,
        devices) are skipped, never followed or opened, and so are cache
        by-products (``canonical.IGNORED_*``).
        """
        root = Path(root)
        out: dict[str, bytes] = {}
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)
            dirnames[:] = sorted(
                d for d in dirnames if d not in IGNORED_DIR_NAMES and not (current / d).is_symlink()
            )
            for name in filenames:
                if name.endswith(IGNORED_SUFFIXES):
                    continue
                full = current / name
                if not stat.S_ISREG(os.lstat(full).st_mode):
                    continue
                # O_NOFOLLOW and the fstat re-check close the window between lstat and open.
                fd = os.open(full, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
                with os.fdopen(fd, "rb") as fh:
                    if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
                        continue
                    data = fh.read()
                out[full.relative_to(root).as_posix()] = data
        return {rel: out[rel] for rel in sorted(out)}

    # ------------------------------------------------------------ contestant
    def _state(self, seq: object) -> dict[str, str]:
        """The path -> digest map of a revealed state, or a ToolError of fixed form."""
        if not isinstance(seq, int) or isinstance(seq, bool):
            raise ToolError(f"seq must be an integer, got {type(seq).__name__}")
        latest = self.revealed_seq
        if seq < 0 or seq > latest:
            available = f"0..{latest}" if latest >= 0 else "none"
            raise ToolError(f"no repository state at seq {_format_int(seq)}; available: {available}")
        return self._states[seq]

    def history(self) -> list[dict[str, Any]]:
        """One entry per revealed state: ``{seq, event_id, timestamp, changed_paths, tree_sha256}``."""
        return [
            {
                "seq": e["seq"],
                "event_id": e["event_id"],
                "timestamp": e["timestamp"],
                "changed_paths": [dict(c) for c in e["changed_paths"]],
                "tree_sha256": e["tree_sha256"],
            }
            for e in self._entries
        ]

    def list_at(self, seq: int, prefix: str = ".") -> list[str]:
        """Sorted files of state ``seq`` under ``prefix`` (same semantics as ``Workspace.list_files``)."""
        state = self._state(seq)
        parts = validate_relpath(prefix, allow_root=True)
        if not parts:
            return sorted(state)
        norm = "/".join(parts)
        if norm in state:
            return [norm]
        under = sorted(p for p in state if p.startswith(norm + "/"))
        if not under:
            raise ToolError(f"no such directory: {prefix!r}")
        return under

    def read_at(self, seq: int, path: str) -> str:
        """UTF-8 contents of ``path`` in state ``seq``."""
        state = self._state(seq)
        norm = "/".join(validate_relpath(path))
        digest = state.get(norm)
        if digest is None:
            if any(p.startswith(norm + "/") for p in state):
                raise ToolError(f"not a file: {path!r}")
            raise ToolError(f"no such file: {path!r}")
        data = self._blobs[digest]
        if len(data) > MAX_FILE_BYTES:
            raise ToolError(f"file too large: {path!r}")
        text = _decode(data)
        if text is None:
            raise ToolError(f"not a UTF-8 text file: {path!r}")
        return text

    def diff(self, seq_a: int, seq_b: int, path: str | None = None) -> dict[str, Any]:
        """Unified diff from state ``seq_a`` to state ``seq_b`` (either order).

        ``path`` limits the diff to one file or to everything under a
        directory; a filter that matches nothing gives an empty diff. Returns
        ``{seq_a, seq_b, path, files: [{path, status}], diff, truncated}`` where
        ``status`` is ``added``, ``deleted`` or ``modified``, ``files`` is
        sorted by path, and ``path`` is the normalized filter (``None`` when
        absent). Non-UTF-8 files are listed but not diffed. The text is capped
        at :data:`MAX_DIFF_CHARS`.
        """
        state_a = self._state(seq_a)
        state_b = self._state(seq_b)
        norm: str | None = None
        if path is not None:
            parts = validate_relpath(path, allow_root=True)
            norm = "/".join(parts) if parts else "."

        def selected(p: str) -> bool:
            return norm is None or norm == "." or p == norm or p.startswith(norm + "/")

        files: list[dict[str, str]] = []
        chunks: list[str] = []
        size = 0
        truncated = False
        for p in sorted(set(state_a) | set(state_b)):
            if not selected(p):
                continue
            da, db = state_a.get(p), state_b.get(p)
            if da == db:
                continue
            status = "added" if da is None else "deleted" if db is None else "modified"
            files.append({"path": p, "status": status})
            if truncated:
                continue  # keep listing files; the text is already full
            old = "" if da is None else _decode(self._blobs[da])
            new = "" if db is None else _decode(self._blobs[db])
            if old is None or new is None:
                chunk = f"Binary files a/{p} and b/{p} differ\n"
            else:
                chunk = _unified(old, new, p)
            if size + len(chunk) > MAX_DIFF_CHARS:
                chunks.append(chunk[: MAX_DIFF_CHARS - size])
                size = MAX_DIFF_CHARS
                truncated = True
            else:
                chunks.append(chunk)
                size += len(chunk)
        return {
            "seq_a": seq_a,
            "seq_b": seq_b,
            "path": norm,
            "files": files,
            "diff": "".join(chunks),
            "truncated": truncated,
        }
