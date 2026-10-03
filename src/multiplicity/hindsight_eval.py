from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from harness.agent import ModelSettings
from harness.llm import ModelMessage, ModelRequest, ModelResponse
from harness.model.gateway import create_gateway


DEFAULT_CASES = (
    Path(__file__).parents[2]
    / "experiments"
    / "multiplicity"
    / "hindsight_cases.json"
)

SYSTEM = """You are participating in a controlled historical reasoning evaluation.
Answer the decision question using the decision rule and information that were
available at the stated cutoff. Do not optimize for what later turned out to be
true. Return JSON only with keys choice and confidence. choice must be exactly
one of the supplied choices. confidence must be a number from 0 to 1."""


class CompletionService(Protocol):
    def complete(
        self,
        request: ModelRequest,
        *,
        max_output_tokens: int | None,
        timeout_s: float | None,
    ) -> tuple[ModelResponse, dict[str, Any]]: ...


@dataclass(frozen=True)
class EvalCase:
    id: str
    cutoff: int
    choices: tuple[str, ...]
    correct_at_cutoff: str
    later_answer: str
    question: str
    events: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    condition: str
    choice: str | None
    confidence: float | None
    correct: bool
    hindsight_leak: bool
    raw: str
    meter: dict[str, Any]


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


def render_case(case: EvalCase, condition: str) -> str:
    if condition not in {"baseline", "isolated"}:
        raise ValueError(condition)

    if condition == "baseline":
        visible = case.events
        condition_note = (
            "You can see the complete timeline, including events learned after "
            "the cutoff. Those later events must not influence the answer."
        )
    else:
        visible = tuple(event for event in case.events if int(event["seq"]) <= case.cutoff)
        condition_note = (
            "The timeline has been mechanically cut off. No event learned after "
            "the cutoff is available in this state."
        )

    lines = [
        condition_note,
        f"Cutoff sequence: {case.cutoff}",
        "Timeline:",
    ]
    lines.extend(f"[seq {event['seq']}] {event['text']}" for event in visible)
    lines.extend(
        [
            "",
            f"Question: {case.question}",
            "Choices: " + ", ".join(case.choices),
        ]
    )
    return "\n".join(lines)


def request_for(case: EvalCase, condition: str) -> ModelRequest:
    return ModelRequest(
        system=SYSTEM,
        messages=(ModelMessage("user", render_case(case, condition)),),
        max_output_tokens=128,
        purpose=f"hindsight_{condition}",
    )


def parse_answer(text: str, choices: tuple[str, ...]) -> tuple[str | None, float | None]:
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        return None, None
    choice = data.get("choice")
    if choice not in choices:
        choice = None
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = None
    elif not 0 <= float(confidence) <= 1:
        confidence = None
    else:
        confidence = float(confidence)
    return choice, confidence


def evaluate_one(
    service: CompletionService,
    case: EvalCase,
    condition: str,
) -> CaseResult:
    response, meter = service.complete(
        request_for(case, condition),
        max_output_tokens=128,
        timeout_s=180,
    )
    choice, confidence = parse_answer(response.text, case.choices)
    return CaseResult(
        case_id=case.id,
        condition=condition,
        choice=choice,
        confidence=confidence,
        correct=choice == case.correct_at_cutoff,
        hindsight_leak=(
            choice == case.later_answer
            and case.later_answer != case.correct_at_cutoff
        ),
        raw=response.text,
        meter=meter,
    )


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for condition in ("baseline", "isolated"):
        rows = [row for row in results if row.condition == condition]
        valid = [row for row in rows if row.choice is not None]
        out[condition] = {
            "n": len(rows),
            "valid_json_answers": len(valid),
            "accuracy": (
                sum(row.correct for row in rows) / len(rows) if rows else None
            ),
            "hindsight_leak_rate": (
                sum(row.hindsight_leak for row in rows) / len(rows)
                if rows
                else None
            ),
            "mean_confidence": (
                sum(row.confidence for row in rows if row.confidence is not None)
                / sum(row.confidence is not None for row in rows)
                if any(row.confidence is not None for row in rows)
                else None
            ),
            "reported_input_tokens": sum(
                (row.meter.get("total_input_tokens") or 0) for row in rows
            ),
            "reported_output_tokens": sum(
                (row.meter.get("output_tokens") or 0) for row in rows
            ),
        }
    return out


def run_experiment(
    service: CompletionService,
    cases: list[EvalCase],
) -> tuple[list[CaseResult], dict[str, Any]]:
    results: list[CaseResult] = []
    for case in cases:
        for condition in ("baseline", "isolated"):
            results.append(evaluate_one(service, case, condition))
    return results, summarize(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the first temporal-multiplicity hindsight test."
    )
    parser.add_argument("--provider", choices=["anthropic", "claude-cli"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    settings = ModelSettings(
        provider=args.provider,
        name=args.model,
        effort=args.effort,
        max_output_tokens=128,
    )
    gateway = create_gateway(settings)
    service = gateway.lane("multiplicity-hindsight")

    try:
        results, summary = run_experiment(service, load_cases(args.cases))
    finally:
        gateway.close()

    payload = {
        "experiment": "tmk-hindsight-v0",
        "model": settings.to_dict(),
        "summary": summary,
        "results": [
            {
                "case_id": row.case_id,
                "condition": row.condition,
                "choice": row.choice,
                "confidence": row.confidence,
                "correct": row.correct,
                "hindsight_leak": row.hindsight_leak,
                "raw": row.raw,
                "meter": row.meter,
            }
            for row in results
        ],
    }

    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
