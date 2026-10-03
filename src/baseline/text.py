"""Code-aware tokenization and entity extraction for the baseline's indexes (contestant code).

Generic text processing; nothing here knows any scenario's content.

:func:`tokenize` lowercases, splits on non-alphanumerics, splits
``snake_case`` and ``camelCase`` identifiers into their parts while keeping
the whole identifier as an extra token, keeps record ids (``adr-0004``),
dotted names (``client.retry_policy``), file paths and version numbers as
extra tokens, drops a small stopword list, and applies a light, deterministic
suffix stemmer to plain words.

:func:`extract_entities` returns typed entity keys used by the retriever's
entity channel: ``id:ADR-0004``, ``path:docs/adr/x.md``, ``file:x.md``,
``ver:2.1.0``, ``sym:retry_policy``.
"""

from __future__ import annotations

import re

__all__ = ["tokenize", "stem", "extract_entities", "STOPWORDS", "canonical_id"]

STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has have he her his how i if in into
    is it its me my of on or our ours she so such than that the their them then there these they this those to
    too was we were what when where which while who whom why will with would you your yours""".split()
)

_RECORD_ID = re.compile(r"\b(adr|tck)[-_ ]?0*(\d{1,6})\b", re.I)
_GENERIC_ID = re.compile(r"\b([A-Z][A-Z0-9]{1,9})-(\d{2,6})\b")
_WORD = re.compile(r"[A-Za-z0-9_]+")
_CAMEL_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")
_DOTTED = re.compile(r"(?<![\w.])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+(?![\w])")
_VERSION = re.compile(r"(?<![\w.])v?(\d+(?:\.\d+){1,3})(?![\w.]*[A-Za-z_])")
_FILE_EXTS = (
    "py", "md", "json", "toml", "txt", "yaml", "yml", "cfg", "ini", "csv", "sql", "sh", "js", "ts", "lock",
    "html", "css", "xml", "rst", "env", "j2", "tpl",
)
_PATH = re.compile(
    r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+|[\w.-]+\.(?:" + "|".join(_FILE_EXTS) + r"))(?![\w/-])"
)
_SNAKE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b")
_CAMEL = re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b")


def canonical_id(prefix: str, number: str) -> str:
    return f"{prefix.upper()}-{int(number):04d}"


def stem(word: str) -> str:
    """Light suffix stemmer for lowercase alphabetic words (deterministic, conservative)."""
    w = word
    if len(w) <= 3 or not w.isalpha():
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")) and len(w) > 3:
        w = w[:-1]
    stripped = False
    if w.endswith("ing") and len(w) > 5:
        w, stripped = w[:-3], True
    elif w.endswith("ed") and len(w) > 4:
        w, stripped = w[:-2], True
    elif w.endswith("ly") and len(w) > 5:
        w = w[:-2]
    if stripped and len(w) > 2 and w[-1] == w[-2] and w[-1] not in "aeiouslz":
        w = w[:-1]
    if w.endswith("e") and len(w) >= 4:
        w = w[:-1]
    return w


def _parts(identifier: str) -> list[str]:
    out: list[str] = []
    for piece in identifier.split("_"):
        if piece:
            out.extend(_CAMEL_PART.findall(piece))
    return out


def tokenize(text: str) -> list[str]:
    """Tokens of ``text`` in order of appearance (with repetitions, for term frequencies)."""
    tokens: list[str] = []
    for m in _WORD.finditer(text):
        raw = m.group(0)
        parts = _parts(raw)
        lower = raw.lower().strip("_")
        if not lower:
            continue
        if len(parts) > 1:
            tokens.append(lower)
            for p in parts:
                pl = p.lower()
                if pl in STOPWORDS or (len(pl) == 1 and not pl.isdigit()):
                    continue
                tokens.append(stem(pl))
        else:
            if lower in STOPWORDS or (len(lower) == 1 and not lower.isdigit()):
                continue
            tokens.append(stem(lower))
    for m in _RECORD_ID.finditer(text):
        tokens.append(canonical_id(m.group(1), m.group(2)).lower())
    for m in _DOTTED.finditer(text):
        tokens.append(m.group(0).lower())
    for m in _VERSION.finditer(text):
        tokens.append(m.group(1))
    for m in _PATH.finditer(text):
        p = _norm_path(m.group(1))
        if "/" in p:
            tokens.append(p.lower())
    return tokens


def _norm_path(p: str) -> str:
    return "/".join(part for part in p.split("/") if part not in ("", "."))


def extract_entities(text: str) -> list[str]:
    """Sorted, de-duplicated entity keys mentioned in ``text``."""
    found: set[str] = set()
    for m in _RECORD_ID.finditer(text):
        found.add("id:" + canonical_id(m.group(1), m.group(2)))
    for m in _GENERIC_ID.finditer(text):
        found.add("id:" + canonical_id(m.group(1), m.group(2)))
    for m in _PATH.finditer(text):
        p = _norm_path(m.group(1)).rstrip(".")
        if not p or p.startswith(".."):
            continue
        base = p.rsplit("/", 1)[-1]
        has_ext = "." in base and base.rsplit(".", 1)[-1].lower() in _FILE_EXTS
        if "/" in p:
            found.add("path:" + p)
        if has_ext:
            found.add("file:" + base)
    for m in _VERSION.finditer(text):
        found.add("ver:" + m.group(1))
    for m in _DOTTED.finditer(text):
        name = m.group(0)
        if name.rsplit(".", 1)[-1].lower() in _FILE_EXTS:
            continue
        found.add("sym:" + name.lower())
    for m in _SNAKE.finditer(text):
        found.add("sym:" + m.group(0).lower())
    for m in _CAMEL.finditer(text):
        found.add("sym:" + m.group(0).lower())
    return sorted(found)
