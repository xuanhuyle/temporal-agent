import json
from pathlib import Path

import pytest

from resume_gate import validate_resume


CASES_PATH = Path(__file__).parents[1] / "examples" / "resume_gate" / "public_cases.json"


def _cases():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return data["cases"]


@pytest.mark.parametrize("case", [c for c in _cases() if c["classification"] != "out_of_scope"], ids=lambda c: c["id"])
def test_public_case_expected_verdict(case):
    result = validate_resume(case["checkpoint"], case["current"])
    assert result.verdict.value == case["expected_verdict"]


def test_public_case_corpus_has_multiple_frameworks_and_failure_classes():
    cases = _cases()
    assert len(cases) >= 15
    assert len({case["framework"] for case in cases}) >= 4
    assert {case["classification"] for case in cases} == {
        "caught",
        "partial",
        "not_caught",
        "out_of_scope",
    }


def test_out_of_scope_cases_have_no_checkpoint_to_validate():
    for case in _cases():
        if case["classification"] == "out_of_scope":
            assert case["checkpoint"] is None
            assert case["current"] is None


def test_v0_rules_were_not_extended_for_public_cases():
    """Coverage corpus is observational: every case must fit the existing manifest vocabulary."""
    allowed_checkpoint = {
        "checkpoint_id",
        "created_at",
        "policy_version",
        "runtime",
        "tools",
        "authorities",
        "dependencies",
        "side_effects",
    }
    allowed_current = {
        "now",
        "policy_version",
        "runtime",
        "tools",
        "authorities",
        "dependencies",
    }
    for case in _cases():
        if case["checkpoint"] is None:
            continue
        assert set(case["checkpoint"]) <= allowed_checkpoint
        assert set(case["current"]) <= allowed_current
