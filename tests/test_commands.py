"""Controlled command execution (``harness.commands``, amendment A2): grammar, isolation, determinism."""

from __future__ import annotations

import json
import os
import resource
import sys
import textwrap
import time
from pathlib import Path

import pytest

from harness.canonical import copy_tree, strip_volatile
from harness.commands import (
    BOOT_NAME,
    FSIZE_LIMIT_BYTES,
    CommandRunner,
    normalize_output,
    parse_command,
    truncate_output,
)
from harness.errors import AccessDenied, ToolError

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_REPO = REPO_ROOT / "world" / "seed_repo"
SMOKE_GT = REPO_ROOT / "world" / "ground_truth" / "smoke_v1"
EXPECTED_ENV = {
    "PATH": "/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "TZ": "UTC",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "NO_COLOR": "1",
    "HOME": "<tmp>/home",
    "TMPDIR": "<tmp>",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


def _make_workspace(root: Path) -> Path:
    ws = root / "ws"
    _write(ws / "pyproject.toml", '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n')
    _write(ws / "app.py", "def add(a, b):\n    return a + b\n")
    _write(ws / "tests" / "test_app.py", "import app\n\ndef test_add():\n    assert app.add(1, 2) == 3\n")
    _write(
        ws / "tools" / "show_argv.py",
        "import json, sys\nprint(json.dumps({'argv': sys.argv, 'name': __name__}))\nsys.exit(3)\n",
    )
    _write(ws / "pkg" / "__init__.py", "")
    _write(ws / "pkg" / "mod.py", "import sys\nprint('pkg.mod', sys.argv[1:])\n")
    return ws


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    return _make_workspace(tmp_path)


@pytest.fixture
def runner(ws: Path, tmp_path: Path) -> CommandRunner:
    return CommandRunner(ws, tmp_path / "scratch")


def _py(code: str, *args: str) -> str:
    """A ``python -c`` command line with ``code`` safely quoted."""
    import shlex

    return " ".join(["python", "-c", shlex.quote(textwrap.dedent(code)), *map(shlex.quote, args)])


# ---------------------------------------------------------------- grammar
ACCEPTED = [
    ("pytest", "module", "pytest", ("pytest", "-p", "no:cacheprovider"), ("pytest",)),
    ("pytest -q", "module", "pytest", ("pytest", "-p", "no:cacheprovider", "-q"), ("pytest", "-q")),
    ("python -m pytest -q -x", "module", "pytest", ("pytest", "-p", "no:cacheprovider", "-q", "-x"), ("pytest", "-q", "-x")),
    ("python3 -m pytest -q", "module", "pytest", ("pytest", "-p", "no:cacheprovider", "-q"), ("pytest", "-q")),
    ("python -mpytest", "module", "pytest", ("pytest", "-p", "no:cacheprovider"), ("pytest",)),
    ("python -m pkg.mod a b", "module", "pkg.mod", ("pkg.mod", "a", "b"), ("python", "-m", "pkg.mod", "a", "b")),
    ("python3 -m json.tool x.json", "module", "json.tool", ("json.tool", "x.json"), ("python", "-m", "json.tool", "x.json")),
    ("python -c 'print(1)' a", "code", "print(1)", ("-c", "a"), ("python", "-c", "print(1)", "a")),
    ("python -cpass", "code", "pass", ("-c",), ("python", "-c", "pass")),
    ("python tools/show_argv.py 1 2", "script", "tools/show_argv.py", ("tools/show_argv.py", "1", "2"),
     ("python", "tools/show_argv.py", "1", "2")),
    ("python ./tools//show_argv.py", "script", "tools/show_argv.py", ("tools/show_argv.py",),
     ("python", "tools/show_argv.py")),
    # Shell metacharacters are ordinary arguments: there is no shell.
    ("pytest -q | cat > out.txt", "module", "pytest", ("pytest", "-p", "no:cacheprovider", "-q", "|", "cat", ">", "out.txt"),
     ("pytest", "-q", "|", "cat", ">", "out.txt")),
    ("python -c 'print(1)' ; rm -rf / && echo $(id) `id`", "code", "print(1)",
     ("-c", ";", "rm", "-rf", "/", "&&", "echo", "$(id)", "`id`"),
     ("python", "-c", "print(1)", ";", "rm", "-rf", "/", "&&", "echo", "$(id)", "`id`")),
]


@pytest.mark.parametrize("command,kind,target,argv,logical", ACCEPTED)
def test_grammar_accepts(ws: Path, command, kind, target, argv, logical) -> None:
    plan = parse_command(command, ws)
    assert (plan.kind, plan.target, plan.argv, plan.logical_argv) == (kind, target, argv, logical)


REJECTED = [
    "",
    "   ",
    "ls -la",
    "echo hi",
    "bash -c 'pytest'",
    "sh -c pytest",
    "env pytest",
    "PYTHONPATH=/x pytest",
    "/usr/bin/python -c 1",
    "/usr/local/bin/pytest",
    "python3.11 -c 1",
    "py.test",
    "pip install requests",
    "git status",
    "python",
    "python3",
    "python -",
    "python -I -c 1",
    "python -E -c 1",
    "python -s -m pytest",
    "python -B tools/show_argv.py",
    "python -u -c 1",
    "python -O -c 1",
    "python -W error -c 1",
    "python -X dev -c 1",
    "python --version",
    "python -m",
    "python -c",
    "python -m 'os;rm'",
    "python -m ../app",
    "python -m .rel",
    "python -m a..b",
    "python -m 1abc",
    "python -m a-b",
    "python -m a/b",
    "python -m ''",
    "python app",
    "python app.txt",
    "python /etc/passwd.py",
    "python ../ws/app.py",
    "python tools/../../ws/app.py",
    "python ~/app.py",
    "python missing.py",
    "python tools",
    "python 'tools\\show_argv.py'",
    "python 'unterminated",
    'pytest "unterminated',
    "pytest -q\x00",
]


@pytest.mark.parametrize("command", REJECTED)
def test_grammar_rejects(ws: Path, command: str) -> None:
    with pytest.raises(ToolError):
        parse_command(command, ws)


def test_grammar_rejects_absolute_script_inside_workspace(ws: Path) -> None:
    with pytest.raises(AccessDenied):
        parse_command(f"python {ws / 'app.py'}", ws)


def test_grammar_rejects_non_string(ws: Path) -> None:
    for bad in (None, 1, ["pytest"], b"pytest"):
        with pytest.raises(ToolError):
            parse_command(bad, ws)


def test_grammar_rejects_symlinked_scripts(ws: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("print('outside')\n")
    os.symlink(outside, ws / "link.py")
    os.symlink(ws / "app.py", ws / "inner_link.py")  # even a link to a workspace file
    os.symlink(ws / "tools", ws / "linkdir")
    (ws / "dir.py").mkdir()
    os.mkfifo(ws / "fifo.py")
    for command in ("python link.py", "python inner_link.py", "python linkdir/show_argv.py", "python dir.py",
                    "python fifo.py"):
        with pytest.raises(ToolError):
            parse_command(command, ws)


def test_rejected_command_spawns_nothing(runner: CommandRunner, ws: Path) -> None:
    with pytest.raises(ToolError):
        runner.run("bash -c 'touch pwned'", 5)
    assert not (ws / "pwned").exists()


@pytest.mark.parametrize("timeout", [0, -1, True, "5", None, float("nan")])
def test_bad_timeout_rejected(runner: CommandRunner, timeout) -> None:
    with pytest.raises(ToolError):
        runner.run("python -c pass", timeout)


def test_scratch_and_workspace_must_be_disjoint(ws: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        CommandRunner(ws, ws / "scratch")
    assert not (ws / "scratch").exists()  # nothing was created inside the workspace
    with pytest.raises(ValueError):
        CommandRunner(ws, tmp_path)


# ----------------------------------------------------------- execution
def test_shell_metacharacters_are_plain_arguments(runner: CommandRunner, ws: Path) -> None:
    before = sorted(p.name for p in ws.iterdir())
    res = runner.run(
        "python -c 'import sys, json; print(json.dumps(sys.argv))' '|' cat '>' out.txt ';' touch pwned "
        "'$(touch pwned2)' '`touch pwned3`' '&&' rm -rf .",
        30,
    )
    assert res["exit_code"] == 0, res
    assert json.loads(res["output"]) == ["-c", "|", "cat", ">", "out.txt", ";", "touch", "pwned",
                                         "$(touch pwned2)", "`touch pwned3`", "&&", "rm", "-rf", "."]
    assert sorted(p.name for p in ws.iterdir()) == before


def test_seed_suite_passes_deterministically(tmp_path: Path) -> None:
    ws = tmp_path / "seed"
    copy_tree(SEED_REPO, ws)
    runner = CommandRunner(ws, tmp_path / "scratch")
    first = runner.run("pytest -q", 120)
    second = runner.run("pytest -q", 120)
    assert first["exit_code"] == 0, first["output"]
    assert first["timed_out"] is False and first["truncated"] is False
    assert first["violations"] == [], first["violations"]
    assert first["argv"] == ["pytest", "-q"]
    assert " passed in <t>s" in first["output"]
    assert strip_volatile(first) == strip_volatile(second)
    assert str(ws) not in first["output"] and str(tmp_path) not in first["output"]
    # Neither bytecode nor the pytest cache was written into the workspace.
    leftovers = [p for p in ws.rglob("*") if p.name in ("__pycache__", ".pytest_cache") or p.suffix == ".pyc"]
    assert leftovers == []
    # The other spellings of pytest run the same thing.
    for alias in ("python -m pytest -q", "python3 -m pytest -q"):
        res = runner.run(alias, 120)
        assert res["argv"] == ["pytest", "-q"]
        assert strip_volatile(res) == strip_volatile(first)


def test_failing_test_gives_nonzero_exit(runner: CommandRunner, ws: Path) -> None:
    _write(ws / "tests" / "test_broken.py", "def test_broken():\n    assert 1 == 2\n")
    res = runner.run("pytest -q", 60)
    assert res["exit_code"] == 1
    assert "1 failed, 1 passed in <t>s" in res["output"]
    assert "assert 1 == 2" in res["output"]
    res = runner.run("pytest -q tests/test_app.py", 60)
    assert res["exit_code"] == 0


def test_exit_codes_and_script_mode(runner: CommandRunner) -> None:
    res = runner.run("python tools/show_argv.py a 'b c'", 30)
    assert res["exit_code"] == 3
    assert json.loads(res["output"]) == {"argv": ["tools/show_argv.py", "a", "b c"], "name": "__main__"}
    assert res["argv"] == ["python", "tools/show_argv.py", "a", "b c"]
    res = runner.run("python -m pkg.mod x y", 30)
    assert res["exit_code"] == 0
    assert res["output"] == "pkg.mod ['x', 'y']\n"
    res = runner.run(_py("raise SystemExit(7)"), 30)
    assert res["exit_code"] == 7
    res = runner.run(_py("raise ValueError('boom')"), 30)
    assert res["exit_code"] == 1
    assert res["output"].endswith("ValueError: boom\n")
    assert BOOT_NAME not in res["output"] and "runpy" not in res["output"]
    res = runner.run("python -m no_such_module_xyz", 30)
    assert res["exit_code"] == 1 and "No module named no_such_module_xyz" in res["output"]


def test_timeout_kills_the_group(runner: CommandRunner) -> None:
    code = """
        import sys, threading, time
        print('before', flush=True)
        threading.Thread(target=time.sleep, args=(60,)).start()
        time.sleep(60)
    """
    started = time.monotonic()
    res = runner.run(_py(code), 2)
    elapsed = time.monotonic() - started
    assert res["timed_out"] is True
    assert res["exit_code"] is None
    assert elapsed < 10
    assert res["output"] == "before\n"
    res = runner.run("python -c 'import time; time.sleep(60)'", 2)
    assert res["timed_out"] is True and res["exit_code"] is None


def test_fast_command_is_not_timed_out(runner: CommandRunner) -> None:
    res = runner.run("python -c 'print(42)'", 30)
    assert res == {**res, "exit_code": 0, "timed_out": False, "truncated": False, "output": "42\n", "violations": []}
    assert isinstance(res["wall_clock_ms"], float)
    assert set(res) == {"argv", "exit_code", "output", "truncated", "timed_out", "violations", "wall_clock_ms"}


def test_signal_exit_is_reported(runner: CommandRunner) -> None:
    res = runner.run(_py("import os, signal; os.kill(os.getpid(), signal.SIGKILL)"), 30)
    assert res["timed_out"] is False
    assert res["exit_code"] == -9


# ------------------------------------------------------------- escapes
def _canary() -> str:
    return (SMOKE_GT / "CANARY").read_text().strip()


ESCAPES = {
    "read_ground_truth": f"open({str(SMOKE_GT / 'labels.json')!r}).read()",
    "read_ground_truth_bytes": f"import pathlib; pathlib.Path({str(SMOKE_GT / 'CANARY')!r}).read_bytes()",
    "os_open_ground_truth": f"import os; os.open({str(SMOKE_GT / 'CANARY')!r}, os.O_RDONLY)",
    "list_repo_root": f"import os; print(os.listdir({str(REPO_ROOT)!r}))",
    "scandir_repo_root": f"import os; print(list(os.scandir({str(REPO_ROOT)!r})))",
    "glob_repo": f"import glob; print(glob.glob({str(REPO_ROOT / 'world' / '*')!r}))",
    "walk_up": "import os; print(os.listdir('..'))",
    "chdir_out": "import os; os.chdir('/'); print(os.listdir('.'))",
    "read_etc_passwd": "open('/etc/passwd').read()",
    "read_proc_cmdline": "open('/proc/self/cmdline', 'rb').read()",
    "read_proc_environ": "open('/proc/self/environ', 'rb').read()",
    "read_parent_environ": "import os; open(f'/proc/{os.getppid()}/environ', 'rb').read()",
    "socket": "import socket; socket.socket()",
    "getaddrinfo": "import socket; socket.getaddrinfo('localhost', 80)",
    "urllib": "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9/')",
    "subprocess": "import subprocess; subprocess.run(['true'])",
    "os_system": "import os; os.system('true')",
    "fork": "import os; os.fork()",
    "posix_spawn": "import os; os.posix_spawn('/bin/true', ['true'], {})",
    "execv": "import os; os.execv('/bin/true', ['true'])",
    "fork_exec_direct": "import _posixsubprocess; _posixsubprocess.fork_exec()",
    "multiprocessing": "import multiprocessing as m; p = m.Process(target=print); p.start(); p.join()",
    "ctypes_import": "import ctypes",
    "ctypes_cdll": "import _ctypes; _ctypes.dlopen(None)",
    "kill_parent": "import os; os.kill(os.getppid(), 0)",
    "killpg_parent": "import os; os.killpg(os.getpgid(os.getppid()), 0)",
}


@pytest.mark.parametrize("name", sorted(ESCAPES))
def test_escape_attempts_fail(runner: CommandRunner, name: str) -> None:
    res = runner.run(_py(ESCAPES[name]), 30)
    assert res["exit_code"] not in (0, None), res
    assert res["violations"], res
    assert _canary() not in res["output"]
    assert "TripwireViolation" in res["output"] or "PermissionError" in res["output"], res["output"]
    assert str(REPO_ROOT) not in json.dumps(res["violations"])


def test_writes_outside_the_workspace_fail(runner: CommandRunner, ws: Path, tmp_path: Path) -> None:
    target = tmp_path / "outside.txt"
    attempts = [
        f"open({str(target)!r}, 'w').write('x')",
        f"import os; os.open({str(target)!r}, os.O_WRONLY | os.O_CREAT)",
        f"import os; os.mkdir({str(tmp_path / 'outdir')!r})",
        f"import os; os.rename('app.py', {str(target)!r})",
        f"import shutil; shutil.copyfile('app.py', {str(target)!r})",
        # Planting a symlink to an outside file would let a later reader follow it.
        "import os; os.symlink('/etc/passwd', 'passwd_link')",
        f"import os; os.link({str(SMOKE_GT / 'CANARY')!r}, 'canary_link')",
        # The bootstrap directory is not writable, so the next command's bootstrap cannot be tampered with.
        f"open({str(runner.boot_dir / BOOT_NAME)!r}, 'w').write('print(1)')",
    ]
    for code in attempts:
        res = runner.run(_py(code), 30)
        assert res["exit_code"] == 1 and res["violations"], (code, res)
    assert not target.exists() and not (tmp_path / "outdir").exists()
    assert (ws / "app.py").exists()
    assert not os.path.lexists(ws / "passwd_link") and not os.path.lexists(ws / "canary_link")
    assert runner.run("python -c 'print(5)'", 30)["output"] == "5\n"


def test_hidden_tests_are_unreachable_via_pytest(runner: CommandRunner) -> None:
    res = runner.run(f"pytest -q {SMOKE_GT / 'hidden_tests'}", 60)
    assert res["exit_code"] not in (0, None)
    assert res["violations"]
    assert _canary() not in res["output"]


def test_violation_reported_even_when_swallowed(runner: CommandRunner) -> None:
    code = f"""
        try:
            open({str(SMOKE_GT / 'labels.json')!r}).read()
        except PermissionError:
            print('caught')
    """
    res = runner.run(_py(code), 30)
    assert res["exit_code"] == 0
    assert res["output"] == "caught\n"
    assert res["violations"] == ["open: read outside the allowed directories"]


def test_violation_flood_is_capped(runner: CommandRunner) -> None:
    code = """
        for _ in range(500):
            try:
                open('/etc/hostname')
            except PermissionError:
                pass
    """
    res = runner.run(_py(code), 60)
    assert res["exit_code"] == 0
    assert len(res["violations"]) == 51
    assert res["violations"][-1] == "... 450 further violations not shown"


def test_closing_the_report_fd_is_harmless(runner: CommandRunner, ws: Path) -> None:
    code = """
        import os
        fd = os.open('reused.txt', os.O_WRONLY | os.O_CREAT)
        for n in range(3, 256):  # put the file behind every fd number, including the report pipe's
            if n != fd:
                try:
                    os.dup2(fd, n)
                except OSError:
                    pass
        try:
            open('/etc/passwd')
        except PermissionError:
            pass
        print(repr(open('reused.txt').read()))
    """
    res = runner.run(_py(code), 30)
    assert res["exit_code"] == 0, res
    assert res["output"] == "''\n"


def test_allowed_operations_work(runner: CommandRunner, ws: Path) -> None:
    code = """
        import json, os, sqlite3, tempfile, zoneinfo
        tz = zoneinfo.ZoneInfo('Europe/Paris')
        with open('notes.txt', 'w') as fh:
            fh.write('in workspace')
        os.makedirs('out/deep', exist_ok=True)
        with tempfile.NamedTemporaryFile('w', delete=False) as fh:
            fh.write('scratch')
        with open(os.path.join(os.environ['HOME'], 'h.txt'), 'w') as fh:
            fh.write('home')
        db = sqlite3.connect('state.db'); db.execute('create table t (x)'); db.close()
        mem = sqlite3.connect(':memory:'); mem.close()
        print(tz.key, open('app.py').read().count('def'), sorted(os.listdir('.'))[:3])
    """
    res = runner.run(_py(code), 30)
    assert res["exit_code"] == 0, res
    assert res["violations"] == []
    assert res["output"] == "Europe/Paris 1 ['app.py', 'notes.txt', 'out']\n"
    assert (ws / "notes.txt").read_text() == "in workspace"
    assert (ws / "state.db").exists()


def test_rlimits_are_set(runner: CommandRunner) -> None:
    res = runner.run(_py("import resource as r; print(r.getrlimit(r.RLIMIT_CORE), r.getrlimit(r.RLIMIT_FSIZE))"), 30)
    assert res["exit_code"] == 0
    hard = resource.getrlimit(resource.RLIMIT_FSIZE)[1]
    expected = FSIZE_LIMIT_BYTES if hard == resource.RLIM_INFINITY else min(FSIZE_LIMIT_BYTES, hard)
    assert res["output"] == f"(0, 0) ({expected}, {expected})\n"


# --------------------------------------------------- environment and paths
def test_environment_is_constructed_from_scratch(runner: CommandRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET-should-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-SECRET-2")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("https_proxy", "http://proxy.invalid:3128")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT / "src"))
    monkeypatch.setenv("PYTHONSTARTUP", str(REPO_ROOT / "evil.py"))
    res = runner.run(_py("import json, os; print(json.dumps(dict(os.environ), sort_keys=True))"), 30)
    assert res["exit_code"] == 0, res
    assert json.loads(res["output"]) == EXPECTED_ENV
    assert "SECRET" not in res["output"] and "proxy" not in res["output"]


def test_child_sees_no_host_paths_or_config(runner: CommandRunner, ws: Path) -> None:
    code = """
        import __main__, json, os, sys
        print(json.dumps({
            'argv': sys.argv, 'orig_argv': sys.orig_argv, 'env': dict(os.environ), 'path': sys.path,
            'cwd': os.getcwd(), 'main': sorted(k for k in vars(__main__) if not k.startswith('__')),
            'tripwire_module': [m for m in sys.modules if 'tripwire' in m],
            'importer_cache': sorted(k for k in sys.path_importer_cache if 'bo' + 'ot' in k),
        }))
    """
    res = runner.run(_py(code, "x"), 30)
    assert res["exit_code"] == 0, res
    info = json.loads(res["output"])
    assert info["argv"] == ["-c", "x"]
    assert info["orig_argv"] == ["python", "-c", textwrap.dedent(code), "x"]
    assert info["cwd"] == "."
    assert info["path"][0] == "."
    assert info["main"] == ["json", "os", "sys"]  # only what the code itself imported; no bootstrap state
    assert info["tripwire_module"] == [] and info["importer_cache"] == []
    raw = res["output"]
    for secret in (str(REPO_ROOT), BOOT_NAME, "boot", "cfg_fd", "violations_fd", str(ws)):
        assert secret not in raw, secret
    # PYTHONPATH-free and user-site-free: only the workspace, stdlib and site-packages remain.
    assert all(p == "." or p.startswith(sys.base_prefix) or p.startswith(sys.prefix) for p in info["path"])


def test_output_never_contains_the_workspace_path(ws: Path, tmp_path: Path) -> None:
    alias = tmp_path / "alias"
    os.symlink(ws, alias)  # the runner is given a symlinked path; both forms must be hidden
    runner = CommandRunner(alias, tmp_path / "scratch")
    code = """
        import os, sys
        print(os.getcwd()); print(os.path.realpath('app.py')); print(os.path.abspath('tests'))
        print(sys.path[0]); import app; print(app.__file__)
        print(os.environ['TMPDIR'], os.environ['HOME'])
    """
    res = runner.run(_py(code), 30)
    assert res["exit_code"] == 0, res
    assert res["output"].splitlines() == [".", "./app.py", "./tests", ".", "./app.py", "<tmp> <tmp>/home"]
    res = runner.run("pytest", 60)  # the verbose header prints rootdir
    assert "rootdir: ." in res["output"]
    for form in (str(ws), str(alias), os.path.realpath(ws), str(tmp_path)):
        assert form not in res["output"]
    _write(ws / "tests" / "test_esc.py", "import socket\n\ndef test_net():\n    socket.socket()\n")
    res = runner.run("pytest -q tests/test_esc.py", 60)
    assert res["exit_code"] == 1
    assert "scratch" not in res["output"] and str(tmp_path) not in res["output"]
    assert "_tab_tripwire.py" not in res["output"]  # tripwire frames are hidden from pytest reports


def test_stdin_is_empty(runner: CommandRunner) -> None:
    res = runner.run(_py("import sys; print(repr(sys.stdin.read()))"), 30)
    assert res["exit_code"] == 0
    assert res["output"] == "''\n"


def test_scratch_is_wiped_between_commands(runner: CommandRunner) -> None:
    code = """
        import os, tempfile
        open(os.path.join(tempfile.gettempdir(), 'leftover.txt'), 'w').write('x')
        open(os.path.join(os.environ['HOME'], '.history'), 'w').write('x')
        os.makedirs(os.path.join(tempfile.gettempdir(), 'locked', 'inner'))
        os.chmod(os.path.join(tempfile.gettempdir(), 'locked'), 0)
        print('written')
    """
    assert runner.run(_py(code), 30)["output"] == "written\n"
    assert list(runner.tmp_dir.iterdir()) == [] and list(runner.home_dir.iterdir()) == []
    res = runner.run(_py("import os, tempfile; print(os.listdir(tempfile.gettempdir()), os.listdir(os.environ['HOME']))"), 30)
    assert res["output"] == "[] []\n"


def test_scratch_wiped_after_timeout(runner: CommandRunner) -> None:
    code = "import tempfile, time; open(tempfile.gettempdir() + '/t', 'w').write('x'); time.sleep(60)"
    res = runner.run(_py(code), 2)
    assert res["timed_out"]
    assert list(runner.tmp_dir.iterdir()) == []


# ----------------------------------------------------------------- output
def test_large_output_is_truncated_head_and_tail(ws: Path, tmp_path: Path) -> None:
    runner = CommandRunner(ws, tmp_path / "scratch", max_output_chars=1000)
    res = runner.run(_py("print('HEAD'); print('x' * 50000); print('TAIL')"), 30)
    assert res["exit_code"] == 0
    assert res["truncated"] is True
    out = res["output"]
    assert out.startswith("HEAD\n") and out.endswith("TAIL\n")
    assert "[... output truncated:" in out
    head, _, tail = out.partition("\n[... output truncated:")
    assert len(tail) > len(head)
    assert len(out) < 1100


def test_output_flood_is_bounded(ws: Path, tmp_path: Path) -> None:
    runner = CommandRunner(ws, tmp_path / "scratch", max_output_chars=1000)
    res = runner.run(_py("import sys; sys.stdout.write('HEAD' + 'y' * 30_000_000 + 'TAIL\\n')"), 60)
    assert res["exit_code"] == 0
    assert res["truncated"] is True
    assert res["output"].startswith("HEAD") and res["output"].endswith("TAIL\n")
    assert "further bytes omitted" in res["output"]
    assert len(res["output"]) < 1200


def test_small_output_not_truncated(ws: Path, tmp_path: Path) -> None:
    runner = CommandRunner(ws, tmp_path / "scratch", max_output_chars=1000)
    res = runner.run(_py("print('z' * 990)"), 30)
    assert res["truncated"] is False and res["output"] == "z" * 990 + "\n"


def test_invalid_utf8_is_replaced(runner: CommandRunner) -> None:
    res = runner.run(_py("import sys; sys.stdout.buffer.write(b'ok \\xff\\xfe end\\n')"), 30)
    assert res["exit_code"] == 0
    assert res["output"] == "ok �� end\n"


def test_normalize_output_rules() -> None:
    reps = [("/data/run/ws", "."), ("/data/run/scratch", "<tmp>"), ("/data/run/scratch/tmp", "<tmp>")]
    text = (
        "/data/run/ws/app.py /data/run/ws2/x /data/run/ws-old /data/run/scratch/tmp/f /data/run/scratch/boot "
        "/x/data/run/ws 3 passed in 0.12s; 1 failed in 61.03s (0:01:01); in 2s"
    )
    assert normalize_output(text, reps) == (
        "./app.py /data/run/ws2/x /data/run/ws-old <tmp>/f <tmp>/boot "
        "/x/data/run/ws 3 passed in <t>s; 1 failed in <t>s; in <t>s"
    )


def test_truncate_output_rules() -> None:
    assert truncate_output("abc", 10) == ("abc", False)
    text = "".join(str(i % 10) for i in range(1000))
    out, truncated = truncate_output(text, 100)
    assert truncated
    head, marker, tail = out.split("\n")
    assert head == text[:25] and tail == text[-75:]
    assert marker == "[... output truncated: 900 characters omitted ...]"


def test_results_are_deterministic(runner: CommandRunner) -> None:
    cmd = _py("import os, tempfile; print(sorted(os.listdir('.')), tempfile.gettempdir(), hash('abc'))")
    a, b = runner.run(cmd, 30), runner.run(cmd, 30)
    assert strip_volatile(a) == strip_volatile(b)
    assert "<tmp>" in a["output"]


def test_repository_code_is_not_importable(runner: CommandRunner) -> None:
    res = runner.run(_py("import harness.scenario"), 30)
    assert res["exit_code"] == 1
    assert "ModuleNotFoundError: No module named 'harness'" in res["output"]


def test_workspace_cannot_shadow_the_bootstrap(runner: CommandRunner, ws: Path) -> None:
    # Modules the bootstrap uses, and the tripwire copy's name, are imported before the workspace is on sys.path.
    for name in ("runpy", "traceback", "linecache", "_tab_tripwire", "sitecustomize", "usercustomize"):
        _write(ws / f"{name}.py", "raise SystemExit('shadowed ' + __name__)\n")
    res = runner.run(_py("import socket; socket.socket()"), 30)
    assert res["exit_code"] == 1 and res["violations"] == ["socket.__new__: network access"]
    assert "shadowed" not in res["output"]


def test_without_pidfd_support(runner: CommandRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(os, "pidfd_open", raising=False)
    res = runner.run("python -c 'print(1)'", 30)
    assert (res["exit_code"], res["output"], res["timed_out"]) == (0, "1\n", False)
    res = runner.run("python -c 'import time; time.sleep(60)'", 2)
    assert res["timed_out"] is True and res["exit_code"] is None
