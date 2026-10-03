import json

from harness.llm import ModelResponse
from multiplicity.hindsight_eval import (
    EvalCase,
    load_cases,
    parse_answer,
    render_case,
    run_experiment,
)


class RuleService:
    """Deterministic test double for harness plumbing, not a model baseline."""

    def complete(self, request, *, max_output_tokens, timeout_s):
        text = request.messages[0].content
        if "Cutoff sequence: 2" not in text:
            raise AssertionError("unexpected cutoff")
        if "known next-hour demand forecast exceeds 80" in text:
            choice = "no_scale"
        elif "sanctions match" in text:
            choice = "approve"
        else:
            choice = None

        if choice is None:
            choices_line = next(
                line for line in text.splitlines() if line.startswith("Choices: ")
            )
            choice = choices_line.removeprefix("Choices: ").split(", ")[0]

        response = ModelResponse(
            text=json.dumps({"choice": choice, "confidence": 0.7}),
            stop_reason="end_turn",
            model="rule-service",
            input_tokens=10,
            output_tokens=5,
        )
        return response, {
            "total_input_tokens": 10,
            "output_tokens": 5,
        }


def test_isolated_render_physically_omits_post_cutoff_events():
    case = load_cases()[0]

    baseline = render_case(case, "baseline")
    isolated = render_case(case, "isolated")

    assert "monitoring bug" in baseline
    assert "monitoring bug" not in isolated
    assert "[seq 4]" in baseline
    assert "[seq 4]" not in isolated


def test_baseline_render_keeps_timestamps_and_explicit_cutoff():
    case = load_cases()[0]
    prompt = render_case(case, "baseline")

    assert "Cutoff sequence: 2" in prompt
    assert "[seq 1]" in prompt
    assert "[seq 4]" in prompt
    assert "later events must not influence" in prompt


def test_all_cases_have_post_cutoff_hindsight_pressure():
    cases = load_cases()
    assert len(cases) >= 8
    for case in cases:
        assert case.later_answer != case.correct_at_cutoff
        assert any(int(event["seq"]) > case.cutoff for event in case.events)
        assert case.correct_at_cutoff in case.choices
        assert case.later_answer in case.choices


def test_answer_parser_is_fail_closed():
    assert parse_answer('{"choice":"approve","confidence":0.8}', ("approve", "reject")) == (
        "approve",
        0.8,
    )
    assert parse_answer("approve", ("approve", "reject")) == (None, None)
    assert parse_answer('{"choice":"other","confidence":0.8}', ("approve", "reject")) == (
        None,
        0.8,
    )


def test_experiment_runs_both_conditions_with_same_service():
    case = EvalCase(
        id="simple",
        cutoff=2,
        choices=("approve", "reject"),
        correct_at_cutoff="approve",
        later_answer="reject",
        question="Decision?",
        events=(
            {"seq": 1, "text": "sanctions match means reject."},
            {"seq": 2, "text": "No sanctions match is known."},
            {"seq": 3, "text": "A sanctions match is discovered later."},
        ),
    )

    results, summary = run_experiment(RuleService(), [case])

    assert [r.condition for r in results] == ["baseline", "isolated"]
    assert summary["baseline"]["n"] == 1
    assert summary["isolated"]["n"] == 1
