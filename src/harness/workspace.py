"""Path-confined file access for an agent's isolated copy of the world.

A :class:`Workspace` is the *only* way contestant tools touch the filesystem.
It rejects anything that could reach outside its root: absolute paths, ``..``
segments, home expansion, backslashes, NUL bytes, symlinks anywhere along the
path, and any path that resolves into a protected root (evaluator ground
truth, future events, scenario manifests, run outputs) even if that root were
somehow nested inside the workspace.
"""

from __future__ import annotations

import errno
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Iterable

from harness.canonical import IGNORED_DIR_NAMES, IGNORED_SUFFIXES, sha256_bytes

MAX_FILE_BYTES = 1_000_000
MAX_SEARCH_RESULTS = 500


class ToolError(Exception):
    """A recoverable tool failure reported back to the agent."""


class AccessDenied(ToolError):
    """The requested path is outside what this workspace may touch."""


def validate_relpath(rel: object, *, allow_root: bool = False) -> tuple[str, ...]:
    """Validate a workspace-relative POSIX path and return its segments.

    Raises :class:`AccessDenied` for anything that is not a plain relative
    path made of ordinary segments. ``"."`` (the root itself) is only accepted
    when ``allow_root`` is true.
    """
    if not isinstance(rel, str):
        raise AccessDenied(f"path must be a string, got {type(rel).__name__}")
    if rel == "" or "\x00" in rel or "\\" in rel:
        raise AccessDenied(f"invalid path: {rel!r}")
    try:
        rel.encode("utf-8")
    except UnicodeEncodeError:
        raise AccessDenied(f"path is not valid UTF-8: {rel!r}") from None
    if rel.startswith("/") or rel.startswith("~") or re.match(r"^[A-Za-z]:", rel):
        raise AccessDenied(f"absolute paths are not allowed: {rel!r}")
    parts = []
    for part in rel.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise AccessDenied(f"parent traversal is not allowed: {rel!r}")
        parts.append(part)
    if not parts and not allow_root:
        raise AccessDenied(f"path refers to the workspace root: {rel!r}")
    return tuple(parts)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


class Workspace:
    """A directory tree an agent may read and write through tools."""

    def __init__(self, root: Path, protected: Iterable[Path] = ()) -> None:
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("workspace root must be a directory")
        self._protected = tuple(sorted({Path(p).resolve() for p in protected}))
        for p in self._protected:
            if _is_within(self.root, p):
                raise ValueError("workspace root lies inside a protected directory")

    # ------------------------------------------------------------------ paths
    def _resolve(self, rel: str, *, allow_root: bool = False) -> Path:
        parts = validate_relpath(rel, allow_root=allow_root)
        current = self.root
        for part in parts:
            current = current / part
            # Refuse symlinks anywhere along the path; lstat never follows.
            try:
                st = os.lstat(current)
            except FileNotFoundError:
                break
            if stat.S_ISLNK(st.st_mode):
                raise AccessDenied(f"symlinks are not allowed: {rel!r}")
        target = self.root.joinpath(*parts)
        resolved = target.resolve(strict=False)
        if not _is_within(resolved, self.root):
            raise AccessDenied(f"path escapes the workspace: {rel!r}")
        if self._is_protected(target):
            raise AccessDenied(f"path is protected: {rel!r}")
        return target

    def _is_protected(self, path: Path) -> bool:
        resolved = path.resolve(strict=False)
        return any(_is_within(resolved, p) for p in self._protected)

    def relpath(self, rel: str) -> str:
        """Normalized relative POSIX form of ``rel`` (validated)."""
        return "/".join(validate_relpath(rel))

    # ------------------------------------------------------------------ reads
    def exists(self, rel: str) -> bool:
        try:
            return self._resolve(rel).is_file()
        except AccessDenied:
            return False

    def read_bytes(self, rel: str) -> bytes:
        path = self._resolve(rel)
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except FileNotFoundError:
            raise ToolError(f"no such file: {rel!r}") from None
        except IsADirectoryError:
            raise ToolError(f"not a file: {rel!r}") from None
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise AccessDenied(f"symlinks are not allowed: {rel!r}") from None
            raise ToolError(f"cannot read {rel!r}: {exc.strerror}") from None
        with os.fdopen(fd, "rb") as fh:
            if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
                raise ToolError(f"not a regular file: {rel!r}")
            data = fh.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ToolError(f"file too large: {rel!r}")
        return data

    def read_text(self, rel: str) -> str:
        data = self.read_bytes(rel)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise ToolError(f"not a UTF-8 text file: {rel!r}") from None

    def file_sha256(self, rel: str) -> str | None:
        if not self.exists(rel):
            return None
        return sha256_bytes(self.read_bytes(rel))

    def list_files(self, prefix: str = ".") -> list[str]:
        base = self._resolve(prefix, allow_root=True)
        if base.is_file():
            return [self.relpath(prefix)]
        if not base.is_dir():
            raise ToolError(f"no such directory: {prefix!r}")
        out: list[str] = []
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            current = Path(dirpath)
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in IGNORED_DIR_NAMES
                and not (current / d).is_symlink()
                and not self._is_protected(current / d)
            )
            for f in filenames:
                full = current / f
                if f.endswith(IGNORED_SUFFIXES) or full.is_symlink():
                    continue
                out.append(full.relative_to(self.root).as_posix())
        out.sort()
        return out

    def search(self, pattern: str, prefix: str = ".") -> dict:
        if not isinstance(pattern, str) or not pattern:
            raise ToolError("search pattern must be a non-empty string")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"invalid regex: {exc}") from None
        matches = []
        truncated = False
        for rel in self.list_files(prefix):
            try:
                text = self.read_text(rel)
            except ToolError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    if len(matches) >= MAX_SEARCH_RESULTS:
                        truncated = True
                        break
                    matches.append({"path": rel, "line": lineno, "text": line})
            if truncated:
                break
        return {"matches": matches, "truncated": truncated}

    # ----------------------------------------------------------------- writes
    def _ensure_parent(self, target: Path, rel: str) -> None:
        parent = target.parent
        missing = []
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for d in reversed(missing):
            os.mkdir(d)
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise ToolError(f"parent is not a directory: {rel!r}")

    def write_bytes(self, rel: str, data: bytes) -> None:
        """Atomically create or replace a file.

        The content is written to a fresh temporary file in the same directory
        and renamed over the target, so the target always gets a new inode:
        a hard link planted in the workspace can never be written through.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise ToolError("content must be bytes")
        if len(data) > MAX_FILE_BYTES:
            raise ToolError(f"content too large for {rel!r}")
        target = self._resolve(rel)
        if target.is_dir() and not target.is_symlink():
            raise ToolError(f"is a directory: {rel!r}")
        self._ensure_parent(target, rel)
        # Re-validate after creating directories (defence in depth).
        target = self._resolve(rel)
        fd, tmp_name = tempfile.mkstemp(prefix=".tab-write-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(bytes(data))
            os.chmod(tmp_name, 0o644)
            os.replace(tmp_name, target)
        except BaseException:
            if os.path.lexists(tmp_name):
                os.unlink(tmp_name)
            raise

    def write_text(self, rel: str, content: str) -> None:
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        self.write_bytes(rel, content.encode("utf-8"))

    def clear_obstructions(self, rel: str) -> list[str]:
        """Make ``rel`` writable as a regular file (harness-only, for world changes).

        Removes a directory at ``rel`` and any non-directory standing where a
        parent directory must be. Returns the relative paths removed.
        """
        parts = validate_relpath(rel)
        removed: list[str] = []
        current = self.root
        for i, part in enumerate(parts):
            current = current / part
            last = i == len(parts) - 1
            try:
                st = os.lstat(current)
            except FileNotFoundError:
                break
            rel_here = "/".join(parts[: i + 1])
            if last and stat.S_ISDIR(st.st_mode):
                shutil.rmtree(current)
                removed.append(rel_here)
            elif not last and not stat.S_ISDIR(st.st_mode):
                os.unlink(current)
                removed.append(rel_here)
                break
        return removed

    def delete(self, rel: str) -> None:
        target = self._resolve(rel)
        if target.is_symlink() or not target.exists():
            raise ToolError(f"no such file: {rel!r}")
        if not target.is_file():
            raise ToolError(f"not a file: {rel!r}")
        os.unlink(target)
