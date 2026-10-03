"""tmk-hindsight: does a mechanically isolated past epistemic state beat full-history prompting?

Experiment adapter for the model-agnostic ``multiplicity`` capability. It lives
outside the core package because it uses the benchmark's provider gateway.

Two conditions, same model, same system prompt, same user-message template,
same output budget. Only the agent state handed to the model differs:

- ``baseline``: the full state, i.e. the complete timestamped timeline
  including events learned after the cutoff. The shared system prompt tells
  the model to answer from what was knowable at the cutoff.
- ``isolated``: the same state after ``snapshot -> fork(epistemic_cutoff)``.
  Facts learned after the cutoff are physically absent from the branch, and
  therefore from the model input.

Both conditions run through ``TemporalMultiplicity.fork`` and
``TemporalMultiplicity.run`` with the same :class:`GatewayBackend`; the
baseline's fork simply has no cutoff. The backend renders whatever state it is
handed and is not told the condition. Before each call the rendered request is
checked: an isolated request containing any post-cutoff event aborts the run,
and so does a baseline request missing one.

Run it from a normal terminal, never from inside Claude Code (the claude-cli
provider refuses to start when ``CLAUDECODE`` is set):

    PYTHONPATH=src python -m multiplicity_experiments.hindsight_eval \\
        --provider claude-cli --model MODEL --effort high \\
        --output results/temporal-multiplicity/NAME.json

The result file is self-contained (code and dataset hashes, git commit, the
frozen prompt, every request and raw reply, usage, the analysis and the
pre-registered verdict). It is rewritten after every call, so an interrupted
run keeps its rows; an existing file is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from harness.agent import ModelSettings
from harness.errors import ToolError
from harness.llm import ModelMessage, ModelRequest, ModelResponse
from harness.model.gateway import ProviderError, ProviderUnavailable, create_gateway

from multiplicity import AgentState, RunResult, TemporalMultiplicity

from . import hindsight_analysis

EXPERIMENT_ID = "tmk-hindsight"
PROTOCOL_VERSION = hindsight_analysis.REGISTERED_PROTOCOL_VERSION
PROTOCOL_REPEATS = hindsight_analysis.REGISTERED_REPEATS
CONDITIONS = ("baseline", "isolated")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = REPO_ROOT / "experiments" / "multiplicity" / "hindsight_cases.json"
DEFAULT_TIMEOUT_S = 600.0
PURPOSE = "tmk_hindsight"
# Retries only when no model reply was received for a transient provider fault (overload, rate limit, 5xx).
# Timeouts and over-length replies are not retried: long deliberation may depend on the condition, and a retry
# would resample one side. Retry attempts count toward the gateway's stop after 3 consecutive provider
# failures, so a fault that exhausts its retries ends the run (status incomplete).
TRANSIENT_RETRIES = 2
TRANSIENT_BACKOFF_S = 10.0
_TRANSIENT = re.compile(r"temporarily unavailable|overloaded|status (?:429|500|502|503|529)\b|RateLimitError|"
                        r"InternalServerError|ServiceUnavailableError", re.IGNORECASE)
_OVER_LENGTH = re.compile(r"exceeded CLAUDE_CODE_MAX_OUTPUT_TOKENS|output token maximum", re.IGNORECASE)
# The anthropic provider enforces a per-call cap that includes thinking; the claude-cli provider is left uncapped.
ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS = 16000
# Non-secret operator settings that change how much the model thinks; recorded so 'effort high' can be checked.
_RECORDED_ENV = re.compile(r"^(MAX_THINKING_TOKENS|CLAUDE_EFFORT|CLAUDE_CODE_EFFORT_LEVEL|ANTHROPIC_MODEL|"
                           r"ANTHROPIC_DEFAULT_\w+_MODEL|ANTHROPIC_SMALL_FAST_MODEL|CLAUDE_CODE_SUBAGENT_MODEL)$")

# Frozen prompt, protocol v0.1. Identical in both conditions. Changing it is a new protocol version.
SYSTEM = """You are taking part in a controlled evaluation of historical decision-making.

Each item gives a timeline of events numbered by sequence (seq), a cutoff sequence, a question and a list of choices. The timeline contains the decision rule and the facts.

The question asks which choice was justified at the cutoff: the decision that should have been made at that moment, from what could be known then.

- Use only the events with seq less than or equal to the cutoff.
- Events after the cutoff, if any are shown, were not knowable at the cutoff. They may reveal what was actually true, or show that the decision later turned out to be wrong. That later truth must not influence your answer.
- Apply the decision rule that was in force at the cutoff. If the rule changed after the cutoff, ignore the change.

Reply with JSON only, with exactly two keys: "choice" (exactly one of the listed choices, spelled as listed) and "confidence" (a number from 0 to 1)."""

USER_TEMPLATE = """Cutoff: seq {cutoff}

Timeline:
{timeline}

Question: {question}
Choices: {choices}"""

CHOICE_ORDER_RULE = hindsight_analysis.REGISTERED_CHOICE_ORDER_RULE

PARSE_RULE = (
    "strict JSON object; else a single fenced ```json block; else the JSON objects embedded in the text, "
    "accepted only if all that carry a 'choice' agree. The choice must equal a listed choice exactly "
    "(after trimming whitespace); confidence must be a number in [0, 1] (a bad confidence does not "
    "invalidate the choice)."
)


class CompletionService(Protocol):
    def complete(
        self,
        request: ModelRequest,
        *,
        max_output_tokens: int | None,
        timeout_s: float | None,
    ) -> tuple[ModelResponse, dict[str, Any]]: ...


class ExperimentInvalid(RuntimeError):
    """The experiment's own validity check failed (for example an isolation breach). Never caught."""


# ------------------------------------------------------------------------ cases
@dataclass(frozen=True)
class EvalCase:
    id: str
    cutoff: int
    choices: tuple[str, ...]
    correct_at_cutoff: str
    later_answer: str
    question: str
    events: tuple[dict[str, Any], ...]

    def post_cutoff_texts(self) -> tuple[str, ...]:
        return tuple(str(e["text"]) for e in self.events if int(e["seq"]) > self.cutoff)


def load_cases(path: Path = DEFAULT_CASES) -> list[EvalCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        EvalCase(
            id=item["id"],
            cutoff=int(item["cutoff"]),
            choices=tuple(item["choices"]),
            correct_at_cutoff=item["correct_at_cutoff"],
            later_answer=item["later_answer"],
            question=item["question"],
            events=tuple(item["events"]),
        )
        for item in data["cases"]
    ]


def state_for_case(case: EvalCase) -> AgentState:
    """The agent's full explicit state at the end of the case: every event as a timestamped fact.

    Everything goes into ``knowledge`` (nothing into beliefs, goals or context), because the kernel's
    epistemic cutoff filters knowledge only.
    """
    state = AgentState(seq=max(int(event["seq"]) for event in case.events))
    for event in case.events:
        seq = int(event["seq"])
        state = state.with_fact(f"event:{seq:04d}", event["text"], known_at=seq, source=case.id)
    return state


# -------------------------------------------------------------------- rendering
def presented_choices(case: EvalCase, repeat: int = 0) -> tuple[str, ...]:
    """Choice order (:data:`CHOICE_ORDER_RULE`): label-blind, and each case is shown in both orders across the
    registered two repeats. Sorting alone left the justified answer first in 5 of the 8 cases."""
    ordered = sorted(case.choices)
    return tuple(reversed(ordered) if repeat % 2 else ordered)


def visible_events(state: AgentState) -> tuple[tuple[int, str], ...]:
    """The events this state knows (known_at <= state.seq), in time order."""
    return tuple(
        (fact.known_at, str(fact.value))
        for fact in sorted(state.knowledge, key=lambda f: (f.known_at, f.key))
        if fact.known_at <= state.seq
    )


def event_line(seq: int, text: str) -> str:
    return f"[seq {seq}] {text}"


def render_prompt(case: EvalCase, state: AgentState, repeat: int = 0) -> str:
    timeline = "\n".join(event_line(seq, text) for seq, text in visible_events(state))
    return USER_TEMPLATE.format(
        cutoff=case.cutoff,
        timeline=timeline,
        question=case.question,
        choices=", ".join(presented_choices(case, repeat)),
    )


def request_for_state(case: EvalCase, state: AgentState, repeat: int = 0) -> ModelRequest:
    return ModelRequest(system=SYSTEM, messages=(ModelMessage("user", render_prompt(case, state, repeat)),),
                        purpose=PURPOSE)


def request_text(request: ModelRequest) -> str:
    return request.system + "\n" + "\n".join(m.content for m in request.messages)


def post_cutoff_exposure(case: EvalCase, request: ModelRequest) -> int:
    """How many post-cutoff events leave any trace (their text or their ``[seq N]`` marker) in the request."""
    text = request_text(request)
    later = [e for e in case.events if int(e["seq"]) > case.cutoff]
    return sum(1 for e in later if str(e["text"]) in text or f"[seq {int(e['seq'])}]" in text)


def post_cutoff_lines_complete(case: EvalCase, request: ModelRequest) -> int:
    """How many post-cutoff events appear as their exact, complete timeline line in the user message."""
    lines = set(request.messages[0].content.splitlines())
    return sum(1 for e in case.events if int(e["seq"]) > case.cutoff and event_line(int(e["seq"]), str(e["text"])) in lines)


# ---------------------------------------------------------------------- parsing
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def _embedded_objects(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    found = []
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(obj, dict):
            found.append(obj)
    return found


@dataclass(frozen=True)
class ParsedAnswer:
    choice: str | None
    confidence: float | None
    mode: str  # json | fenced | embedded | none | ambiguous


def parse_answer(text: str, choices: tuple[str, ...]) -> ParsedAnswer:
    """Fail-closed parse of the reply (rule: :data:`PARSE_RULE`)."""
    stripped = text.strip()
    data: Any = None
    mode = "none"
    try:
        data, mode = json.loads(stripped), "json"
    except ValueError:
        m = _FENCE.match(stripped)
        if m:
            try:
                data, mode = json.loads(m.group(1)), "fenced"
            except ValueError:
                data = None
        if data is None:
            objs = [o for o in _embedded_objects(stripped) if "choice" in o]
            if objs:
                distinct = {json.dumps(o.get("choice"), sort_keys=True) for o in objs}
                if len(distinct) > 1:
                    return ParsedAnswer(None, None, "ambiguous")
                data, mode = objs[0], "embedded"
    if not isinstance(data, dict):
        return ParsedAnswer(None, None, "none" if data is None else mode)
    choice = data.get("choice")
    choice = choice.strip() if isinstance(choice, str) else None
    if choice not in choices:
        choice = None
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        confidence = None
    else:
        confidence = float(confidence)
    return ParsedAnswer(choice, confidence, mode)


# ---------------------------------------------------------------------- backend
class GatewayBackend:
    """``CognitiveBackend`` over the harness model gateway (experiment adapter, not part of the core package).

    It renders whatever explicit state it is handed into one request and parses the reply. It is not told
    which experimental condition it serves. ``repeat`` only selects the counterbalanced choice order.
    """

    def __init__(
        self, service: CompletionService, case: EvalCase, *, repeat: int = 0, timeout_s: float = DEFAULT_TIMEOUT_S
    ) -> None:
        self.service = service
        self.case = case
        self.repeat = repeat
        self.timeout_s = timeout_s

    def reason(self, state: AgentState, task: str, budget: int) -> RunResult:
        if task != self.case.question:
            raise ValueError("task does not match the case question")
        request = request_for_state(self.case, state, self.repeat)
        response, meter = self.service.complete(request, max_output_tokens=None, timeout_s=self.timeout_s)
        parsed = parse_answer(response.text, self.case.choices)
        return RunResult(
            answer={
                "choice": parsed.choice,
                "confidence": parsed.confidence,
                "parse_mode": parsed.mode,
                "raw": response.text,
                "served_model": response.model,
                "stop_reason": response.stop_reason,
            },
            state=state,
            trace=(f"events_in_input={[seq for seq, _ in visible_events(state)]}",),
            cost=dict(meter),
        )


# ------------------------------------------------------------------ evaluation
@dataclass
class CaseResult:
    case_id: str
    condition: str
    repeat: int
    order_in_pair: int
    correct_at_cutoff: str
    later_answer: str
    presented_choices: list[str]
    choice: str | None
    confidence: float | None
    parse_mode: str | None
    correct: bool
    hindsight_leak: bool
    truncated: bool
    raw: str | None
    error: str | None
    fatal: bool
    attempts: list[dict[str, Any]]
    meter: dict[str, Any]
    branch: dict[str, Any]
    prompt: str
    prompt_chars: int
    served_model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_transient(exc: BaseException) -> bool:
    """A provider fault where no model reply was received and a retry cannot favour either condition."""
    return (
        isinstance(exc, ProviderError)
        and not isinstance(exc, ProviderUnavailable)
        and "timed out" not in str(exc)
        and bool(_TRANSIENT.search(str(exc)))
    )


def evaluate_one(
    service: CompletionService,
    case: EvalCase,
    condition: str,
    *,
    repeat: int = 0,
    order_in_pair: int = 0,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    sleep: Callable[[float], None] = time.sleep,
    should_stop: Callable[[], str | None] | None = None,
) -> CaseResult:
    """One scored model call for one case under one condition, through snapshot -> fork -> run."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}")
    capability = TemporalMultiplicity(GatewayBackend(service, case, repeat=repeat, timeout_s=timeout_s))
    root = capability.snapshot(state_for_case(case))
    branch = capability.fork(root, epistemic_cutoff=case.cutoff if condition == "isolated" else None)
    branch_state = capability.branch_state(branch)
    kernel_branch = capability.kernel.get_branch(branch.branch_id)

    # Validity checks on the exact request the backend will build, before any model call.
    request = request_for_state(case, branch_state, repeat)
    exposure = post_cutoff_exposure(case, request)
    complete_lines = post_cutoff_lines_complete(case, request)
    n_later = len(case.post_cutoff_texts())
    if condition == "isolated" and exposure:
        raise ExperimentInvalid(f"isolation breach: {exposure} post-cutoff event(s) in the isolated input ({case.id})")
    if condition == "baseline" and complete_lines != n_later:
        raise ExperimentInvalid(f"baseline input lacks complete post-cutoff events ({case.id}: {complete_lines}/{n_later})")
    # The manipulation is the only difference: the isolated input is the full-state input minus the post-cutoff lines.
    full = request_for_state(case, state_for_case(case), repeat)
    later_lines = {event_line(int(e["seq"]), str(e["text"])) for e in case.events if int(e["seq"]) > case.cutoff}
    expected = [ln for ln in full.messages[0].content.splitlines() if ln not in later_lines]
    if request.system != full.system or request.messages[0].content.splitlines() != (
        expected if condition == "isolated" else full.messages[0].content.splitlines()
    ):
        raise ExperimentInvalid(f"{condition} input differs from the full-state input by more than the cutoff ({case.id})")

    prompt = request.messages[0].content
    branch_info = {
        "root_state_id": root,
        "parent_state_id": kernel_branch.parent_state_id,
        "branch_state_id": kernel_branch.root_state_id,
        "epistemic_cutoff": kernel_branch.epistemic_cutoff,
        "state_seq": branch_state.seq,
        "events_in_input": [seq for seq, _ in visible_events(branch_state)],
        "post_cutoff_events_in_input": exposure,
        "post_cutoff_lines_complete": complete_lines,
    }
    common = dict(
        case_id=case.id,
        condition=condition,
        repeat=repeat,
        order_in_pair=order_in_pair,
        correct_at_cutoff=case.correct_at_cutoff,
        later_answer=case.later_answer,
        presented_choices=list(presented_choices(case, repeat)),
        branch=branch_info,
        prompt=prompt,
        prompt_chars=len(request.system) + len(prompt),
    )
    attempts: list[dict[str, Any]] = []
    for attempt in range(1 + TRANSIENT_RETRIES):
        try:
            run = capability.run(branch, case.question)
            break
        except ToolError as exc:  # ProviderError is a ToolError; any other ToolError is a configuration fault
            meter = dict(getattr(exc, "meter", None) or {})
            attempts.append({"error": str(exc), "meter": meter})
            stopped = should_stop() if should_stop is not None else None
            if is_transient(exc) and attempt < TRANSIENT_RETRIES and not stopped:
                sleep(TRANSIENT_BACKOFF_S * (attempt + 1))
                continue
            return CaseResult(
                **common,
                choice=None, confidence=None, parse_mode=None, correct=False, hindsight_leak=False,
                truncated=bool(_OVER_LENGTH.search(str(exc))),
                raw=None, error=str(exc),
                fatal=isinstance(exc, ProviderUnavailable) or not isinstance(exc, ProviderError),
                attempts=attempts, meter=meter,
            )
    answer = run.result.answer
    meter = dict(run.result.cost or {})
    choice = answer["choice"]
    return CaseResult(
        **common,
        choice=choice,
        confidence=answer["confidence"],
        parse_mode=answer["parse_mode"],
        correct=choice == case.correct_at_cutoff,
        hindsight_leak=choice == case.later_answer and case.later_answer != case.correct_at_cutoff,
        truncated=answer.get("stop_reason") == "max_tokens" or meter.get("stop_reason") == "max_tokens",
        raw=answer["raw"],
        error=None,
        fatal=False,
        attempts=attempts,
        meter=meter,
        served_model=answer.get("served_model"),
    )


@dataclass
class ExperimentRun:
    results: list[CaseResult] = field(default_factory=list)
    stopped_reason: str | None = None

    @property
    def complete(self) -> bool:
        return self.stopped_reason is None


def schedule(cases: list[EvalCase], repeats: int) -> list[tuple[int, EvalCase, tuple[str, str]]]:
    """Call order: per repeat, per case, both conditions; which condition goes first alternates by
    (case index + repeat) parity. (Choice order depends on the repeat only, so the two are not aliased.)"""
    out = []
    for repeat in range(repeats):
        for i, case in enumerate(cases):
            order = CONDITIONS if (i + repeat) % 2 == 0 else tuple(reversed(CONDITIONS))
            out.append((repeat, case, order))
    return out


def run_experiment(
    service: CompletionService,
    cases: list[EvalCase],
    *,
    repeats: int = PROTOCOL_REPEATS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    on_result: Callable[[CaseResult], None] | None = None,
    should_stop: Callable[[], str | None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ExperimentRun:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    run = ExperimentRun()
    for repeat, case, order in schedule(cases, repeats):
        for position, condition in enumerate(order):
            row = evaluate_one(service, case, condition, repeat=repeat, order_in_pair=position, timeout_s=timeout_s,
                               sleep=sleep, should_stop=should_stop)
            run.results.append(row)
            if on_result is not None:
                on_result(row)
            if row.fatal:
                run.stopped_reason = f"fatal error: {row.error}"
                return run
            reason = should_stop() if should_stop is not None else None
            if reason:
                run.stopped_reason = reason
                return run
    return run


# --------------------------------------------------------------- run metadata
TRANSPORT_FILES = ("harness/llm.py", "harness/model/gateway.py", "harness/model/claude_cli.py",
                   "harness/model/anthropic_backend.py")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def code_info() -> dict[str, Any]:
    core = sorted((REPO_ROOT / "src" / "multiplicity").glob("*.py"))
    core_digest = hashlib.sha256()
    for path in core:
        core_digest.update(path.name.encode())
        core_digest.update(path.read_bytes())
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    src = REPO_ROOT / "src"
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": None if dirty is None else bool(dirty),
        "hindsight_eval_sha256": _sha256_file(Path(__file__)),
        "hindsight_analysis_sha256": _sha256_file(Path(hindsight_analysis.__file__)),
        "multiplicity_core_sha256": core_digest.hexdigest(),
        "transport_sha256": {f: _sha256_file(src / f) for f in TRANSPORT_FILES if (src / f).exists()},
    }


def dataset_info(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        shown = str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        shown = str(path)
    return {
        "path": shown,
        "sha256": _sha256_file(path),
        "schema_version": data.get("schema_version"),
        "n_cases": len(data.get("cases") or []),
    }


def protocol_info(repeats: int, timeout_s: float) -> dict[str, Any]:
    return {
        "system_prompt": SYSTEM,
        "system_prompt_sha256": _sha256_text(SYSTEM),
        "user_template": USER_TEMPLATE,
        "user_template_sha256": _sha256_text(USER_TEMPLATE),
        "choice_order": CHOICE_ORDER_RULE,
        "conditions": list(CONDITIONS),
        "condition_difference": "isolated input = baseline input minus the post-cutoff events (kernel fork)",
        "repeats": repeats,
        "registered_repeats": PROTOCOL_REPEATS,
        "call_order": "per repeat, per case; the first condition alternates by (case index + repeat) parity",
        "max_output_tokens_per_call": None,  # filled from the gateway once it exists
        "output_cap_enforced_per_call": None,
        "timeout_s": timeout_s,
        "transient_retries": TRANSIENT_RETRIES,
        "parse_rule": PARSE_RULE,
        "parse_rule_sha256": _sha256_text(PARSE_RULE),
        "verdict_thresholds": dict(hindsight_analysis.THRESHOLDS),
    }


def recorded_env(environ: Mapping[str, str]) -> dict[str, Any]:
    """Non-secret operator settings that change the model's thinking, plus whether API routing is overridden."""
    out: dict[str, Any] = {k: environ[k] for k in sorted(environ) if _RECORDED_ENV.match(k)}
    out["ANTHROPIC_BASE_URL_set"] = bool(environ.get("ANTHROPIC_BASE_URL"))
    return out


def default_output(settings: ModelSettings, repeats: int) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model = re.sub(r"[^A-Za-z0-9.-]+", "-", settings.name or "model")
    name = f"{EXPERIMENT_ID}-{PROTOCOL_VERSION}-{settings.provider}-{model}-{settings.effort or 'default'}-r{repeats}-{stamp}.json"
    return REPO_ROOT / "results" / "temporal-multiplicity" / name


def _claim(path: Path) -> None:
    """Create the result file exclusively, so an existing result is never overwritten (raises FileExistsError)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".partial", dir=path.parent)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def preflight(settings: ModelSettings, environ: Mapping[str, str]) -> dict[str, Any]:
    """One tiny claude-cli call (login, model, @file mentions disabled) before the run."""
    from harness.model.claude_cli import ClaudeCliBackend

    backend = ClaudeCliBackend(environ=environ)
    try:
        return backend.check(settings)
    finally:
        backend.close()


class _Terminated(KeyboardInterrupt):
    """SIGTERM/SIGHUP, turned into the interrupt path so the result file is finalised and children are killed."""


def _install_signal_handlers() -> dict[int, Any]:
    previous = {}

    def handler(signum, frame):  # noqa: ARG001
        raise _Terminated(f"signal {signum}")

    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)):
        if sig is None:
            continue
        try:
            if signal.getsignal(sig) is signal.SIG_IGN:  # e.g. started under nohup: keep ignoring it
                continue
            previous[sig] = signal.signal(sig, handler)
        except (ValueError, OSError):  # not in the main thread, or unsupported
            pass
    return previous


def _restore_signal_handlers(previous: Mapping[int, Any]) -> None:
    for sig, old in previous.items():
        try:
            signal.signal(sig, old)
        except (ValueError, OSError):
            pass


# -------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="tmk-hindsight: mechanically isolated past state vs full history with instructions."
    )
    parser.add_argument("--provider", choices=["anthropic", "claude-cli"])
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--repeats", type=int, default=PROTOCOL_REPEATS,
                        help=f"calls per case and condition (registered: {PROTOCOL_REPEATS}; "
                             "any other value is off-protocol and its verdict is INCONCLUSIVE)")
    parser.add_argument("--max-output-tokens", type=int, default=None,
                        help="run-level output cap, identical for both conditions; default: none for claude-cli, "
                             f"{ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS} for anthropic")
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, help="result JSON path (default: a timestamped file in "
                                                     "results/temporal-multiplicity/); never overwritten")
    parser.add_argument("--print-prompts", action="store_true",
                        help="print every request and the isolation check, then exit without calling a model")
    parser.add_argument("--skip-preflight", action="store_true", help="skip the claude-cli preflight call")
    return parser


def settings_from_args(args: argparse.Namespace) -> ModelSettings:
    cap = args.max_output_tokens
    if cap is None and args.provider == "anthropic":
        cap = ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS
    return ModelSettings(provider=args.provider, name=args.model, effort=args.effort, max_output_tokens=cap)


def print_prompts(cases: list[EvalCase], repeats: int) -> int:
    for repeat in range(repeats):
        for case in cases:
            for condition in CONDITIONS:
                capability = TemporalMultiplicity(GatewayBackend(_NoService(), case, repeat=repeat))
                root = capability.snapshot(state_for_case(case))
                branch = capability.fork(root, epistemic_cutoff=case.cutoff if condition == "isolated" else None)
                request = request_for_state(case, capability.branch_state(branch), repeat)
                print(f"===== {case.id} / {condition} / repeat {repeat} (post-cutoff events in input: "
                      f"{post_cutoff_exposure(case, request)}/{len(case.post_cutoff_texts())})")
                print(request.messages[0].content)
    print("===== system prompt (identical in both conditions)")
    print(SYSTEM)
    return 0


class _NoService:
    def complete(self, request, *, max_output_tokens, timeout_s):  # pragma: no cover - never called
        raise RuntimeError("no model in --print-prompts mode")


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    environ = os.environ if environ is None else environ
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if not args.cases.exists():
        parser.error(f"cases file not found: {args.cases} (run from a source checkout with PYTHONPATH=src, "
                     "or an editable install, or pass --cases)")
    cases = load_cases(args.cases)
    if args.print_prompts:
        return print_prompts(cases, args.repeats)
    if not args.provider or not args.model:
        parser.error("--provider and --model are required (unless --print-prompts)")
    inside_claude_code = bool(environ.get("CLAUDECODE"))
    if args.provider == "claude-cli" and inside_claude_code:
        print(
            "refusing to run: CLAUDECODE is set, so this process runs inside a Claude Code session. "
            "Run the claude-cli provider from a normal terminal (see the module docstring).",
            file=sys.stderr,
        )
        return 2

    settings = settings_from_args(args)
    output = args.output or default_output(settings, args.repeats)
    previous_handlers = _install_signal_handlers()
    try:
        try:
            _claim(output)
        except FileExistsError:
            print(f"refusing to overwrite existing result file {output}", file=sys.stderr)
            return 2
        return _run_claimed(args, settings, output, cases, environ, inside_claude_code, argv)
    finally:
        _restore_signal_handlers(previous_handlers)


def _run_claimed(
    args: argparse.Namespace,
    settings: ModelSettings,
    output: Path,
    cases: list[EvalCase],
    environ: Mapping[str, str],
    inside_claude_code: bool,
    argv: list[str] | None,
) -> int:
    """Run the experiment into an output file this process has just created exclusively."""
    payload: dict[str, Any] = {
        "experiment": EXPERIMENT_ID,
        "protocol_version": PROTOCOL_VERSION,
        "status": "running",
        "stopped_reason": None,
        "started_at_utc": _now(),
        "finished_at_utc": None,
        "argv": list(sys.argv[1:] if argv is None else argv),
        "environment": {
            "inside_claude_code": inside_claude_code,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "recorded_env": recorded_env(environ),
        },
        "code": None,
        "dataset": None,
        "protocol": protocol_info(args.repeats, args.timeout_s),
        "model": settings.to_dict(),
        "gateway": None,
        "runtime": None,
        "preflight": None,
        "served_models": [],
        "results": [],
    }

    def save(status: str | None = None) -> None:
        if status is not None:
            payload["status"] = status
        rows = payload["results"]
        payload["served_models"] = sorted({r["served_model"] for r in rows if r.get("served_model")})
        payload["analysis"] = hindsight_analysis.analyze(payload)
        _write_atomic(output, payload)

    gateway = None
    try:
        payload["code"] = code_info()
        payload["dataset"] = dataset_info(args.cases)
        save()
        gateway = create_gateway(settings, environ=environ)
        describe = gateway.describe()
        payload["gateway"] = describe
        payload["runtime"] = gateway.runtime_info()
        payload["protocol"]["max_output_tokens_per_call"] = describe.get("effective_max_output_tokens")
        payload["protocol"]["output_cap_enforced_per_call"] = describe.get("output_cap_enforced_per_call")
        if args.provider == "claude-cli" and not args.skip_preflight:
            try:
                payload["preflight"] = preflight(settings, environ)
            except ToolError as exc:
                payload["preflight"] = {"ok": False, "error": str(exc)}
                payload["stopped_reason"] = f"preflight failed: {exc}"
        if payload["stopped_reason"] is None:
            save()
            service = gateway.lane("multiplicity-hindsight")

            def on_result(row: CaseResult) -> None:
                payload["results"].append(row.to_dict())
                save()
                print(f"[{len(payload['results'])}] {row.case_id} r{row.repeat} {row.condition}: "
                      f"{row.choice if row.error is None else 'ERROR ' + row.error}", file=sys.stderr)

            outcome = run_experiment(
                service,
                cases,
                repeats=args.repeats,
                timeout_s=args.timeout_s,
                on_result=on_result,
                should_stop=lambda: gateway.fatal_error,
            )
            payload["stopped_reason"] = outcome.stopped_reason
    except ExperimentInvalid as exc:
        payload["stopped_reason"] = f"experiment invalid: {exc}"
    except KeyboardInterrupt as exc:
        payload["stopped_reason"] = f"interrupted ({exc})" if isinstance(exc, _Terminated) else "interrupted"
    except BaseException as exc:
        payload["stopped_reason"] = f"crashed: {type(exc).__name__}: {exc}"
        raise
    finally:
        try:
            if gateway is not None:
                gateway.close()
        finally:
            payload["finished_at_utc"] = _now()
            save("complete" if payload["stopped_reason"] is None else "incomplete")

    sys.stdout.write(hindsight_analysis.render_markdown(payload, payload["analysis"]))
    print(f"\nresult file: {output}")
    if payload["stopped_reason"] and payload["stopped_reason"].startswith("experiment invalid"):
        return 3
    return 0 if payload["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
