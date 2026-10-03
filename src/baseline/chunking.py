"""Splitting workspace files into retrievable chunks (contestant code).

- Markdown: one chunk per heading section (headings inside code fences are
  ignored); each chunk carries the document title and its heading path.
- Python: a module header (docstring, imports, constants before the first
  definition) and one chunk per top-level ``def``/``class`` (decorators
  included). Files that do not parse are split by size.
- Everything else (JSON, TOML, SQL, text, ...): by size on line boundaries,
  with overlap.

Any chunk larger than ``chunk_chars`` is split further by size. Chunk ids are
stable: ``path#ordinal:sha256(text)[:12]``.
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass

__all__ = ["Chunk", "chunk_file", "split_by_size"]

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
_FENCE = re.compile(r"^[ \t]*(```|~~~)")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    path: str
    ordinal: int
    title: str  # document title / heading path / definition name
    start_line: int
    end_line: int
    text: str


def split_by_size(lines: list[str], start_line: int, chunk_chars: int, overlap: int) -> list[tuple[int, int, str]]:
    """Split ``lines`` (with line ends) into ``(start, end, text)`` windows of about ``chunk_chars``."""
    out: list[tuple[int, int, str]] = []
    n = len(lines)
    i = 0
    while i < n:
        size = 0
        j = i
        while j < n and (size + len(lines[j]) <= chunk_chars or j == i):
            size += len(lines[j])
            j += 1
        text = "".join(lines[i:j])
        if len(text) > chunk_chars * 2:  # a single enormous line
            text = text[: chunk_chars * 2]
        out.append((start_line + i, start_line + j - 1, text))
        if j >= n:
            break
        # step back over up to ``overlap`` characters of whole lines, always advancing
        back = 0
        k = j
        while k - 1 > i and back + len(lines[k - 1]) <= overlap:
            back += len(lines[k - 1])
            k -= 1
        i = max(k, i + 1)
    return out


def _segments_markdown(lines: list[str]) -> tuple[str, list[tuple[int, int, str]]]:
    """Heading sections as ``(start_idx, end_idx_exclusive, heading_path)``; also the document title."""
    title = ""
    stack: list[tuple[int, str]] = []
    bounds: list[tuple[int, str]] = []
    in_fence = False
    for idx, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line.rstrip("\n"))
        if not m:
            continue
        level, text = len(m.group(1)), m.group(2).strip()
        if level == 1 and not title:
            title = text
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))
        bounds.append((idx, " > ".join(t for _, t in stack)))
    segments: list[tuple[int, int, str]] = []
    if not bounds or bounds[0][0] > 0:
        first = bounds[0][0] if bounds else len(lines)
        if "".join(lines[:first]).strip():
            segments.append((0, first, ""))
    for n, (start, heading) in enumerate(bounds):
        end = bounds[n + 1][0] if n + 1 < len(bounds) else len(lines)
        segments.append((start, end, heading))
    return title, segments


def _segments_python(text: str, lines: list[str]) -> list[tuple[int, int, str]] | None:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    starts: list[tuple[int, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
            kind = "class" if isinstance(node, ast.ClassDef) else "def"
            starts.append((first, f"{kind} {node.name}"))
    segments: list[tuple[int, int, str]] = []
    first_def = starts[0][0] if starts else len(lines)
    if "".join(lines[:first_def]).strip():
        segments.append((0, first_def, "module header"))
    for n, (start, name) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        segments.append((start, end, name))
    return segments


def chunk_file(path: str, text: str, chunk_chars: int = 1500, overlap: int = 200) -> list[Chunk]:
    """Chunks of one file, in file order. Empty files yield no chunks."""
    if not text.strip():
        return []
    lines = text.splitlines(keepends=True)
    lower = path.lower()
    title = ""
    segments: list[tuple[int, int, str]] | None = None
    if lower.endswith((".md", ".markdown", ".rst")):
        title, segments = _segments_markdown(lines)
    elif lower.endswith(".py"):
        segments = _segments_python(text, lines)
    if segments is None:
        segments = [(0, len(lines), "")]

    pieces: list[tuple[int, int, str, str]] = []
    for start, end, heading in segments:
        seg_lines = lines[start:end]
        if not "".join(seg_lines).strip():
            continue
        if heading and title and not heading.startswith(title):
            label = f"{title} > {heading}"
        else:
            label = heading or title
        for s, e, chunk_text in split_by_size(seg_lines, start + 1, chunk_chars, overlap):
            if chunk_text.strip():
                pieces.append((s, e, label, chunk_text))

    out: list[Chunk] = []
    for ordinal, (s, e, label, chunk_text) in enumerate(pieces):
        digest = hashlib.sha256(chunk_text.encode("utf-8", "surrogatepass")).hexdigest()[:12]
        out.append(Chunk(f"{path}#{ordinal}:{digest}", path, ordinal, label, s, e, chunk_text))
    return out
