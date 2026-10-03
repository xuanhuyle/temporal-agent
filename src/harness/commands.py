"""Controlled command execution for contestants: ``run_command`` (amendment A2).

A :class:`CommandRunner` runs one of a few command shapes in an agent's
workspace, never through a shell:

- ``pytest ARGS...`` / ``python -m pytest ARGS...``, run as
  ``pytest -p no:cacheprovider ARGS...``;
- ``python -m MODULE ARGS...`` (dotted identifier);
- ``python PATH.py ARGS...``, where ``PATH.py`` is a workspace-relative,
  validated, existing regular file reached without symlinks;
- ``python -c CODE ARGS...``.

``python3`` is an alias of ``python``. The command is split with
:func:`shlex.split` (POSIX rules), so shell metacharacters such as ``|``,
``>``, ``;`` or ``$(...)`` are ordinary arguments. Anything else raises
:class:`~harness.errors.ToolError`.

Execution (``docs/milestone-2-design.md`` section 3):

- the child is ``[python, "-s", "-B", <scratch>/boot/tab_cmd_boot.py, <fd>]``
  with ``cwd`` = the workspace, stdin from ``/dev/null``, stdout and stderr
  merged, in a new session (its own process group), and an environment built
  from scratch (no inherited variables: no credentials, proxies or
  ``PYTHONPATH``);
- the bootstrap and a copy of :mod:`harness.tripwire` are written into the
  scratch directory; the bootstrap imports nothing from the repository. Its
  configuration (paths, target) arrives over an inherited pipe, so no host
  path appears in the child's argv or environment beyond ``HOME``/``TMPDIR``.
  It sets rlimits, installs the tripwire (reads: workspace, the
  interpreter's stdlib and site-packages, ``/usr/share/zoneinfo``; writes:
  workspace and scratch ``tmp``/``home``; no network, processes or ctypes),
  then runs the target with :mod:`runpy` (or ``exec`` for ``-c``). Tripwire
  refusals are streamed back over a second inherited pipe;
- on timeout the process group is killed with ``SIGKILL`` (``timed_out``,
  ``exit_code`` ``None``); the group is killed after every command anyway,
  and the scratch ``tmp`` and ``home`` are wiped;
- output is decoded as UTF-8 (incrementally, with replacement) and
  normalized for determinism *while it streams*, then truncated (head and a
  larger tail), so truncation is decided on normalized text and never depends
  on host path lengths. Normalized (see :class:`_Normalizer`):

  * the workspace path (as given and resolved) -> ``.``; the scratch
    directory, its ``tmp`` and pytest's relative form of it -> ``<tmp>``;
  * pytest durations: ``in 0.12s`` / ``in 61.03s (0:01:01)`` -> ``in <t>s``;
    ``--durations`` rows ``0.01s call ...`` -> ``<t>s call ...`` and the
    ``(N durations < 0.005s hidden.`` count -> ``<n>`` (which rows appear can
    still depend on timing; that is inherent to ``--durations``);
  * object addresses: ``0x`` followed by 6 or more hex digits, delimited by
    non-alphanumerics (``<Foo object at 0x7f3a2c1d9e80>``, ``id=0x55d0c3a1``)
    -> ``0x<addr>``. Shorter constants such as ``0x1F`` or ``0xFFFF`` are kept.

  Not normalized: host facts that are constant per host and interpreter
  (pytest's ``platform ... -- Python 3.11.x, pytest-x.y`` header, stdlib
  paths in tracebacks, the user name in ``pytest-of-<user>``) and decimal
  ``id()`` values a program prints itself.

The tripwire is not a sandbox; see ``harness.tripwire`` and the design doc.
"""

from __future__ import annotations

import codecs
import json
import os
import re
import selectors
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from harness import tripwire as _tripwire_module
from harness.errors import ToolError
from harness.workspace import validate_relpath

__all__ = [
    "CommandPlan",
    "CommandRunner",
    "parse_command",
    "normalize_output",
    "truncate_output",
    "BOOT_NAME",
    "FSIZE_LIMIT_BYTES",
]

BOOT_NAME = "tab_cmd_boot.py"
_TRIPWIRE_COPY = "_tab_tripwire.py"
FSIZE_LIMIT_BYTES = 64 * 1024 * 1024
MAX_VIOLATIONS = 50
_MAX_VIOLATION_CHARS = 500
_DRAIN_S = 2.0
_POLL_S = 0.05
_READ_CHUNK = 65536

_MODULE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_PYTHONS = ("python", "python3")


# --------------------------------------------------------------------- grammar
@dataclass(frozen=True)
class CommandPlan:
    """A parsed, validated command.

    ``kind`` is ``"module"``, ``"script"`` or ``"code"``; ``target`` is the
    module name, the workspace-relative script path, or the code. ``argv`` is
    what the child's ``sys.argv`` starts as; ``logical_argv`` is the
    normalized command shown to the agent (never a host path).
    """

    kind: str
    target: str
    argv: tuple[str, ...]
    logical_argv: tuple[str, ...]


def _pytest_plan(args: Sequence[str]) -> CommandPlan:
    return CommandPlan(
        kind="module",
        target="pytest",
        argv=("pytest", "-p", "no:cacheprovider", *args),
        logical_argv=("pytest", *args),
    )


def _check_script(workspace_root: Path, rel: str) -> str:
    parts = validate_relpath(rel)  # AccessDenied (a ToolError) for absolute, '..', '~', ...
    current = Path(workspace_root)
    for i, part in enumerate(parts):
        current = current / part
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            raise ToolError(f"run_command: no such script in the workspace: {rel!r}") from None
        except OSError as exc:
            raise ToolError(f"run_command: cannot use script {rel!r}: {exc.strerror}") from None
        if stat.S_ISLNK(st.st_mode):
            raise ToolError(f"run_command: symlinks are not allowed in script paths: {rel!r}")
        last = i == len(parts) - 1
        if not last and not stat.S_ISDIR(st.st_mode):
            raise ToolError(f"run_command: no such script in the workspace: {rel!r}")
        if last and not stat.S_ISREG(st.st_mode):
            raise ToolError(f"run_command: script is not a regular file: {rel!r}")
    return "/".join(parts)


def parse_command(command: object, workspace_root: Path) -> CommandPlan:
    """Parse ``command`` against the grammar above; raise :class:`ToolError` if it is not allowed."""
    if not isinstance(command, str):
        raise ToolError(f"run_command: command must be a string, got {type(command).__name__}")
    if "\x00" in command:
        raise ToolError("run_command: command contains a NUL character")
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ToolError(f"run_command: cannot parse command: {exc}") from None
    if not tokens:
        raise ToolError("run_command: empty command")
    program, rest = tokens[0], tokens[1:]
    if program == "pytest":
        return _pytest_plan(rest)
    if program not in _PYTHONS:
        raise ToolError(
            f"run_command: program {program!r} is not allowed; use 'pytest ARGS', 'python -m MODULE ARGS', "
            "'python PATH.py ARGS' or 'python -c CODE ARGS' (no shell)"
        )
    if not rest:
        raise ToolError("run_command: interactive python is not supported; use -m MODULE, -c CODE or PATH.py")
    head, args = rest[0], rest[1:]
    if head == "-m" or (head.startswith("-m") and len(head) > 2):
        if head == "-m":
            if not args:
                raise ToolError("run_command: python -m requires a module name")
            module, args = args[0], args[1:]
        else:
            module = head[2:]
        if not _MODULE_RE.match(module):
            raise ToolError(f"run_command: invalid module name: {module!r}")
        if module == "pytest":
            return _pytest_plan(args)
        return CommandPlan("module", module, (module, *args), ("python", "-m", module, *args))
    if head == "-c" or (head.startswith("-c") and len(head) > 2):
        if head == "-c":
            if not args:
                raise ToolError("run_command: python -c requires code")
            code, args = args[0], args[1:]
        else:
            code = head[2:]
        return CommandPlan("code", code, ("-c", *args), ("python", "-c", code, *args))
    if head.startswith("-"):
        raise ToolError(f"run_command: python option {head!r} is not allowed; only -m MODULE and -c CODE are supported")
    if not head.endswith(".py"):
        raise ToolError(f"run_command: python scripts must be workspace-relative .py files, got {head!r}")
    rel = _check_script(workspace_root, head)
    return CommandPlan("script", rel, (rel, *args), ("python", rel, *args))


# ------------------------------------------------------------------ output
_DURATION_SRC = r"\bin \d+(?:\.\d+)?s(?: \(\d+:\d{2}:\d{2}\))?"
# pytest --durations rows: f"{duration:02.2f}s {when:<8} {nodeid}" at the start of a line.
_DURATION_ROW_SRC = r"(?<=\n)\d+\.\d+s(?= +(?:setup|call|teardown)\b)"
_HIDDEN_COUNT_SRC = r"(?<=\()\d+(?= durations < \d)"
# Object addresses (id/repr): 0x and at least 6 hex digits, not part of a longer word.
_ADDRESS_SRC = r"(?<![0-9A-Za-z_])0x[0-9a-fA-F]{6,}(?![0-9A-Za-z_])"
_FIXED_TOKENS = {"dur": "in <t>s", "row": "<t>s", "hidden": "<n>", "addr": "0x<addr>"}
# A line longer than this many characters is normalized in pieces (memory stays bounded);
# a piece always keeps the last _LONG_LINE_KEEP characters back for context.
_LONG_LINE_CHARS = 1 << 18
_LONG_LINE_KEEP = 1 << 16


class _Normalizer:
    """One-pass normalizer: host paths (longest first), pytest durations and object addresses.

    Every pattern lies within one line and looks at most one character
    before or after a match, so text can be normalized in pieces cut after a
    newline (or, for very long lines, away from any match) with the same
    result as normalizing it whole; see :class:`_OutputStream`.
    """

    def __init__(self, replacements: Sequence[tuple[str, str]]) -> None:
        tokens: dict[str, str] = {}
        for path, token in sorted(set(replacements), key=lambda pt: (-len(pt[0]), pt)):
            if path and path != os.sep:
                tokens.setdefault(path, token)
        self._tokens = tokens
        branches = []
        if tokens:
            alternation = "|".join(re.escape(p) for p in tokens)  # dict order: longest first
            # Do not rewrite a longer sibling name such as "<ws>2" or "<ws>-old".
            branches.append(rf"(?P<path>(?<![\w.-])(?:{alternation})(?![\w-]))")
        branches += [
            rf"(?P<dur>{_DURATION_SRC})",
            rf"(?P<row>{_DURATION_ROW_SRC})",
            rf"(?P<hidden>{_HIDDEN_COUNT_SRC})",
            rf"(?P<addr>{_ADDRESS_SRC})",
        ]
        self.pattern = re.compile("|".join(branches))
        self.longest = max((len(p) for p in tokens), default=0)
        # Every match contains one of these substrings (or has it in its lookahead on the same line);
        # text without any of them is left as it is without running the regex (output floods).
        self._triggers = tuple(tokens) + ("in ", "0x", "durations", "setup", "call", "teardown")

    def matches(self, text: str, start: int, end: int) -> list[re.Match[str]]:
        """The matches in ``text[start:end]``; ``text[start - 1]`` is context (lookbehind) only."""
        if not any(text.find(t, start, end) >= 0 for t in self._triggers):
            return []
        return list(self.pattern.finditer(text, start, end))

    def token(self, match: re.Match[str]) -> str:
        kind = match.lastgroup
        if kind == "path":
            return self._tokens[match.group()]
        return _FIXED_TOKENS[kind]  # type: ignore[index]

    def substitute(self, text: str, matches: Sequence[re.Match[str]], start: int, end: int) -> str:
        """``text[start:end]`` with ``matches`` (all within it, in order) replaced by their tokens."""
        out = []
        pos = start
        for m in matches:
            out.append(text[pos:m.start()])
            out.append(self.token(m))
            pos = m.end()
        out.append(text[pos:end])
        return "".join(out)

    def segment(self, text: str, start: int, end: int) -> str:
        """Normalize ``text[start:end]``; ``text[start - 1]`` is context (lookbehind) only."""
        return self.substitute(text, self.matches(text, start, end), start, end)

    def __call__(self, text: str) -> str:
        buf = "\n" + text  # a newline before the start: same as start-of-text for every pattern
        return self.segment(buf, 1, len(buf))


def normalize_output(text: str, replacements: Sequence[tuple[str, str]]) -> str:
    """Replace host paths (longest first), pytest durations and object addresses so output is deterministic."""
    return _Normalizer(replacements)(text)


def _truncation_marker(omitted: int) -> str:
    return f"\n[... output truncated: {omitted} characters omitted ...]\n"


def truncate_output(text: str, max_chars: int) -> tuple[str, bool]:
    """Keep a head and a larger tail of ``text`` (``max_chars`` characters in all), with a marker between.

    Returns ``(text, truncated)``.
    """
    if len(text) <= max_chars:
        return text, False
    head_n = max_chars // 4
    tail_n = max_chars - head_n
    omitted = len(text) - head_n - tail_n
    return text[:head_n] + _truncation_marker(omitted) + text[len(text) - tail_n:], True


class _TextWindow:
    """Bounded record of a text stream that renders exactly as ``truncate_output(whole_text, max_chars)``."""

    def __init__(self, max_chars: int) -> None:
        self.max_chars = max_chars
        self.head_n = max_chars // 4
        self.tail_n = max_chars - self.head_n
        self.head = ""
        self.tail = ""
        self.total = 0

    def add(self, text: str) -> None:
        if not text:
            return
        self.total += len(text)
        if len(self.head) < self.max_chars:
            self.head += text[: self.max_chars - len(self.head)]
        self.tail += text
        if len(self.tail) > 2 * self.tail_n:
            self.tail = self.tail[-self.tail_n:]

    def render(self) -> tuple[str, bool]:
        if self.total <= self.max_chars:
            return self.head, False
        omitted = self.total - self.head_n - self.tail_n
        return self.head[: self.head_n] + _truncation_marker(omitted) + self.tail[-self.tail_n:], True


class _OutputStream:
    """Decode, normalize and window a child's output as it arrives, in bounded memory.

    The result equals ``truncate_output(normalize(decode(all_bytes)), max_chars)``
    whatever the chunking, so it never depends on where the host's absolute
    paths (of varying length) made the raw byte stream cross a buffer limit.
    Text is normalized up to the last complete line; a line longer than
    ``_LONG_LINE_CHARS`` is cut away from any match, keeping the last
    ``_LONG_LINE_KEEP`` characters back (exact unless a single digit/hex run
    or path is longer than that).
    """

    def __init__(self, normalizer: _Normalizer, max_chars: int) -> None:
        self._norm = normalizer
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._buf = "\n"  # _buf[0] is context only (the character before the pending text)
        self._window = _TextWindow(max_chars)
        self._keep = max(_LONG_LINE_KEEP, 2 * normalizer.longest + 64)
        self._long = max(_LONG_LINE_CHARS, 2 * self._keep)

    def feed(self, data: bytes) -> None:
        self._push(self._decoder.decode(data))

    def _push(self, text: str) -> None:
        if not text:
            return
        base = len(self._buf)
        self._buf += text
        nl = text.rfind("\n")
        if nl >= 0:
            cut = base + nl + 1
            self._window.add(self._norm.segment(self._buf, 1, cut))
            self._buf = self._buf[cut - 1:]
        if len(self._buf) - 1 > self._long:
            self._cut_long_line()

    def _cut_long_line(self) -> None:
        buf = self._buf
        pos = len(buf) - self._keep
        done: list[re.Match[str]] = []
        for m in self._norm.matches(buf, 1, len(buf)):
            if m.end() <= pos:
                done.append(m)
                continue
            if m.start() < pos:
                pos = m.start()  # never cut through a match
            break
        if pos <= 1:  # one match longer than the whole window: cut anyway, memory must stay bounded
            pos = len(buf) - self._keep
            done = [m for m in done if m.end() <= pos]
        self._window.add(self._norm.substitute(buf, done, 1, pos))
        self._buf = buf[pos - 1:]

    def finish(self) -> tuple[str, bool]:
        self._push(self._decoder.decode(b"", final=True))
        self._window.add(self._norm.segment(self._buf, 1, len(self._buf)))
        self._buf = "\n"
        return self._window.render()


# --------------------------------------------------------------- bootstrap
_BOOT_SOURCE = r'''"""Command bootstrap written by harness.commands (stdlib only; imports nothing from the benchmark)."""

import os
import sys


def _read_config(fd):
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    os.close(fd)
    import json

    return json.loads(b"".join(chunks).decode("utf-8"))


def _main():
    cfg = _read_config(int(sys.argv[1]))
    import builtins
    import resource
    import runpy
    import sysconfig
    import traceback
    import types

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    fsize = int(cfg["fsize"])
    _soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    if hard != resource.RLIM_INFINITY:
        fsize = min(fsize, hard)
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))

    paths = sysconfig.get_paths()
    read_roots = [cfg["workspace"], "/usr/share/zoneinfo"]
    read_roots += [paths[k] for k in ("stdlib", "platstdlib", "purelib", "platlib") if paths.get(k)]
    read_roots += list(cfg["extra_read_roots"])
    write_roots = [cfg["workspace"], cfg["tmp"], cfg["home"]]

    vfd = int(cfg["violations_fd"])
    try:
        vst = os.fstat(vfd)
        vid = (vst.st_dev, vst.st_ino)
    except OSError:
        vid = None

    def report(msg):
        # Write only while vfd is still the pipe we inherited (code under test may close and reuse the number).
        if vid is None:
            return
        try:
            st = os.fstat(vfd)
            if (st.st_dev, st.st_ino) != vid:
                return
            os.write(vfd, (msg.replace("\n", " ")[:500] + "\n").encode("utf-8", "replace"))
        except OSError:
            pass

    import linecache

    boot_file = os.path.realpath(__file__)
    boot_dir = os.path.dirname(boot_file)
    import _tab_tripwire

    tripwire_file = os.path.realpath(_tab_tripwire.__file__)
    hidden_files = {boot_file, tripwire_file, os.path.realpath(runpy.__file__), "<frozen runpy>"}
    # Cache the harness's own sources now: formatting a traceback through them
    # later must not read boot/, which is outside the allowlist.
    for name in (boot_file, tripwire_file):
        linecache.getlines(name)
    _tab_tripwire.install(read_roots, write_roots, report=report)
    del sys.modules["_tab_tripwire"]

    real_roots = [os.path.realpath(r) for r in read_roots + write_roots]

    def allowed(entry):
        if not entry:
            return False
        p = os.path.realpath(entry)
        return any(p == r or p.startswith(r.rstrip(os.sep) + os.sep) for r in real_roots)

    workspace = cfg["workspace"]
    rest = [p for p in sys.path[1:] if p != boot_dir and allowed(p)]
    sys.path[:] = [workspace] + [p for p in rest if p != workspace]
    sys.path_importer_cache.clear()
    kind, target = cfg["kind"], cfg["target"]
    sys.argv = list(cfg["argv"])
    sys.orig_argv = list(cfg["orig_argv"])
    del cfg, paths, read_roots, write_roots, real_roots

    try:
        if kind == "module":
            runpy.run_module(target, run_name="__main__", alter_sys=True)
        elif kind == "script":
            # Relative, as `python PATH.py` would leave sys.argv[0] (run_path sets argv[0] to this).
            runpy.run_path(target, run_name="__main__")
        else:
            main = types.ModuleType("__main__")
            main.__dict__["__builtins__"] = builtins
            sys.modules["__main__"] = main
            exec(compile(target, "<string>", "exec"), main.__dict__)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - mirror the interpreter: report and exit 1
        report_exc = traceback.TracebackException.from_exception(exc)
        seen = set()
        todo = [report_exc]
        while todo:  # drop bootstrap, runpy and tripwire frames, including in chained exceptions
            te = todo.pop()
            if id(te) in seen:
                continue
            seen.add(id(te))
            te.stack = traceback.StackSummary.from_list(
                [f for f in te.stack if f.filename not in hidden_files and os.path.realpath(f.filename) not in hidden_files]
            )
            todo += [t for t in (te.__cause__, te.__context__) if t is not None]
        sys.stderr.write("".join(report_exc.format()))
        sys.stderr.flush()
        raise SystemExit(1) from None


_main()
'''


def _wipe_dir(path: Path) -> None:
    """Remove ``path`` (whatever the child left there) and recreate it as an empty directory."""
    if os.path.islink(path) or (os.path.lexists(path) and not os.path.isdir(path)):
        os.unlink(path)
    elif os.path.isdir(path):
        # The child may have removed permissions on directories it created; restore them first
        # (top-down, never following symlinks) so that the removal cannot fail half-way.
        stack = [str(path)]
        while stack:
            current = stack.pop()
            try:
                os.chmod(current, 0o700)
                entries = list(os.scandir(current))
            except OSError:
                continue
            stack.extend(e.path for e in entries if e.is_dir(follow_symlinks=False))
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)
    os.chmod(path, 0o700)


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


# ------------------------------------------------------------------- runner
class CommandRunner:
    """Runs contestant commands in one workspace (implements ``tools.CommandService``)."""

    def __init__(
        self,
        workspace_root: Path,
        scratch_dir: Path,
        *,
        python: str = sys.executable,
        max_output_chars: int = 20_000,
        extra_read_roots: Sequence[Path] = (),
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self._ws_real = Path(os.path.realpath(self.workspace_root))
        if not self._ws_real.is_dir():
            raise ValueError("workspace root must be an existing directory")
        self.scratch_dir = Path(scratch_dir)
        self._scratch_real = Path(os.path.realpath(self.scratch_dir))
        if _is_within(self._scratch_real, self._ws_real) or _is_within(self._ws_real, self._scratch_real):
            raise ValueError("scratch directory and workspace must not contain each other")
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        if not python:
            raise ValueError("python interpreter must be given")
        if max_output_chars < 100:
            raise ValueError("max_output_chars must be at least 100")
        self.python = python
        self.max_output_chars = int(max_output_chars)
        self.extra_read_roots = tuple(os.path.realpath(p) for p in extra_read_roots)
        self.boot_dir = self._scratch_real / "boot"
        self.home_dir = self._scratch_real / "home"
        self.tmp_dir = self._scratch_real / "tmp"
        for d in (self.boot_dir, self.home_dir, self.tmp_dir):
            d.mkdir(parents=True, exist_ok=True)
        # The copy is the module verbatim plus a pytest hint (appended, so line numbers are unchanged)
        # that keeps tripwire frames out of test failure reports.
        self._tripwire_source = (
            Path(_tripwire_module.__file__).read_bytes()
            + b"\n__tracebackhide__ = True  # appended by harness.commands for pytest reports\n"
        )

    # ------------------------------------------------------------- helpers
    def _write_boot(self) -> Path:
        """(Re)write the bootstrap and its tripwire copy; the child cannot modify them (boot/ is not writable)."""
        boot = self.boot_dir / BOOT_NAME
        for name, data in ((BOOT_NAME, _BOOT_SOURCE.encode("utf-8")), (_TRIPWIRE_COPY, self._tripwire_source)):
            target = self.boot_dir / name
            tmp = self.boot_dir / f".{name}.tmp"
            if os.path.lexists(tmp):
                os.unlink(tmp)
            tmp.write_bytes(data)
            os.chmod(tmp, 0o444)
            os.replace(tmp, target)
        return boot

    def _environment(self) -> dict[str, str]:
        return {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home_dir),
            "TMPDIR": str(self.tmp_dir),
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "NO_COLOR": "1",
        }

    def _replacements(self) -> list[tuple[str, str]]:
        pairs = []
        for p in {str(self.workspace_root.absolute()), str(self._ws_real)}:
            pairs.append((p, "."))
        # pytest prints a path relative to the workspace when that is shorter, e.g. "../scratch/...".
        scratch_forms = {str(self.scratch_dir.absolute()), str(self._scratch_real)}
        scratch_forms.add(os.path.relpath(self._scratch_real, self._ws_real))
        for p in scratch_forms:
            pairs.append((p, "<tmp>"))
            pairs.append((os.path.join(p, "tmp"), "<tmp>"))
        return pairs

    # ----------------------------------------------------------------- run
    def run(self, command: str, timeout_s: float) -> dict[str, Any]:
        """Run ``command`` with a wall-clock limit of ``timeout_s`` seconds; see the module docstring."""
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not timeout_s > 0:
            raise ToolError("run_command: timeout must be a positive number of seconds")
        plan = parse_command(command, self._ws_real)
        started = time.monotonic()
        try:
            exit_code, timed_out, capture, violations = self._execute(plan, float(timeout_s))
        finally:
            _wipe_dir(self.tmp_dir)
            _wipe_dir(self.home_dir)
        output, truncated = capture.finish()
        normalize = _Normalizer(self._replacements())
        shown = [normalize(v) for v in violations.lines]
        if violations.total > len(violations.lines):
            shown.append(f"... {violations.total - len(violations.lines)} further violations not shown")
        return {
            "argv": list(plan.logical_argv),
            "exit_code": None if timed_out else exit_code,
            "output": output,
            "truncated": truncated,
            "timed_out": timed_out,
            "violations": shown,
            "wall_clock_ms": round((time.monotonic() - started) * 1000.0, 3),
        }

    def _execute(self, plan: CommandPlan, timeout_s: float) -> tuple[int | None, bool, _OutputStream, _Violations]:
        _wipe_dir(self.tmp_dir)
        _wipe_dir(self.home_dir)
        boot = self._write_boot()
        cfg_r, cfg_w = os.pipe()
        viol_r, viol_w = os.pipe()
        config = {
            "workspace": str(self._ws_real),
            "tmp": str(self.tmp_dir),
            "home": str(self.home_dir),
            "extra_read_roots": list(self.extra_read_roots),
            "violations_fd": viol_w,
            "fsize": FSIZE_LIMIT_BYTES,
            "kind": plan.kind,
            "target": plan.target,
            "argv": list(plan.argv),
            "orig_argv": list(plan.logical_argv),
        }
        payload = json.dumps(config, ensure_ascii=True, sort_keys=True).encode("ascii")
        try:
            proc = subprocess.Popen(
                [self.python, "-s", "-B", str(boot), str(cfg_r)],
                cwd=str(self._ws_real),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=self._environment(),
                start_new_session=True,
                pass_fds=(cfg_r, viol_w),
                close_fds=True,
            )
        except BaseException:
            for fd in (cfg_r, cfg_w, viol_r, viol_w):
                os.close(fd)
            raise
        os.close(cfg_r)
        os.close(viol_w)
        stream = _OutputStream(_Normalizer(self._replacements()), self.max_output_chars)
        session = _Session(proc, cfg_w, viol_r, payload, stream)
        try:
            timed_out = session.supervise(timeout_s)
        finally:
            _kill_group(proc.pid)  # reap stragglers even after a normal exit
            session.close()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        return proc.returncode, timed_out, session.capture, session.violations


@dataclass
class _Violations:
    """Tripwire refusals reported by the child: the first ``MAX_VIOLATIONS`` lines and a total count."""

    lines: list[str]
    total: int = 0

    def add(self, line: str) -> None:
        self.total += 1
        if len(self.lines) < MAX_VIOLATIONS:
            self.lines.append(line[:_MAX_VIOLATION_CHARS])


class _Session:
    """One running command: feeds its config, collects output and violations, enforces the deadline."""

    def __init__(self, proc: subprocess.Popen, cfg_w: int, viol_r: int, payload: bytes, capture: _OutputStream) -> None:
        self.proc = proc
        self.capture = capture
        self.violations = _Violations([])
        self._fds: dict[str, int | None] = {"cfg": cfg_w, "viol": viol_r}
        self._pending = memoryview(payload)
        self._viol_buf = bytearray()

    def _close_fd(self, tag: str) -> None:
        fd = self._fds.get(tag)
        if fd is not None:
            self._fds[tag] = None
            os.close(fd)

    def close(self) -> None:
        for tag in ("cfg", "viol"):
            self._close_fd(tag)
        if self.proc.stdout is not None:
            self.proc.stdout.close()

    def supervise(self, timeout_s: float) -> bool:
        """Run until the command exits (or times out) and its pipes drain. Returns ``timed_out``.

        The leader's exit is observed through a pidfd, which does not reap it,
        so the group is killed while its id cannot have been reused.
        """
        proc = self.proc
        assert proc.stdout is not None
        out_fd = proc.stdout.fileno()
        cfg_w, viol_r = self._fds["cfg"], self._fds["viol"]
        assert cfg_w is not None and viol_r is not None
        pidfd: int | None
        try:
            pidfd = os.pidfd_open(proc.pid)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pidfd = None
        for fd in (out_fd, viol_r, cfg_w):
            os.set_blocking(fd, False)
        sel = selectors.DefaultSelector()
        sel.register(out_fd, selectors.EVENT_READ, "out")
        sel.register(viol_r, selectors.EVENT_READ, "viol")
        sel.register(cfg_w, selectors.EVENT_WRITE, "cfg")
        if pidfd is not None:
            sel.register(pidfd, selectors.EVENT_READ, "pid")
        readers = {"out", "viol"}
        deadline = time.monotonic() + timeout_s
        exited = False
        timed_out = False
        drain_until: float | None = None
        try:
            while True:
                now = time.monotonic()
                if drain_until is None:
                    if exited:
                        _kill_group(proc.pid)
                        drain_until = now + _DRAIN_S
                    elif now >= deadline:
                        timed_out = True
                        _kill_group(proc.pid)
                        drain_until = now + _DRAIN_S
                if drain_until is not None and (not readers or now >= drain_until):
                    break
                wait = (drain_until if drain_until is not None else deadline) - now
                if pidfd is None and not exited:
                    wait = min(wait, _POLL_S)
                for key, _mask in sel.select(max(0.0, wait)):
                    tag = key.data
                    if tag == "pid":
                        exited = True
                        sel.unregister(key.fd)
                    elif tag == "cfg":
                        self._feed_config(sel)
                    else:
                        try:
                            data = os.read(key.fd, _READ_CHUNK)
                        except BlockingIOError:
                            continue
                        if not data:
                            sel.unregister(key.fd)
                            readers.discard(tag)
                        elif tag == "out":
                            self.capture.feed(data)
                        else:
                            self._viol_buf += data
                            self._take_violations()
                if pidfd is None and not exited and proc.poll() is not None:
                    exited = True
        finally:
            sel.close()
            if pidfd is not None:
                os.close(pidfd)
        if self._viol_buf:
            self._viol_buf += b"\n"
            self._take_violations()
        return timed_out

    def _feed_config(self, sel: selectors.BaseSelector) -> None:
        fd = self._fds["cfg"]
        assert fd is not None
        try:
            n = os.write(fd, self._pending)
            self._pending = self._pending[n:]
        except BlockingIOError:
            return
        except OSError:  # the child is gone (EPIPE): nothing more to send
            self._pending = self._pending[:0]
        if not self._pending:
            sel.unregister(fd)
            self._close_fd("cfg")

    def _take_violations(self) -> None:
        buf = self._viol_buf
        while True:
            nl = buf.find(b"\n")
            if nl < 0:
                if len(buf) > 4 * _MAX_VIOLATION_CHARS:  # an unterminated flood: drop it
                    del buf[:]
                return
            line = bytes(buf[:nl]).decode("utf-8", errors="replace").strip()
            del buf[: nl + 1]
            if line:
                self.violations.add(line)
