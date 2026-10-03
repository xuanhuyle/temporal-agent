"""Deterministic hashing and serialization primitives."""

from __future__ import annotations

import os

from harness.canonical import canonical_json, copy_tree, strip_volatile, tree_hash


def test_canonical_json_is_order_independent():
    assert canonical_json({"b": 1, "a": [1, {"d": 2, "c": 3}]}) == canonical_json({"a": [1, {"c": 3, "d": 2}], "b": 1})


def test_strip_volatile_is_recursive():
    obj = {"a": 1, "wall_clock_ms": 3, "nested": [{"started_at": "x", "keep": 2}], "traceback": "t"}
    assert strip_volatile(obj) == {"a": 1, "nested": [{"keep": 2}]}
    assert strip_volatile({"state_tree": 1, "k": 2}, ["state_tree"]) == {"k": 2}


def test_tree_hash_ignores_runtime_byproducts_and_tracks_content(tmp_path):
    root = tmp_path / "t"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "m.py").write_text("x = 1\n")
    h1 = tree_hash(root)
    (root / "pkg" / "__pycache__").mkdir()
    (root / "pkg" / "__pycache__" / "m.cpython-311.pyc").write_bytes(b"junk")
    (root / ".pytest_cache").mkdir()
    assert tree_hash(root) == h1
    (root / "pkg" / "m.py").write_text("x = 2\n")
    assert tree_hash(root) != h1


def test_tree_hash_depends_on_paths_not_mtimes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        d.mkdir()
        (d / "f").write_text("same")
    os.utime(b / "f", (0, 0))
    assert tree_hash(a) == tree_hash(b)
    (b / "f").rename(b / "g")
    assert tree_hash(a) != tree_hash(b)


def test_symlinks_hash_by_target_and_copy_as_links(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "real").write_text("data")
    os.symlink("/nonexistent/target", src / "link")
    dst = tmp_path / "dst"
    copy_tree(src, dst)
    assert (dst / "link").is_symlink()
    assert tree_hash(src) == tree_hash(dst)
