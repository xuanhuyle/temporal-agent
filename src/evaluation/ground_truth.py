"""Evaluator-only ground truth (``tab.ground_truth/1``).

This is the only module that reads ``world/ground_truth``. Nothing it returns
may be passed to a contestant; the runner hands contestants
``harness.agent.AgentEvent`` views only.

Every file a reconsideration references (hidden tests, reference
remediations) is read into memory once, at load time, right after the
scenario's content hashes were verified; the evaluator never re-reads ground
truth from disk while agent code may be running.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from harness.agent import HISTORICAL_STATE_KEYS, canonical_target
from harness.workspace import AccessDenied, validate_relpath

GT_SCHEMA_VERSION = "tab.ground_truth/1"
LABELS_FILE = "labels.json"
CANARY_FILE = "CANARY"
PATTERNS = ("A", "B", "C", "D", "E", "F", "G")
ROLES = ("distractor", "decision_setup", "parked_setup", "trigger")
TARGET_KINDS = ("decision", "work_item")
LAGS = ("near", "medium", "far")
WORDINGS = ("explicit", "natural", "indirect")
EVIDENCE_LOCI = ("workspace", "event_history", "mixed")
HISTORICAL_KEYS = HISTORICAL_STATE_KEYS
COMPARISON_OPS = ("eq", "ne", "lt", "le", "gt", "ge")

# Temporal-lag buckets by number of events between the decision and the trigger
# (seed decisions count as event 0). Fixed for evaluator v0.1.
LAG_NEAR_MAX_EVENTS = 2
LAG_MEDIUM_MAX_EVENTS = 6

CHECK_KEYS: dict[str, tuple[set[str], set[str]]] = {
    "file_exists": ({"type", "path"}, set()),
    "file_absent": ({"type", "path"}, set()),
    "file_regex": ({"type", "path", "pattern", "must_match"}, set()),
    "json_value": ({"type", "path", "pointer", "op", "value"}, set()),
    "hidden_pytest": ({"type", "files"}, set()),
}
_TOP_KEYS = {"schema_version", "scenario_id", "canary", "targets", "events", "reconsiderations"}
_EVENT_KEYS = {"role", "should_trigger_reconsideration", "near_miss_of", "acceptable_reopens", "notes"}
_R_KEYS = {
    "id",
    "pattern",
    "trigger_event",
    "affected_targets",
    "window",
    "abstention_acceptable",
    "evidence_locus",
    "causal_path",
    "historical_state",
    "remediation",
    "difficulty",
    "notes",
}


def lag_bucket(lag_events: int) -> str:
    if lag_events <= LAG_NEAR_MAX_EVENTS:
        return "near"
    if lag_events <= LAG_MEDIUM_MAX_EVENTS:
        return "medium"
    return "far"


class GroundTruthError(ValueError):
    pass


@dataclass(frozen=True)
class EventLabel:
    event_id: str
    role: str
    should_trigger_reconsideration: bool
    near_miss_of: str | None
    acceptable_reopens: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class RemediationAlternative:
    id: str
    checks: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Remediation:
    evaluate_at_seq: int
    acceptable: tuple[RemediationAlternative, ...]
    reference: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Reconsideration:
    id: str
    pattern: str
    trigger_event: str
    trigger_seq: int
    affected_targets: tuple[str, ...]
    window_from: int
    window_to: int
    abstention_acceptable: bool
    evidence_locus: str
    causal_path: tuple[dict[str, Any], ...]
    historical_state: dict[str, tuple[str, ...]]
    remediation: Remediation | None
    difficulty: dict[str, Any]
    notes: str = ""

    def in_window(self, seq: int) -> bool:
        return self.window_from <= seq <= self.window_to


@dataclass(frozen=True)
class GroundTruth:
    scenario_id: str
    canary: str
    root: Path
    targets: Mapping[str, dict[str, Any]]
    events: Mapping[str, EventLabel]
    reconsiderations: tuple[Reconsideration, ...]
    event_seq: Mapping[str, int] = field(default_factory=dict)
    files: Mapping[str, bytes] = field(default_factory=dict)
    hidden_test_counts: Mapping[str, int] = field(default_factory=dict)

    def file_bytes(self, rel: str) -> bytes:
        """In-memory content of a ground-truth file referenced by a reconsideration."""
        if rel not in self.files:
            raise GroundTruthError(f"ground-truth file not loaded: {rel}")
        return self.files[rel]


def _fail(msg: str) -> None:
    raise GroundTruthError(msg)


def _exact_keys(obj: Any, required: set[str], optional: set[str], where: str) -> None:
    if not isinstance(obj, dict):
        _fail(f"{where}: must be an object")
    keys = set(obj)
    if not required <= keys or keys - required - optional:
        _fail(f"{where}: keys mismatch (missing={sorted(required - keys)}, unknown={sorted(keys - required - optional)})")


def _load_file(root: Path, rel: str, files: dict[str, bytes]) -> bytes:
    try:
        parts = validate_relpath(rel)
    except AccessDenied as exc:
        _fail(f"bad ground-truth file reference {rel!r}: {exc}")
    path = root.joinpath(*parts)
    if path.is_symlink() or not path.is_file():
        _fail(f"ground-truth file missing: {rel}")
    if root.resolve() not in path.resolve().parents:
        _fail(f"ground-truth file escapes its directory: {rel}")
    data = path.read_bytes()
    files["/".join(parts)] = data
    return data


def count_test_functions(source: bytes, name: str) -> int:
    """Number of pytest test items (module-level ``test_*`` and ``Test*.test_*``)."""
    tree = ast.parse(source, filename=name)
    count = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            count += 1
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            count += sum(
                1
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test")
            )
    return count


def _validate_check(check: Any, where: str, root: Path, files: dict[str, bytes], counts: dict[str, int]) -> dict[str, Any]:
    if not isinstance(check, dict) or check.get("type") not in CHECK_KEYS:
        _fail(f"{where}: unknown check type {check.get('type') if isinstance(check, dict) else check!r}")
    required, optional = CHECK_KEYS[check["type"]]
    _exact_keys(check, required, optional, where)
    if "path" in check:
        try:
            validate_relpath(check["path"])
        except AccessDenied as exc:
            _fail(f"{where}: bad path: {exc}")
    if check["type"] == "file_regex":
        try:
            re.compile(check["pattern"])
        except (re.error, TypeError) as exc:
            _fail(f"{where}: bad regex: {exc}")
        if not isinstance(check["must_match"], bool):
            _fail(f"{where}: must_match must be a boolean")
    if check["type"] == "json_value":
        if check["op"] not in COMPARISON_OPS:
            _fail(f"{where}: op must be one of {COMPARISON_OPS}")
        if not isinstance(check["pointer"], str) or not (check["pointer"] == "" or check["pointer"].startswith("/")):
            _fail(f"{where}: pointer must be a JSON pointer")
    if check["type"] == "hidden_pytest":
        hidden = check["files"]
        if not isinstance(hidden, list) or not hidden:
            _fail(f"{where}: hidden_pytest needs a non-empty 'files' list")
        names = set()
        for rel in hidden:
            data = _load_file(root, rel, files)
            base = Path(rel).name
            if not (base.startswith("test_") and base.endswith(".py")) or base in names:
                _fail(f"{where}: hidden tests must be uniquely named test_*.py files")
            names.add(base)
            try:
                n = count_test_functions(data, rel)
            except SyntaxError as exc:
                _fail(f"{where}: hidden test {rel} does not parse: {exc}")
            if n == 0:
                _fail(f"{where}: hidden test {rel} defines no tests")
            counts[rel] = n
    return dict(check)


def load_ground_truth(
    gt_dir: Path, event_seq: Mapping[str, int], event_dates: Mapping[str, str] | None = None
) -> GroundTruth:
    """Load and cross-validate ground truth against the event stream.

    ``event_seq`` maps every event id in the stream to its ``seq``;
    ``event_dates`` (optional) maps event ids to ``YYYY-MM-DD...`` timestamps and
    enables the ``lag_days`` consistency check.

    Difficulty labels are checked against the data, not trusted: ``causal_depth``
    must equal the index of the first affected target in ``causal_path`` (whose
    first node is the trigger event), ``lag_events`` must equal the trigger seq
    minus the seq that introduced the target (seed = 0), ``temporal_lag`` must be
    the bucket of ``lag_events``, and ``lag_days`` must match ``decided_on``.
    """
    gt_dir = Path(gt_dir)
    try:
        raw = json.loads((gt_dir / LABELS_FILE).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GroundTruthError(f"{LABELS_FILE}: invalid JSON: {exc}") from None
    _exact_keys(raw, _TOP_KEYS, set(), LABELS_FILE)
    if raw["schema_version"] != GT_SCHEMA_VERSION:
        _fail(f"unsupported schema_version {raw['schema_version']!r}")
    if not isinstance(raw["canary"], str) or len(raw["canary"]) < 16:
        _fail("canary must be a string of at least 16 characters")
    n_events = len(event_seq)
    valid_refs = set(event_seq) | {"seed"}
    files: dict[str, bytes] = {}
    counts: dict[str, int] = {}

    def ref_seq(ref: str) -> int:
        return 0 if ref == "seed" else event_seq[ref]

    # ---- targets
    targets: dict[str, dict[str, Any]] = {}
    for tid, info in raw["targets"].items():
        if canonical_target(tid) != tid:
            _fail(f"target id {tid!r} is not canonical")
        _exact_keys(info, {"kind", "introduced_by", "decided_on", "summary"}, set(), f"targets.{tid}")
        if info["kind"] not in TARGET_KINDS:
            _fail(f"targets.{tid}.kind must be one of {TARGET_KINDS}")
        if info["introduced_by"] not in valid_refs:
            _fail(f"targets.{tid}.introduced_by must be 'seed' or an event id")
        try:
            date.fromisoformat(info["decided_on"])
        except (TypeError, ValueError):
            _fail(f"targets.{tid}.decided_on must be a YYYY-MM-DD date")
        targets[tid] = dict(info)

    # ---- event labels
    events: dict[str, EventLabel] = {}
    if set(raw["events"]) != set(event_seq):
        _fail("ground truth must label exactly the events in the stream")
    for eid, lab in raw["events"].items():
        _exact_keys(lab, _EVENT_KEYS, set(), f"events.{eid}")
        if lab["role"] not in ROLES:
            _fail(f"events.{eid}.role must be one of {ROLES}")
        if not isinstance(lab["should_trigger_reconsideration"], bool):
            _fail(f"events.{eid}.should_trigger_reconsideration must be a boolean")
        if lab["should_trigger_reconsideration"] != (lab["role"] == "trigger"):
            _fail(f"events.{eid}: should_trigger_reconsideration must be true exactly for role=trigger")
        if lab["near_miss_of"] is not None and lab["near_miss_of"] not in targets:
            _fail(f"events.{eid}.near_miss_of must be null or a known target")
        acceptable = lab["acceptable_reopens"]
        if not isinstance(acceptable, list) or any(t not in targets for t in acceptable):
            _fail(f"events.{eid}.acceptable_reopens must list known targets")
        events[eid] = EventLabel(
            event_id=eid,
            role=lab["role"],
            should_trigger_reconsideration=lab["should_trigger_reconsideration"],
            near_miss_of=lab["near_miss_of"],
            acceptable_reopens=tuple(acceptable),
            notes=lab["notes"],
        )

    # ---- reconsiderations
    recs: list[Reconsideration] = []
    seen_ids: set[str] = set()
    for i, r in enumerate(raw["reconsiderations"]):
        where = f"reconsiderations[{i}]"
        _exact_keys(r, _R_KEYS - {"notes"}, {"notes"}, where)
        rid = r["id"]
        if not isinstance(rid, str) or rid in seen_ids:
            _fail(f"{where}: id must be a unique string")
        seen_ids.add(rid)
        if r["pattern"] not in PATTERNS:
            _fail(f"{where}: pattern must be one of {PATTERNS}")
        trig = r["trigger_event"]
        if trig not in event_seq:
            _fail(f"{where}: unknown trigger_event {trig}")
        if events[trig].role != "trigger":
            _fail(f"{where}: trigger_event {trig} must be labelled role=trigger, should_trigger=true")
        affected = r["affected_targets"]
        if not isinstance(affected, list) or not affected or len(set(affected)) != len(affected):
            _fail(f"{where}: affected_targets must be a non-empty list of unique targets")
        for t in affected:
            if t not in targets:
                _fail(f"{where}: affected target {t} missing from targets registry")
            if ref_seq(targets[t]["introduced_by"]) >= event_seq[trig]:
                _fail(f"{where}: affected target {t} must exist before the trigger")
        _exact_keys(r["window"], {"from_seq", "to_seq"}, set(), f"{where}.window")
        w_from, w_to = r["window"]["from_seq"], r["window"]["to_seq"]
        if not (isinstance(w_from, int) and isinstance(w_to, int)):
            _fail(f"{where}: window bounds must be integers")
        if not (event_seq[trig] <= w_from <= w_to <= n_events):
            _fail(f"{where}: window must satisfy trigger_seq <= from_seq <= to_seq <= {n_events}")
        if not isinstance(r["abstention_acceptable"], bool):
            _fail(f"{where}: abstention_acceptable must be a boolean")
        if r["evidence_locus"] not in EVIDENCE_LOCI:
            _fail(f"{where}: evidence_locus must be one of {EVIDENCE_LOCI}")
        if not isinstance(r["causal_path"], list) or len(r["causal_path"]) < 2:
            _fail(f"{where}: causal_path needs at least two nodes")
        for j, node in enumerate(r["causal_path"]):
            _exact_keys(node, {"ref", "kind", "note"}, set(), f"{where}.causal_path[{j}]")

        # Historical state: what the decision relied on, how things really were,
        # and what has been learned since.
        _exact_keys(r["historical_state"], set(HISTORICAL_KEYS), set(), f"{where}.historical_state")
        hist: dict[str, tuple[str, ...]] = {}
        for k in HISTORICAL_KEYS:
            vals = r["historical_state"][k]
            if not isinstance(vals, list) or any(v not in valid_refs for v in vals) or len(set(vals)) != len(vals):
                _fail(f"{where}.historical_state.{k}: items must be unique 'seed' or event ids")
            hist[k] = tuple(vals)
        decided_seq = max(ref_seq(targets[t]["introduced_by"]) for t in affected)
        if not hist["known_then"]:
            _fail(f"{where}: known_then must not be empty")
        for v in hist["known_then"]:
            if ref_seq(v) > decided_seq:
                _fail(f"{where}: known_then item {v} postdates the decision")
        if not hist["known_now_about_then"]:
            _fail(f"{where}: known_now_about_then must not be empty")
        for v in hist["known_now_about_then"]:
            if not (decided_seq < ref_seq(v) <= event_seq[trig]):
                _fail(f"{where}: known_now_about_then item {v} must arrive after the decision and by the trigger")
        for v in hist["true_then"]:
            if ref_seq(v) > event_seq[trig]:
                _fail(f"{where}: true_then item {v} must be known by the trigger")

        # Difficulty labels are derived, not trusted.
        diff = r["difficulty"]
        _exact_keys(diff, {"causal_depth", "temporal_lag", "lag_events", "lag_days", "wording"}, set(), f"{where}.difficulty")
        if diff["temporal_lag"] not in LAGS or diff["wording"] not in WORDINGS:
            _fail(f"{where}: temporal_lag must be in {LAGS} and wording in {WORDINGS}")
        path_refs = [node["ref"] for node in r["causal_path"]]
        if path_refs[0] != trig:
            _fail(f"{where}: causal_path must start at the trigger event")
        depth = next((k for k, ref in enumerate(path_refs) if ref in affected), None)
        if depth is None or diff["causal_depth"] != depth:
            _fail(f"{where}: causal_depth must equal the position of the affected target in causal_path ({depth})")
        primary = targets[affected[0]]
        intro_seq = ref_seq(primary["introduced_by"])
        if diff["lag_events"] != event_seq[trig] - intro_seq:
            _fail(f"{where}: lag_events must be {event_seq[trig] - intro_seq} (trigger seq - introducing seq)")
        if diff["temporal_lag"] != lag_bucket(diff["lag_events"]):
            _fail(f"{where}: temporal_lag must be {lag_bucket(diff['lag_events'])!r} for lag_events={diff['lag_events']}")
        if event_dates is not None:
            days = (date.fromisoformat(event_dates[trig][:10]) - date.fromisoformat(primary["decided_on"])).days
            if diff["lag_days"] != days:
                _fail(f"{where}: lag_days must be {days} (trigger date - decided_on)")

        remediation = None
        if r["remediation"] is not None:
            rem = r["remediation"]
            _exact_keys(rem, {"evaluate_at_seq", "acceptable", "reference"}, set(), f"{where}.remediation")
            at = rem["evaluate_at_seq"]
            if not isinstance(at, int) or not (w_from <= at <= n_events):
                _fail(f"{where}: evaluate_at_seq must be within [from_seq, {n_events}]")
            if not isinstance(rem["acceptable"], list) or not rem["acceptable"]:
                _fail(f"{where}: remediation.acceptable must be a non-empty list")
            alts = []
            for k, alt in enumerate(rem["acceptable"]):
                _exact_keys(alt, {"id", "checks"}, set(), f"{where}.remediation.acceptable[{k}]")
                if not alt["checks"]:
                    _fail(f"{where}: remediation alternative {alt['id']} has no checks")
                checks = tuple(
                    _validate_check(c, f"{where}.remediation.acceptable[{k}].checks[{m}]", gt_dir, files, counts)
                    for m, c in enumerate(alt["checks"])
                )
                alts.append(RemediationAlternative(id=alt["id"], checks=checks))
            refs = []
            for k, op in enumerate(rem["reference"]):
                _exact_keys(op, {"op", "path"}, {"source"}, f"{where}.remediation.reference[{k}]")
                if op["op"] not in ("write_file", "delete_file"):
                    _fail(f"{where}: reference op must be write_file or delete_file")
                try:
                    validate_relpath(op["path"])
                except AccessDenied as exc:
                    _fail(f"{where}: bad reference path: {exc}")
                if op["op"] == "write_file":
                    if "source" not in op:
                        _fail(f"{where}: reference write_file needs a source")
                    _load_file(gt_dir, op["source"], files)
                refs.append(dict(op))
            remediation = Remediation(evaluate_at_seq=at, acceptable=tuple(alts), reference=tuple(refs))
        recs.append(
            Reconsideration(
                id=rid,
                pattern=r["pattern"],
                trigger_event=trig,
                trigger_seq=event_seq[trig],
                affected_targets=tuple(affected),
                window_from=w_from,
                window_to=w_to,
                abstention_acceptable=r["abstention_acceptable"],
                evidence_locus=r["evidence_locus"],
                causal_path=tuple(dict(n) for n in r["causal_path"]),
                historical_state=hist,
                remediation=remediation,
                difficulty=dict(diff),
                notes=r.get("notes", ""),
            )
        )

    triggers = {r.trigger_event for r in recs}
    for eid, lab in events.items():
        if lab.should_trigger_reconsideration and eid not in triggers:
            _fail(f"events.{eid} should trigger reconsideration but no reconsideration uses it")

    return GroundTruth(
        scenario_id=raw["scenario_id"],
        canary=raw["canary"],
        root=gt_dir.resolve(),
        targets=targets,
        events=events,
        reconsiderations=tuple(recs),
        event_seq=dict(event_seq),
        files=files,
        hidden_test_counts=counts,
    )
