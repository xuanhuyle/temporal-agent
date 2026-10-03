"""Deterministic serialization, hashing, and tree utilities.

Every artifact the harness emits goes through :func:`canonical_json` so that two
runs with the same inputs produce byte-identical output (apart from fields
listed in :data:`VOLATILE_KEYS`). Output is ASCII-only (non-ASCII is escaped),
so any Python string, including lone surrogates, serializes without error.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any, Iterable

# Directory names and suffixes that are runtime by-products, never world state.
IGNORED_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
IGNORED_SUFFIXES = (".pyc", ".pyo")

# Keys whose values depend on wall-clock time or the host machine. They are
# recorded for humans but excluded from fingerprints and replay comparison.
VOLATILE_KEYS = frozenset(
    {"wall_clock_ms", "started_at", "finished_at", "traceback", "host", "git"}
)


def canonical_json(obj: Any) -> str:
    """Serialize ``obj`` deterministically (sorted keys, no whitespace, no NaN)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def pretty_json(obj: Any) -> str:
    """Human-readable but still deterministic JSON with a trailing newline."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_json(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def strip_volatile(obj: Any, extra_keys: Iterable[str] = ()) -> Any:
    """Return a copy of ``obj`` with volatile keys removed at every depth."""
    drop = VOLATILE_KEYS | frozenset(extra_keys)
    if isinstance(obj, dict):
        return {k: strip_volatile(v, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [strip_volatile(v, drop) for v in obj]
    return obj


def _is_ignored(name: str, is_dir: bool) -> bool:
    if is_dir:
        return name in IGNORED_DIR_NAMES
    return name.endswith(IGNORED_SUFFIXES)


def iter_tree(root: Path) -> list[tuple[str, Path]]:
    """List ``(relative_posix_path, absolute_path)`` for every file under ``root``.

    Symlinks are listed (never followed) so that hashing is a pure function of
    the tree itself. Output is sorted by relative path.
    """
    root = Path(root)
    out: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        kept_dirs = []
        for d in sorted(dirnames):
            full = current / d
            if full.is_symlink():
                # A symlinked directory is recorded as a link entry, not descended.
                out.append(((full.relative_to(root)).as_posix(), full))
            elif not _is_ignored(d, is_dir=True):
                kept_dirs.append(d)
        dirnames[:] = kept_dirs
        for f in filenames:
            if _is_ignored(f, is_dir=False):
                continue
            full = current / f
            out.append(((full.relative_to(root)).as_posix(), full))
    out.sort(key=lambda item: item[0])
    return out


def file_digest(path: Path) -> str:
    """Digest a single entry without following links or opening special files."""
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        return "symlink:" + sha256_text(os.readlink(path))
    if not stat.S_ISREG(st.st_mode):
        return f"special:{stat.S_IFMT(st.st_mode):o}"
    return sha256_bytes(path.read_bytes())


def tree_manifest(root: Path) -> list[list[str]]:
    return [[rel, file_digest(full)] for rel, full in iter_tree(root)]


def tree_hash(root: Path) -> str:
    """Content hash of a directory: sha256 over sorted ``path NUL digest`` lines."""
    h = hashlib.sha256()
    for rel, digest in tree_manifest(root):
        h.update(rel.encode("utf-8", "surrogateescape"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def copy_tree(src: Path, dst: Path, *, regular_only: bool = False) -> list[str]:
    """Copy a directory tree, skipping runtime by-products.

    With ``regular_only`` (used for evaluator snapshots and preserved final
    state) only regular files are copied, as fresh files: symlinks, FIFOs,
    sockets and devices are skipped. Otherwise symlinks are preserved as links
    and special files are still skipped. Returns the relative paths skipped.
    """
    src, dst = Path(src), Path(dst)
    skipped: list[str] = []
    dst.mkdir(parents=True, exist_ok=False)
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        current = Path(dirpath)
        rel_dir = current.relative_to(src)
        kept = []
        for d in sorted(dirnames):
            full = current / d
            if full.is_symlink():
                if regular_only:
                    skipped.append((rel_dir / d).as_posix())
                else:
                    os.symlink(os.readlink(full), dst / rel_dir / d)
            elif not _is_ignored(d, is_dir=True):
                kept.append(d)
                (dst / rel_dir / d).mkdir()
        dirnames[:] = kept
        for f in sorted(filenames):
            if _is_ignored(f, is_dir=False):
                continue
            full = current / f
            st = os.lstat(full)
            if stat.S_ISREG(st.st_mode):
                shutil.copyfile(full, dst / rel_dir / f, follow_symlinks=False)
            elif stat.S_ISLNK(st.st_mode) and not regular_only:
                os.symlink(os.readlink(full), dst / rel_dir / f)
            else:
                skipped.append((rel_dir / f).as_posix())
    return skipped
