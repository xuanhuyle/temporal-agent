"""World history (``harness.history``, protocol amendment A1).

The central property is structural future-blindness: a state that has not
been revealed does not exist in the object, and every way of asking for it
fails with the same error wording.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from pathlib import Path

import pytest

from harness.agent import StepBudget
from harness.canonical import copy_tree, tree_hash
from harness.errors import AccessDenied, ToolError
from harness.history import HISTORY_ENTRY_KEYS, MAX_DIFF_CHARS, WorldHistory
from harness.scenario import load_scenario
from harness.tools import ToolBox
from harness.workspace import Workspace
from harness.world import apply_event

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_MANIFEST = REPO_ROOT / "scenarios" / "smoke" / "smoke_v1.json"

FUTURE_MARKER = b"FUTURE-STATE-MARKER-7c1d"

SEED = {
    "README.md": b"# Demo\n",
    "app/config.py": b"LIMIT = 1\n",
    "app/core.py": b"def f():\n    return 1\n",
    "docs/adr/0001-limit.md": b"# ADR-0001\n\nLimit is 1.\n",
}
EV1 = {**SEED, "app/config.py": b"LIMIT = 5\n", "NEW.md": b"new file\n"}
EV2 = {k: v for k, v in EV1.items() if k != "app/core.py"}
EV2["blob.bin"] = b"\xff\xfe\x00binary"


def _reveal_seed(h: WorldHistory, files: dict[str, bytes] | None = None) -> str:
    return h.reveal(0, SEED if files is None else files, event_id=None, timestamp=None, changed_paths=[])


def _three_states() -> WorldHistory:
    h = WorldHistory()
    _reveal_seed(h)
    h.reveal(1, EV1, event_id="evt-0001", timestamp="2026-01-02T09:00:00Z",
             changed_paths=[{"op": "write_file", "path": "app/config.py"}, {"op": "write_file", "path": "NEW.md"}])
    h.reveal(2, EV2, event_id="evt-0002", timestamp="2026-01-03T09:00:00Z",
             changed_paths=[{"op": "delete_file", "path": "app/core.py"}, {"op": "write_file", "path": "blob.bin"}])
    return h


def _unavailable(seq: int, latest: int) -> str:
    return f"no repository state at seq {seq}; available: 0..{latest}"


# ------------------------------------------------------------------ reveal
class TestReveal:
    def test_starts_empty(self):
        h = WorldHistory()
        assert h.revealed_seq == -1
        assert h.history() == []

    def test_accepts_only_next_seq(self):
        h = WorldHistory()
        for bad in (1, -1, 2, 10**9):
            with pytest.raises(ValueError, match="expected seq 0"):
                h.reveal(bad, SEED, event_id="evt-0001", timestamp="t", changed_paths=[])
        assert h.revealed_seq == -1
        _reveal_seed(h)
        assert h.revealed_seq == 0
        for bad in (0, 2, 3, -1):
            with pytest.raises(ValueError, match="expected seq 1"):
                h.reveal(bad, EV1, event_id="evt-0001", timestamp="t", changed_paths=[])
        assert h.revealed_seq == 0
        h.reveal(1, EV1, event_id="evt-0001", timestamp="t", changed_paths=[])
        assert h.revealed_seq == 1

    def test_rejects_bool_and_non_int_seq(self):
        h = WorldHistory()
        for bad in (False, True, 0.0, "0", None):
            with pytest.raises(ValueError, match="must be an integer"):
                h.reveal(bad, SEED, event_id=None, timestamp=None, changed_paths=[])  # type: ignore[arg-type]
        assert h.revealed_seq == -1

    def test_seed_state_has_no_event_metadata(self):
        h = WorldHistory()
        with pytest.raises(ValueError):
            h.reveal(0, SEED, event_id="evt-0001", timestamp=None, changed_paths=[])
        with pytest.raises(ValueError):
            h.reveal(0, SEED, event_id=None, timestamp="2026-01-01T00:00:00Z", changed_paths=[])
        with pytest.raises(ValueError):
            h.reveal(0, SEED, event_id=None, timestamp=None, changed_paths=[{"op": "write_file", "path": "x"}])
        assert h.revealed_seq == -1

    def test_event_states_need_event_metadata(self):
        h = WorldHistory()
        _reveal_seed(h)
        with pytest.raises(ValueError):
            h.reveal(1, EV1, event_id=None, timestamp="t", changed_paths=[])
        with pytest.raises(ValueError):
            h.reveal(1, EV1, event_id="evt-0001", timestamp=None, changed_paths=[])
        assert h.revealed_seq == 0

    @pytest.mark.parametrize(
        "files",
        [
            {"../escape.txt": b"x"},
            {"/abs.txt": b"x"},
            {"a/./b.txt": b"x"},
            {"a//b.txt": b"x"},
            {"a\\b.txt": b"x"},
            {"": b"x"},
            {"a.txt": "not bytes"},
            {"a": b"file", "a/b": b"under a file"},
        ],
    )
    def test_rejects_malformed_files_without_storing(self, files):
        h = WorldHistory()
        with pytest.raises(ValueError):
            h.reveal(0, files, event_id=None, timestamp=None, changed_paths=[])
        assert h.revealed_seq == -1
        assert h._blobs == {} and h._states == [] and h._entries == []

    @pytest.mark.parametrize("changed", ["write_file a", [("write_file", "a")], [{"op": "write_file"}], [{"op": 1, "path": "a"}]])
    def test_rejects_malformed_changed_paths(self, changed):
        h = WorldHistory()
        _reveal_seed(h)
        with pytest.raises(ValueError):
            h.reveal(1, EV1, event_id="evt-0001", timestamp="t", changed_paths=changed)
        assert h.revealed_seq == 0

    def test_drops_cache_by_products(self):
        h = WorldHistory()
        files = {**SEED, "app/__pycache__/core.cpython-311.pyc": b"\0junk", "app/stale.pyc": b"x", ".pytest_cache/v": b"y"}
        assert _reveal_seed(h, files) == _reveal_seed(WorldHistory())
        assert h.list_at(0) == sorted(SEED)

    def test_copies_its_input(self):
        content = bytearray(b"LIMIT = 1\n")
        files: dict[str, object] = {"app/config.py": content, "README.md": b"# Demo\n"}
        changed = [{"op": "write_file", "path": "app/config.py"}]
        h = WorldHistory()
        h.reveal(0, files, event_id=None, timestamp=None, changed_paths=[])  # type: ignore[arg-type]
        h.reveal(1, files, event_id="evt-0001", timestamp="t", changed_paths=changed)  # type: ignore[arg-type]
        before = h.history()
        content[:] = b"MUTATED\n"
        files["README.md"] = b"replaced\n"
        files["sneaky.txt"] = b"added later\n"
        changed[0]["path"] = "elsewhere"
        changed.append({"op": "delete_file", "path": "README.md"})
        assert h.read_at(0, "app/config.py") == "LIMIT = 1\n"
        assert h.read_at(1, "README.md") == "# Demo\n"
        assert h.list_at(1) == ["README.md", "app/config.py"]
        assert h.history() == before

    def test_changed_paths_keep_only_op_and_path_in_given_order(self):
        h = WorldHistory()
        _reveal_seed(h)
        given = [
            {"op": "write_file", "path": "z.md", "content_sha256": "abc", "subject": "SECRET PROSE"},
            {"op": "delete_file", "path": "a.md"},
        ]
        h.reveal(1, EV1, event_id="evt-0001", timestamp="t", changed_paths=given)
        assert h.history()[1]["changed_paths"] == [{"op": "write_file", "path": "z.md"}, {"op": "delete_file", "path": "a.md"}]


# ----------------------------------------------------------------- history
class TestHistoryEntries:
    def test_exact_keys_and_values(self):
        h = _three_states()
        entries = h.history()
        assert [e["seq"] for e in entries] == [0, 1, 2]
        for e in entries:
            assert tuple(sorted(e)) == tuple(sorted(HISTORY_ENTRY_KEYS))
            assert set(e) == {"seq", "event_id", "timestamp", "changed_paths", "tree_sha256"}
            assert re.fullmatch(r"[0-9a-f]{64}", e["tree_sha256"])
            for c in e["changed_paths"]:
                assert set(c) == {"op", "path"}
        assert entries[0] == {"seq": 0, "event_id": None, "timestamp": None, "changed_paths": [],
                              "tree_sha256": entries[0]["tree_sha256"]}
        assert entries[1]["event_id"] == "evt-0001" and entries[1]["timestamp"] == "2026-01-02T09:00:00Z"

    def test_no_event_prose_can_enter(self):
        # reveal() has no parameter for prose; extra mapping keys are dropped.
        h = WorldHistory()
        _reveal_seed(h)
        h.reveal(1, EV1, event_id="evt-0001", timestamp="t",
                 changed_paths=[{"op": "write_file", "path": "NEW.md", "body": "PROSE-BODY", "role": "trigger"}])
        dumped = json.dumps(h.history())
        assert "PROSE-BODY" not in dumped and "trigger" not in dumped

    def test_returned_entries_are_copies(self):
        h = _three_states()
        got = h.history()
        got[1]["changed_paths"].append({"op": "write_file", "path": "evil"})
        got[1]["changed_paths"][0]["path"] = "evil"
        got[0]["tree_sha256"] = "0" * 64
        got.append({"seq": 3})
        assert h.history() == _three_states().history()
        assert h.revealed_seq == 2

    def test_reveal_returns_hash_recorded_in_history(self):
        h = WorldHistory()
        t0 = _reveal_seed(h)
        t1 = h.reveal(1, EV1, event_id="evt-0001", timestamp="t", changed_paths=[])
        assert [e["tree_sha256"] for e in h.history()] == [t0, t1]
        assert t0 != t1

    def test_tree_hash_matches_canonical_tree_hash(self, tmp_path: Path):
        for i, files in enumerate((SEED, EV1, EV2, {})):
            root = tmp_path / f"tree{i}"
            root.mkdir()
            for rel, data in files.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(data)
            h = WorldHistory()
            assert h.reveal(0, files, event_id=None, timestamp=None, changed_paths=[]) == tree_hash(root)
            # Round trip through snapshot_files too, including cache by-products on disk.
            (root / "__pycache__").mkdir(exist_ok=True)
            (root / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"\0")
            assert WorldHistory().reveal(0, WorldHistory.snapshot_files(root), event_id=None, timestamp=None,
                                         changed_paths=[]) == tree_hash(root)


# ----------------------------------------------------- future-state leakage
ALL_QUERIES = (
    ("list_at", lambda h, s: h.list_at(s)),
    ("list_at_prefix", lambda h, s: h.list_at(s, "app")),
    ("read_at", lambda h, s: h.read_at(s, "app/config.py")),
    ("read_at_missing", lambda h, s: h.read_at(s, "does/not/exist.py")),
    ("diff_b", lambda h, s: h.diff(0, s)),
    ("diff_a", lambda h, s: h.diff(s, 0)),
    ("diff_path", lambda h, s: h.diff(0, s, "app/config.py")),
)


class TestFutureBlindness:
    @pytest.mark.parametrize("name,query", ALL_QUERIES, ids=[q[0] for q in ALL_QUERIES])
    @pytest.mark.parametrize("seq", [2, 3, 10, 10**6, 2**63, 10**30, -1, -2, -(10**30)])
    def test_unrevealed_seq_has_one_error_form(self, name, query, seq):
        h = WorldHistory()
        _reveal_seed(h)
        h.reveal(1, EV1, event_id="evt-0001", timestamp="t", changed_paths=[])
        with pytest.raises(ToolError) as exc:
            query(h, seq)
        assert type(exc.value) is ToolError
        assert str(exc.value) == _unavailable(seq, 1)

    def test_absurd_seq_beyond_int_str_limit(self):
        h = _three_states()
        seq = 10**5000
        for _, query in ALL_QUERIES:
            with pytest.raises(ToolError) as exc:
                query(h, seq)
            assert str(exc.value) == "no repository state at seq 1" + "0" * 5000 + "; available: 0..2"
            with pytest.raises(ToolError) as exc:
                query(h, -seq)
            assert str(exc.value) == "no repository state at seq -1" + "0" * 5000 + "; available: 0..2"

    def test_error_form_is_identical_for_negative_next_and_absurd(self):
        h = _three_states()
        messages = {}
        for seq in (-1, 3, 4, 10**12):
            with pytest.raises(ToolError) as exc:
                h.read_at(seq, "README.md")
            messages[seq] = str(exc.value)
        templates = {m.replace(str(s), "N", 1) for s, m in messages.items()}
        assert templates == {"no repository state at seq N; available: 0..2"}

    def test_error_does_not_depend_on_future_content(self):
        # Two histories with the same revealed prefix but different would-be
        # futures behave identically for every unrevealed query.
        a, b = WorldHistory(), WorldHistory()
        for h in (a, b):
            _reveal_seed(h)
        for _, query in ALL_QUERIES:
            for seq in (1, 2, 99, -1):
                errs = []
                for h in (a, b):
                    with pytest.raises(ToolError) as exc:
                        query(h, seq)
                    errs.append(str(exc.value))
                assert errs[0] == errs[1] == _unavailable(seq, 0)
        # Then reveal state 1 differently in each: only now do they differ.
        a.reveal(1, EV1, event_id="evt-0001", timestamp="t", changed_paths=[])
        b.reveal(1, {**SEED, "x": FUTURE_MARKER}, event_id="evt-0001", timestamp="t", changed_paths=[])
        assert a.list_at(1) != b.list_at(1)

    def test_next_state_does_not_exist_before_reveal(self):
        h = WorldHistory()
        _reveal_seed(h)
        future = {**SEED, "future.md": FUTURE_MARKER}
        # Physically: only the revealed state and its blobs are held.
        assert h.revealed_seq == 0
        assert len(h._states) == 1 and len(h._entries) == 1
        assert all(FUTURE_MARKER not in blob for blob in h._blobs.values())
        assert set(h._blobs) == {e for e in h._states[0].values()}
        assert set(vars(h)) == {"_blobs", "_states", "_entries"}
        with pytest.raises(ToolError, match=re.escape(_unavailable(1, 0))):
            h.read_at(1, "future.md")
        with pytest.raises(ToolError, match=re.escape("no such file: 'future.md'")):
            h.read_at(0, "future.md")
        with pytest.raises(ToolError):
            h.list_at(0, "future.md")
        assert h.diff(0, 0)["files"] == []
        h.reveal(1, future, event_id="evt-0001", timestamp="t", changed_paths=[{"op": "write_file", "path": "future.md"}])
        assert h.read_at(1, "future.md") == FUTURE_MARKER.decode()

    @pytest.mark.parametrize("bad", [True, False, 1.0, "1", None, [1]])
    def test_non_int_seq_rejected_by_type(self, bad):
        h = _three_states()
        # bool is an int subclass: True must not alias seq 1.
        for query in (lambda s: h.list_at(s), lambda s: h.read_at(s, "README.md"),
                      lambda s: h.diff(s, 0), lambda s: h.diff(0, s)):
            with pytest.raises(ToolError, match="seq must be an integer"):
                query(bad)

    def test_nothing_revealed(self):
        h = WorldHistory()
        for seq in (0, 1, -1):
            with pytest.raises(ToolError) as exc:
                h.read_at(seq, "README.md")
            assert str(exc.value) == f"no repository state at seq {seq}; available: none"
        with pytest.raises(ToolError):
            h.list_at(0)
        with pytest.raises(ToolError):
            h.diff(0, 0)

    def test_seq_checked_before_path(self):
        # For an unrevealed seq the reply is the same whatever the path is.
        h = _three_states()
        for path in ("README.md", "nope", "../../etc/passwd", "/abs"):
            with pytest.raises(ToolError) as exc:
                h.read_at(3, path)
            assert type(exc.value) is ToolError
            assert str(exc.value) == _unavailable(3, 2)


# ------------------------------------------------------------------- paths
TRAVERSALS = ["../x", "app/../../x", "/etc/passwd", "~/x", "~root/x", "a\\b", "C:/x", "app/\x00", "\udcff"]


class TestPaths:
    @pytest.mark.parametrize("path", TRAVERSALS)
    def test_read_at_denies(self, path):
        h = _three_states()
        with pytest.raises(AccessDenied):
            h.read_at(0, path)

    @pytest.mark.parametrize("path", TRAVERSALS)
    def test_list_at_denies(self, path):
        h = _three_states()
        with pytest.raises(AccessDenied):
            h.list_at(0, path)

    @pytest.mark.parametrize("path", TRAVERSALS)
    def test_diff_denies(self, path):
        h = _three_states()
        with pytest.raises(AccessDenied):
            h.diff(0, 1, path)

    def test_read_at_root_and_empty_denied(self):
        h = _three_states()
        for p in (".", "", "./"):
            with pytest.raises(AccessDenied):
                h.read_at(0, p)

    def test_non_string_paths_denied(self):
        h = _three_states()
        for p in (None, 1, b"README.md"):
            with pytest.raises(AccessDenied):
                h.read_at(0, p)  # type: ignore[arg-type]
            with pytest.raises(AccessDenied):
                h.list_at(0, p)  # type: ignore[arg-type]

    def test_read_at_normalizes_like_workspace(self):
        h = _three_states()
        assert h.read_at(0, "./app//config.py") == "LIMIT = 1\n"
        assert h.read_at(1, "app/config.py") == "LIMIT = 5\n"

    def test_read_at_missing_directory_and_binary(self):
        h = _three_states()
        with pytest.raises(ToolError, match="no such file: 'app/nope.py'"):
            h.read_at(0, "app/nope.py")
        with pytest.raises(ToolError, match="not a file: 'app'"):
            h.read_at(0, "app")
        with pytest.raises(ToolError, match="no such file"):
            h.read_at(2, "app/core.py")  # deleted by event 2
        assert h.read_at(1, "app/core.py") == "def f():\n    return 1\n"
        with pytest.raises(ToolError, match="not a UTF-8 text file: 'blob.bin'"):
            h.read_at(2, "blob.bin")

    def test_list_at_semantics_match_workspace(self, tmp_path: Path):
        h = _three_states()
        root = tmp_path / "ws"
        for rel, data in EV1.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data)
        ws = Workspace(root)
        for prefix in (".", "./", "app", "app/", "./app", "docs", "docs/adr", "app/config.py", "README.md"):
            assert h.list_at(1, prefix) == ws.list_files(prefix), prefix
        for prefix in ("nope", "app/nope", "ap"):
            with pytest.raises(ToolError, match="no such directory"):
                ws.list_files(prefix)
            with pytest.raises(ToolError, match="no such directory"):
                h.list_at(1, prefix)

    def test_list_at_prefix_is_segment_based(self):
        h = WorldHistory()
        _reveal_seed(h, {"app/x.py": b"", "app2/y.py": b"", "app.md": b""})
        assert h.list_at(0, "app") == ["app/x.py"]
        assert h.list_at(0) == ["app.md", "app/x.py", "app2/y.py"]


# -------------------------------------------------------------------- diff
class TestDiff:
    def test_statuses_and_shape(self):
        h = _three_states()
        d = h.diff(0, 2)
        assert set(d) == {"seq_a", "seq_b", "path", "files", "diff", "truncated"}
        assert d["seq_a"] == 0 and d["seq_b"] == 2 and d["path"] is None and d["truncated"] is False
        assert d["files"] == [
            {"path": "NEW.md", "status": "added"},
            {"path": "app/config.py", "status": "modified"},
            {"path": "app/core.py", "status": "deleted"},
            {"path": "blob.bin", "status": "added"},
        ]
        text = d["diff"]
        assert "--- a/app/config.py\n+++ b/app/config.py\n" in text
        assert "-LIMIT = 1\n+LIMIT = 5\n" in text
        assert "--- a/NEW.md\n+++ b/NEW.md\n@@ -0,0 +1 @@\n+new file\n" in text
        assert "--- a/app/core.py\n+++ b/app/core.py\n" in text and "-    return 1\n" in text
        assert "Binary files a/blob.bin and b/blob.bin differ\n" in text
        assert "\xff" not in text and "binary" not in text.replace("Binary files", "")
        # Files appear in the text in path order.
        order = [text.index(f"a/{f['path']}") for f in d["files"]]
        assert order == sorted(order)

    def test_reverse_order_is_a_to_b(self):
        h = _three_states()
        d = h.diff(2, 0)
        assert d["seq_a"] == 2 and d["seq_b"] == 0
        assert d["files"] == [
            {"path": "NEW.md", "status": "deleted"},
            {"path": "app/config.py", "status": "modified"},
            {"path": "app/core.py", "status": "added"},
            {"path": "blob.bin", "status": "deleted"},
        ]
        assert "-LIMIT = 5\n+LIMIT = 1\n" in d["diff"]

    def test_same_state_is_empty(self):
        h = _three_states()
        for s in (0, 1, 2):
            assert h.diff(s, s) == {"seq_a": s, "seq_b": s, "path": None, "files": [], "diff": "", "truncated": False}

    def test_path_filter_file_and_directory(self):
        h = _three_states()
        f = h.diff(0, 2, "app/config.py")
        assert f["path"] == "app/config.py"
        assert f["files"] == [{"path": "app/config.py", "status": "modified"}]
        assert "core.py" not in f["diff"] and "NEW.md" not in f["diff"]
        d = h.diff(0, 2, "app")
        assert d["path"] == "app"
        assert [x["path"] for x in d["files"]] == ["app/config.py", "app/core.py"]
        assert h.diff(0, 2, "./app/")["files"] == d["files"]
        # Segment-based: "ap" matches neither "app/..." nor anything else.
        assert h.diff(0, 2, "ap")["files"] == []
        assert h.diff(0, 2, "nowhere")["files"] == []
        assert h.diff(0, 2, "README.md")["files"] == []  # unchanged
        root = h.diff(0, 2, ".")
        assert root["path"] == "." and root["files"] == h.diff(0, 2)["files"]

    def test_binary_on_one_side(self):
        h = WorldHistory()
        _reveal_seed(h, {"f": b"text\n"})
        h.reveal(1, {"f": b"\xc3\x28"}, event_id="evt-0001", timestamp="t", changed_paths=[])
        d = h.diff(0, 1)
        assert d["files"] == [{"path": "f", "status": "modified"}]
        assert d["diff"] == "Binary files a/f and b/f differ\n"

    def test_missing_trailing_newline_marker(self):
        h = WorldHistory()
        _reveal_seed(h, {"f": b"a\nb"})
        h.reveal(1, {"f": b"a\nc"}, event_id="evt-0001", timestamp="t", changed_paths=[])
        text = h.diff(0, 1)["diff"]
        assert text == "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n a\n-b\n\\ No newline at end of file\n+c\n\\ No newline at end of file\n"

    def test_only_newline_splits_lines(self):
        h = WorldHistory()
        _reveal_seed(h, {"f": "a\rb\u2028c\n".encode()})
        h.reveal(1, {"f": "a\rb\u2028d\n".encode()}, event_id="evt-0001", timestamp="t", changed_paths=[])
        text = h.diff(0, 1)["diff"]
        assert text == "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\rb\u2028c\n+a\rb\u2028d\n"

    def test_truncation(self):
        h = WorldHistory()
        big_a = "".join(f"line {i}\n" for i in range(20_000)).encode()
        big_b = "".join(f"LINE {i}\n" for i in range(20_000)).encode()
        _reveal_seed(h, {"a.txt": big_a, "z.txt": b"1\n"})
        h.reveal(1, {"a.txt": big_b, "z.txt": b"2\n"}, event_id="evt-0001", timestamp="t", changed_paths=[])
        d = h.diff(0, 1)
        assert d["truncated"] is True
        assert len(d["diff"]) == MAX_DIFF_CHARS
        # Every changed file is still listed, even those whose text was cut.
        assert d["files"] == [{"path": "a.txt", "status": "modified"}, {"path": "z.txt", "status": "modified"}]
        assert d == h.diff(0, 1)
        small = h.diff(0, 1, "z.txt")
        assert small["truncated"] is False and "-1\n+2\n" in small["diff"]

    def test_exactly_at_cap_is_not_truncated(self):
        h = WorldHistory()
        header = "--- a/f\n+++ b/f\n@@ -0,0 +1 @@\n+"
        body = "x" * (MAX_DIFF_CHARS - len(header) - 1) + "\n"
        _reveal_seed(h, {})
        h.reveal(1, {"f": body.encode()}, event_id="evt-0001", timestamp="t", changed_paths=[])
        d = h.diff(0, 1)
        assert len(d["diff"]) == MAX_DIFF_CHARS and d["truncated"] is False

    def test_empty_files(self):
        h = WorldHistory()
        _reveal_seed(h, {"keep": b"k\n"})
        h.reveal(1, {"keep": b"k\n", "empty": b""}, event_id="evt-0001", timestamp="t", changed_paths=[])
        d = h.diff(0, 1)
        assert d["files"] == [{"path": "empty", "status": "added"}]
        assert d["diff"] == ""

    def test_deterministic(self):
        a, b = _three_states(), _three_states()
        for args in ((0, 2), (2, 0), (1, 2, "app"), (0, 1, None)):
            assert json.dumps(a.diff(*args), sort_keys=True) == json.dumps(b.diff(*args), sort_keys=True)
            assert a.diff(*args) == a.diff(*args)
        assert a.history() == b.history()


# ------------------------------------------------------------ snapshot_files
class TestSnapshotFiles:
    def test_reads_regular_files_sorted(self, tmp_path: Path):
        root = tmp_path / "r"
        (root / "b").mkdir(parents=True)
        (root / "b" / "x.py").write_bytes(b"x\n")
        (root / "a.txt").write_bytes(b"\xff\x00")
        (root / "empty_dir").mkdir()
        snap = WorldHistory.snapshot_files(root)
        assert list(snap) == ["a.txt", "b/x.py"]
        assert snap == {"a.txt": b"\xff\x00", "b/x.py": b"x\n"}
        assert all(type(v) is bytes for v in snap.values())

    def test_skips_caches_symlinks_and_fifos(self, tmp_path: Path):
        root = tmp_path / "r"
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("SECRET")
        (root / "pkg" / "__pycache__").mkdir(parents=True)
        (root / "pkg" / "mod.py").write_text("x = 1\n")
        (root / "pkg" / "__pycache__" / "mod.cpython-311.pyc").write_bytes(b"\0")
        (root / "pkg" / "stray.pyc").write_bytes(b"\0")
        (root / "pkg" / "stray.pyo").write_bytes(b"\0")
        (root / ".pytest_cache").mkdir()
        (root / ".pytest_cache" / "README.md").write_text("cache")
        (root / ".mypy_cache").mkdir()
        (root / ".mypy_cache" / "x.json").write_text("{}")
        os.symlink(outside / "secret.txt", root / "link_file.txt")
        os.symlink(outside, root / "link_dir")
        os.symlink("does-not-exist", root / "dangling")
        os.mkfifo(root / "pipe")
        snap = WorldHistory.snapshot_files(root)  # must not block on the FIFO
        assert snap == {"pkg/mod.py": b"x = 1\n"}
        assert all(b"SECRET" not in v for v in snap.values())

    def test_snapshot_round_trip_matches_tree_hash_of_seed(self):
        scenario = load_scenario(SMOKE_MANIFEST)
        snap = WorldHistory.snapshot_files(scenario.seed_dir)
        h = WorldHistory()
        assert h.reveal(0, snap, event_id=None, timestamp=None, changed_paths=[]) == tree_hash(scenario.seed_dir)


# --------------------------------------------------------- ToolBox wiring
def test_toolbox_serves_history_and_records_errors(tmp_path: Path):
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    records: list[dict] = []
    h = _three_states()
    tb = ToolBox(Workspace(ws_root), StepBudget(), records.append, history=h)
    assert tb.history() == h.history()
    assert tb.read_at(1, "app/config.py") == "LIMIT = 5\n"
    assert tb.list_at(0, "app") == ["app/config.py", "app/core.py"]
    assert tb.diff(0, 1, "app")["files"] == [{"path": "app/config.py", "status": "modified"}]
    with pytest.raises(ToolError, match=re.escape(_unavailable(3, 2))):
        tb.read_at(3, "README.md")
    with pytest.raises(ToolError, match="must be an integer"):
        tb.read_at(True, "README.md")  # type: ignore[arg-type]
    with pytest.raises(AccessDenied):
        tb.read_at(0, "../outside")
    statuses = [(r["tool"], r["status"]) for r in records]
    assert statuses == [("history", "ok"), ("read_at", "ok"), ("list_at", "ok"), ("diff", "ok"),
                        ("read_at", "error"), ("read_at", "error"), ("read_at", "denied")]
    assert records[4]["error"] == _unavailable(3, 2)


# --------------------------------------------- realistic: frozen smoke world
def test_smoke_scenario_world_replay_matches_manifest_hashes(tmp_path: Path):
    scenario = load_scenario(SMOKE_MANIFEST)
    events = scenario.load_events()
    expected = scenario.data["world_state_hashes"]
    assert len(expected) == len(events) == 10

    root = tmp_path / "world"
    copy_tree(scenario.seed_dir, root)
    ws = Workspace(root)
    h = WorldHistory()
    seed_hash = h.reveal(0, WorldHistory.snapshot_files(root), event_id=None, timestamp=None, changed_paths=[])
    assert seed_hash == scenario.data["content_hashes"]["seed_repo"] == tree_hash(scenario.seed_dir)

    for i, ev in enumerate(events):
        # Before the reveal, the state this event produces does not exist.
        with pytest.raises(ToolError, match=re.escape(_unavailable(ev.seq, ev.seq - 1))):
            h.list_at(ev.seq)
        apply_event(ev, ws)
        changed = [asdict(c) for c in ev.agent_view().changed_paths]
        got = h.reveal(ev.seq, WorldHistory.snapshot_files(root), event_id=ev.event_id,
                       timestamp=ev.timestamp, changed_paths=changed)
        assert got == expected[i] == tree_hash(root), ev.event_id
        assert h.revealed_seq == ev.seq

    entries = h.history()
    assert [e["seq"] for e in entries] == list(range(11))
    assert [e["event_id"] for e in entries] == [None] + [ev.event_id for ev in events]
    assert [e["tree_sha256"] for e in entries] == [seed_hash] + expected
    # No event prose leaks into the timeline.
    dumped = json.dumps(entries)
    for ev in events:
        assert ev.body not in dumped
        assert ev.subject not in dumped
    assert scenario.scenario_id not in dumped
    # Every state's diff against its predecessor touches exactly the event's changed paths.
    for ev in events:
        changed = {c.path for c in ev.world_changes}
        diffed = {f["path"] for f in h.diff(ev.seq - 1, ev.seq)["files"]}
        assert diffed <= changed, ev.event_id
    # The final state reads back the world's bytes.
    for rel, data in WorldHistory.snapshot_files(root).items():
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        assert h.read_at(10, rel) == text
