"""Path confinement of the contestant tool surface."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness.agent import StepBudget
from harness.tools import BudgetExceeded, ToolBox
from harness.workspace import AccessDenied, ToolError, Workspace, validate_relpath


@pytest.fixture
def layout(tmp_path: Path):
    ws_root = tmp_path / "ws"
    secret = tmp_path / "secret"
    ws_root.mkdir()
    secret.mkdir()
    (secret / "labels.json").write_text("SECRET-LABEL")
    (ws_root / "a.txt").write_text("hello\n")
    (ws_root / "pkg").mkdir()
    (ws_root / "pkg" / "mod.py").write_text("x = 1\n")
    return ws_root, secret


ESCAPES = [
    "../secret/labels.json",
    "pkg/../../secret/labels.json",
    "./../secret/labels.json",
    "/etc/passwd",
    "~/labels.json",
    "~root/x",
    "pkg\\..\\..\\secret\\labels.json",
    "a.txt\x00",
    "",
    "C:/Windows/win.ini",
]


@pytest.mark.parametrize("path", ESCAPES)
def test_escape_paths_are_denied(layout, path):
    ws_root, secret = layout
    ws = Workspace(ws_root, protected=[secret])
    with pytest.raises(AccessDenied):
        ws.read_text(path)
    with pytest.raises(AccessDenied):
        ws.write_text(path, "x")


def test_absolute_path_to_secret_is_denied(layout):
    ws_root, secret = layout
    ws = Workspace(ws_root, protected=[secret])
    with pytest.raises(AccessDenied):
        ws.read_text(str(secret / "labels.json"))


def test_symlink_inside_workspace_cannot_reach_outside(layout):
    ws_root, secret = layout
    os.symlink(secret, ws_root / "link_dir")
    os.symlink(secret / "labels.json", ws_root / "link_file")
    ws = Workspace(ws_root, protected=[secret])
    for p in ("link_dir/labels.json", "link_file"):
        with pytest.raises(AccessDenied):
            ws.read_text(p)
        with pytest.raises(AccessDenied):
            ws.write_text(p, "overwrite")
    assert (secret / "labels.json").read_text() == "SECRET-LABEL"
    # Listing and search never follow links out of the workspace.
    assert "link_dir/labels.json" not in ws.list_files()
    assert "link_file" not in ws.list_files()
    assert ws.search("SECRET")["matches"] == []


def test_symlink_to_inside_file_is_also_refused(layout):
    ws_root, _ = layout
    os.symlink(ws_root / "a.txt", ws_root / "alias.txt")
    ws = Workspace(ws_root)
    with pytest.raises(AccessDenied):
        ws.read_text("alias.txt")


def test_protected_dir_nested_inside_workspace_is_hidden(tmp_path):
    root = tmp_path / "ws"
    nested = root / "world" / "ground_truth"
    nested.mkdir(parents=True)
    (nested / "labels.json").write_text("SECRET")
    (root / "ok.txt").write_text("fine")
    ws = Workspace(root, protected=[nested])
    with pytest.raises(AccessDenied):
        ws.read_text("world/ground_truth/labels.json")
    with pytest.raises(AccessDenied):
        ws.list_files("world/ground_truth")
    assert ws.list_files() == ["ok.txt"]
    assert ws.search("SECRET")["matches"] == []


def test_workspace_inside_protected_root_is_rejected(tmp_path):
    protected = tmp_path / "gt"
    (protected / "ws").mkdir(parents=True)
    with pytest.raises(ValueError):
        Workspace(protected / "ws", protected=[protected])


def test_normal_operations(layout):
    ws_root, _ = layout
    ws = Workspace(ws_root)
    assert ws.read_text("./pkg/mod.py") == "x = 1\n"
    ws.write_text("new/dir/file.md", "content")
    assert ws.read_text("new/dir/file.md") == "content"
    assert ws.list_files() == ["a.txt", "new/dir/file.md", "pkg/mod.py"]
    assert ws.list_files("pkg") == ["pkg/mod.py"]
    assert ws.search(r"x = \d")["matches"] == [{"path": "pkg/mod.py", "line": 1, "text": "x = 1"}]
    ws.delete("a.txt")
    assert not ws.exists("a.txt")
    with pytest.raises(ToolError):
        ws.read_text("a.txt")
    with pytest.raises(ToolError):
        ws.delete("pkg")
    with pytest.raises(ToolError):
        ws.search("(unclosed")


def test_list_files_skips_caches(layout):
    ws_root, _ = layout
    (ws_root / "pkg" / "__pycache__").mkdir()
    (ws_root / "pkg" / "__pycache__" / "mod.cpython-311.pyc").write_bytes(b"\0")
    assert Workspace(ws_root).list_files() == ["a.txt", "pkg/mod.py"]


def test_validate_relpath_normalizes():
    assert validate_relpath("a/./b//c") == ("a", "b", "c")
    assert validate_relpath(".", allow_root=True) == ()
    with pytest.raises(AccessDenied):
        validate_relpath(".")
    with pytest.raises(AccessDenied):
        validate_relpath(123)  # type: ignore[arg-type]


def test_toolbox_records_every_call_and_enforces_budget(layout):
    ws_root, secret = layout
    records = []
    tools = ToolBox(Workspace(ws_root, protected=[secret]), StepBudget(max_tool_calls_per_event=3), records.append)
    assert tools.read_file("a.txt") == "hello\n"
    with pytest.raises(AccessDenied):
        tools.read_file("../secret/labels.json")
    tools.write_file("b.txt", "B")
    with pytest.raises(BudgetExceeded):
        tools.list_files()
    assert [r["status"] for r in records] == ["ok", "denied", "ok", "budget_exceeded"]
    assert records[2]["args"] == {"path": "b.txt", "content": "B"}
    assert all("SECRET" not in str(r) for r in records)
    assert tools.calls_made == 3 and tools.calls_remaining == 0


def test_toolbox_records_unserializable_args_by_type(layout):
    ws_root, _ = layout
    records = []
    tools = ToolBox(Workspace(ws_root), StepBudget(), records.append)
    with pytest.raises(ToolError):
        tools.write_file("x.txt", b"bytes")  # type: ignore[arg-type]
    assert records[0]["args"]["content"] == {"unrecordable_type": "bytes"}


def test_directory_symlink_to_unprotected_location_is_invisible(tmp_path):
    root, elsewhere = tmp_path / "ws", tmp_path / "other_lane"
    root.mkdir()
    elsewhere.mkdir()
    (elsewhere / "memory.txt").write_text("another agent's notes")
    (root / "a.txt").write_text("mine")
    os.symlink(elsewhere, root / "peek")
    ws = Workspace(root)  # no protected roots at all
    assert ws.list_files() == ["a.txt"]
    assert ws.search("notes")["matches"] == []
    with pytest.raises(AccessDenied):
        ws.read_text("peek/memory.txt")
