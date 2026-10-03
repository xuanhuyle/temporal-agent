"""``harness.tripwire`` tested directly, installed in a fresh child interpreter.

The tripwire is permanent for the life of a process, so every case runs in its
own ``python -s -B`` child (as the contestant worker and the command bootstrap
do): the child loads the module from its source file, installs it, runs a set
of probes and prints what was allowed, what was refused, and the record.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

TRIPWIRE_SRC = Path(__file__).resolve().parents[1] / "src" / "harness" / "tripwire.py"

_CHILD = r"""
import importlib.util, json, sys

cfg = json.loads(sys.argv[1])
spec = importlib.util.spec_from_file_location("tab_tripwire_under_test", cfg["tripwire"])
tw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tw)
reports = []
tw.install(cfg["read"], cfg["write"], report=reports.append, **cfg["flags"])
tw.install(["/"], ["/"], allow_network=True, allow_processes=True, allow_ctypes=True)  # ignored: first call counts
results = {}
for name, code in cfg["probes"]:
    try:
        exec(code, {"__name__": "probe"})
        results[name] = "allowed"
    except tw.TripwireViolation:
        results[name] = "denied"
    except OSError as exc:
        results[name] = "oserror:" + type(exc).__name__
    except Exception as exc:  # noqa: BLE001
        results[name] = "error:%s:%s" % (type(exc).__name__, exc)
sys.stdout.write(json.dumps({"results": results, "violations": tw.violations(), "reports": reports,
                             "installed": tw.installed()}))
"""


def _stdlib_roots() -> list[str]:
    paths = sysconfig.get_paths()
    return [paths[k] for k in ("stdlib", "platstdlib", "purelib", "platlib") if paths.get(k)]


def _run(tmp_path: Path, probes: dict[str, str], *, flags: dict | None = None,
         extra_args: tuple[str, ...] = ("-B",)) -> dict:
    cfg = {
        "tripwire": str(TRIPWIRE_SRC),
        "read": _stdlib_roots() + [str(tmp_path / "r")],
        "write": [str(tmp_path / "w")],
        "flags": flags or {},
        "probes": list(probes.items()),
    }
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONHASHSEED": "0"}
    if "-B" in extra_args:
        env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-s", *extra_args, "-c", _CHILD, json.dumps(cfg)],
        cwd=str(tmp_path / "r"), env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.fixture
def area(tmp_path: Path) -> Path:
    (tmp_path / "r" / "lib").mkdir(parents=True)
    (tmp_path / "r" / "data.txt").write_text("readable")
    (tmp_path / "r" / "lib" / "rolib.py").write_text("VALUE = 41\n")
    (tmp_path / "w").mkdir()
    (tmp_path / "w" / "wlib.py").write_text("VALUE = 42\n")
    (tmp_path / "outside" / "__pycache__").mkdir(parents=True)
    (tmp_path / "outside" / "secret.txt").write_text("secret")
    return tmp_path


def _p(path: Path) -> str:
    return repr(str(path))


# ------------------------------------------------------------- filesystem
def test_read_and_write_allowlists(area: Path) -> None:
    out, r, w = area / "outside", area / "r", area / "w"
    probes = {
        "read_read_root": f"open({_p(r / 'data.txt')}).read()",
        "read_write_root": f"open({_p(w / 'wlib.py')}).read()",
        "read_stdlib": "import json, os; open(json.__file__).read()",
        "read_outside": f"open({_p(out / 'secret.txt')}).read()",
        "read_outside_relative": "open('../outside/secret.txt').read()",
        "list_outside": f"import os; os.listdir({_p(out)})",
        "scandir_outside": f"import os; list(os.scandir({_p(out)}))",
        "glob_outside": f"import glob; glob.glob({_p(out / '*')})",
        "chdir_outside": f"import os; os.chdir({_p(out)})",
        "read_etc": "open('/etc/hostname').read()",
        "read_dev_null": "open('/dev/null').read()",
        "write_write_root": f"open({_p(w / 'new.txt')}, 'w').write('x')",
        "mkdir_write_root": f"import os; os.mkdir({_p(w / 'sub')})",
        "write_read_root": f"open({_p(r / 'data.txt')}, 'a').write('x')",
        "os_open_write_read_root": f"import os; os.open({_p(r / 'n.txt')}, os.O_WRONLY | os.O_CREAT)",
        "write_outside": f"open({_p(out / 'new.txt')}, 'w').write('x')",
        "write_dev_null": "open('/dev/null', 'w').write('x')",
        "rename_out": f"import os; os.rename({_p(w / 'new.txt')}, {_p(out / 'moved.txt')})",
        "symlink_out": f"import os; os.symlink({_p(out / 'secret.txt')}, {_p(out / 'link')})",
        "remove_outside": f"import os; os.remove({_p(out / 'secret.txt')})",
        "chmod_read_root": f"import os; os.chmod({_p(r / 'data.txt')}, 0o777)",
        "sqlite_memory": "import sqlite3; sqlite3.connect(':memory:').close()",
        "sqlite_write_root": f"import sqlite3; sqlite3.connect({_p(w / 'db.sqlite')}).close()",
        "sqlite_outside": f"import sqlite3; sqlite3.connect({_p(out / 'db.sqlite')})",
        "escape_by_dotdot": f"open({_p(w)} + '/../outside/new2.txt', 'w')",
    }
    res = _run(area, probes)
    denied = {k for k, v in res["results"].items() if v == "denied"}
    assert denied == {
        "read_outside", "read_outside_relative", "list_outside", "scandir_outside", "glob_outside",
        "chdir_outside", "read_etc", "write_read_root", "os_open_write_read_root", "write_outside",
        "rename_out", "symlink_out", "remove_outside", "chmod_read_root", "sqlite_outside", "escape_by_dotdot",
    }, res["results"]
    assert all(v == "allowed" for k, v in res["results"].items() if k not in denied), res["results"]
    assert res["installed"] is True
    assert (area / "outside" / "secret.txt").read_text() == "secret"
    assert sorted(p.name for p in (area / "outside").iterdir()) == ["__pycache__", "secret.txt"]
    assert (area / "r" / "data.txt").read_text() == "readable"
    assert (area / "w" / "new.txt").is_file() and (area / "w" / "db.sqlite").is_file()
    # Every refusal is recorded and reported, with the event name and no path.
    assert res["violations"] == res["reports"]
    assert len(res["violations"]) == len(denied)
    assert "open: write outside the allowed directories" in res["violations"]
    assert "open: read outside the allowed directories" in res["violations"]
    assert not any(str(area) in v for v in res["violations"])


# ---------------------------------------------------- no bytecode exemption
def test_bytecode_cache_paths_are_not_exempt(area: Path) -> None:
    out, r, w = area / "outside", area / "r", area / "w"
    probes = {
        "pyc_in_outside_pycache": f"open({_p(out / '__pycache__' / 'x.cpython-311.pyc')}, 'wb').write(b'x')",
        "tmp_in_outside_pycache": f"open({_p(out / '__pycache__' / 'x.cpython-311.pyc.1234')}, 'wb')",
        "bare_pyc_outside": f"open({_p(out / 'state.pyc')}, 'wb').write(b'x')",
        "pyc_tmp_outside": f"open({_p(out / 'state.pyc.tmp')}, 'wb').write(b'x')",
        "mkdir_pycache_outside": f"import os; os.mkdir({_p(out / 'sub__pycache__')}); os.mkdir({_p(out / 'x' / '__pycache__')})",
        "pycache_dir_name_outside": f"import os; os.makedirs({_p(out / 'pkg' / '__pycache__' / 'deep')})",
        "pyc_in_read_root": f"import os; os.mkdir({_p(r / 'lib' / '__pycache__')})",
        "pyc_beside_write_root": f"open({_p(w)} + '/../__pycache__/y.pyc', 'wb')",
        "rename_into_pycache": f"import os; os.rename({_p(w / 'wlib.py')}, {_p(out / '__pycache__' / 'z.pyc')})",
        "pyc_in_write_root": f"import os; os.makedirs({_p(w / '__pycache__')}); open({_p(w / '__pycache__' / 'ok.pyc')}, 'wb')",
    }
    res = _run(area, probes)
    assert {k: v for k, v in res["results"].items() if v != "denied"} == {"pyc_in_write_root": "allowed"}
    assert sorted(p.name for p in (area / "outside").iterdir()) == ["__pycache__", "secret.txt"]
    assert list((area / "outside" / "__pycache__").iterdir()) == []
    assert not (area / "r" / "lib" / "__pycache__").exists() and not (area / "__pycache__").exists()
    assert (area / "w" / "wlib.py").is_file()


def test_imports_work_and_write_no_bytecode_under_dash_b(area: Path) -> None:
    probes = {
        "import_stdlib": "import email.mime.text, decimal, zoneinfo",
        "import_read_root": "import sys; sys.path.insert(0, 'lib'); import rolib; assert rolib.VALUE == 41",
        "import_write_root": f"import sys; sys.path.insert(0, {_p(area / 'w')}); import wlib; assert wlib.VALUE == 42",
    }
    res = _run(area, probes)
    assert set(res["results"].values()) == {"allowed"}, res
    assert res["violations"] == []
    assert sorted(p.relative_to(area).as_posix() for p in area.rglob("*.pyc")) == []
    assert not (area / "r" / "lib" / "__pycache__").exists() and not (area / "w" / "__pycache__").exists()


def test_bytecode_writes_without_dash_b_are_refused_not_exempt(area: Path) -> None:
    """Even if a child forgot -B, the import system's cache writes outside the write roots are refused
    (and recorded); the import itself still succeeds because importlib ignores cache-write errors."""
    probes = {"import_read_root": "import sys; sys.path.insert(0, 'lib'); import rolib; assert rolib.VALUE == 41"}
    res = _run(area, probes, extra_args=())
    assert res["results"] == {"import_read_root": "allowed"}
    assert res["violations"] and all(v.endswith("write outside the allowed directories") for v in res["violations"])
    assert not (area / "r" / "lib" / "__pycache__").exists()


# ------------------------------------------------- network, processes, ...
REFUSALS = {
    "socket": ("import socket; socket.socket()", "socket.__new__: network access"),
    "getaddrinfo": ("import socket; socket.getaddrinfo('localhost', 80)", "socket.getaddrinfo: network access"),
    "gethostbyname": ("import socket; socket.gethostbyname('localhost')", "socket.gethostbyname: network access"),
    "subprocess": ("import subprocess; subprocess.run(['true'])", "subprocess.Popen: starting processes"),
    "os_system": ("import os; os.system('true')", "os.system: starting processes"),
    "fork": ("import os; os.fork()", "os.fork: starting processes"),
    "posix_spawn": ("import os; os.posix_spawn('/bin/true', ['true'], {})", "os.posix_spawn: starting processes"),
    "execv": ("import os; os.execv('/bin/true', ['true'])", "os.exec: starting processes"),
    "fork_exec": ("import _posixsubprocess; _posixsubprocess.fork_exec()", "_posixsubprocess.fork_exec: starting processes"),
    "ctypes_dlopen": ("import _ctypes; _ctypes.dlopen(None)", "ctypes.dlopen: ctypes"),
    "kill_parent": ("import os; os.kill(os.getppid(), 0)", "os.kill: signalling other processes"),
    "killpg": ("import os; os.killpg(os.getpgid(0), 0)", "os.killpg: signalling other processes"),
}


def test_network_process_ctypes_and_signal_refusals(area: Path) -> None:
    probes = {name: code for name, (code, _) in REFUSALS.items()}
    probes["kill_self"] = "import os; os.kill(os.getpid(), 0)"
    res = _run(area, probes)
    assert res["results"] == {**{name: "denied" for name in REFUSALS}, "kill_self": "allowed"}
    assert sorted(res["violations"]) == sorted(msg for _, msg in REFUSALS.values())


def test_allow_flags_lift_only_their_category(area: Path) -> None:
    probes = {
        "socket": "import socket; socket.socket().close()",
        "subprocess": "import subprocess; subprocess.run(['true'], check=True)",
        "write_outside": f"open({_p(area / 'outside' / 'n.txt')}, 'w')",
        "kill_parent": "import os; os.kill(os.getppid(), 0)",
    }
    res = _run(area, probes, flags={"allow_network": True, "allow_processes": True})
    assert res["results"] == {"socket": "allowed", "subprocess": "allowed", "write_outside": "denied",
                              "kill_parent": "denied"}


def test_tripwire_imports_only_the_standard_library() -> None:
    import ast

    tree = ast.parse(TRIPWIRE_SRC.read_text())
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert names <= {"__future__", "_posixsubprocess", "os", "sys", "typing"}, names
    assert os.path.isfile(TRIPWIRE_SRC)
