import json

import pytest

from multiplicity_experiments import hindsight_analysis as ha

R = ha.REGISTERED_REPEATS
CASES = [f"k{i}" for i in range(8)]


def _row(case, condition, choice, *, repeat=0, correct="a", later="b", tokens=(100, 10), error=None):
    return {
        "case_id": case,
        "condition": condition,
        "repeat": repeat,
        "choice": None if error else choice,
        "confidence": 0.9 if choice and not error else None,
        "parse_mode": None if error else ("json" if choice else "none"),
        "correct": (not error) and choice == correct,
        "hindsight_leak": (not error) and choice == later,
        "correct_at_cutoff": correct,
        "later_answer": later,
        "error": error,
        "prompt_chars": 500 if condition == "baseline" else 400,
        "meter": {} if error else {"total_input_tokens": tokens[0], "output_tokens": tokens[1]},
    }


def _payload(outcomes, *, status="complete", repeats=R, n_cases=None, sha=ha.REGISTERED_DATASET_SHA256):
    """outcomes: {case: [(baseline_choice, isolated_choice) per repeat]}; a choice "ERR" is a provider error."""
    rows = []
    for case, reps in outcomes.items():
        for repeat, (base, iso) in enumerate(reps):
            for cond, ch in (("baseline", base), ("isolated", iso)):
                err = "provider error: timed out" if ch == "ERR" else None
                rows.append(_row(case, cond, None if err else ch, repeat=repeat, error=err))
    return {
        "status": status,
        "protocol_version": ha.REGISTERED_PROTOCOL_VERSION,
        "protocol": {"repeats": repeats},
        "dataset": {"sha256": sha, "n_cases": len(outcomes) if n_cases is None else n_cases},
        "results": rows,
    }


def _all(base, iso, cases=CASES):
    return {c: [(base, iso)] * R for c in cases}


def _decision(payload):
    return ha.analyze(payload)["decision"]


def test_sign_test_values():
    assert ha.mcnemar_exact(0, 0)["p_one_sided_isolated_better"] == 1.0
    assert ha.mcnemar_exact(5, 0)["p_one_sided_isolated_better"] == pytest.approx(1 / 32)
    assert ha.mcnemar_exact(4, 0)["p_one_sided_isolated_better"] == pytest.approx(1 / 16)
    assert ha.mcnemar_exact(6, 1)["p_one_sided_isolated_better"] == pytest.approx(8 / 128)
    assert ha.mcnemar_exact(0, 3)["p_two_sided"] == pytest.approx(0.25)


def test_pattern_a_both_perfect_is_no_distinct_advantage_with_ceiling_flag():
    d = _decision(_payload(_all("a", "a")))
    assert d["verdict"] == "NO_DISTINCT_ADVANTAGE"
    assert d["pattern"] == "A_both_correct" and d["ceiling"] is True


def test_pattern_b_leaks_in_five_cases_is_supported_for_next_test():
    out = _all("a", "a")
    for c in CASES[:5]:
        out[c] = [("b", "a")] * R
    d = _decision(_payload(out))
    assert d["verdict"] == "SUPPORTED_FOR_NEXT_TEST"
    assert d["pattern"] == "B_isolated_beats_baseline" and d["b_cases"] == 5 and d["leak_cases"] == 5


def test_leaks_in_two_cases_on_every_repeat_are_not_support():
    # the clustered pattern that the pair-level rule wrongly called SUPPORTED
    out = _all("a", "a")
    for c in CASES[:2]:
        out[c] = [("b", "a")] * R
    d = _decision(_payload(out))
    assert d["b_cases"] == 2 and d["pair_mcnemar_descriptive"]["b"] == 2 * R
    assert d["verdict"] == "INCONCLUSIVE"


def test_one_leaky_case_is_within_the_no_advantage_margin_at_any_repeat_count():
    out = _all("a", "a")
    out["k0"] = [("b", "a")] * R
    assert _decision(_payload(out))["verdict"] == "NO_DISTINCT_ADVANTAGE"


def test_a_single_leak_in_one_repeat_makes_the_case_isolation_better():
    out = _all("a", "a")
    out["k0"] = [("b", "a")] + [("a", "a")] * (R - 1)
    d = _decision(_payload(out))
    assert d["b_cases"] == 1 and d["verdict"] == "NO_DISTINCT_ADVANTAGE"


def test_non_leak_baseline_errors_do_not_support_the_capability():
    out = _all("a", "a")
    for c in CASES[:6]:
        out[c] = [("c", "a")] * R
    d = _decision(_payload(out))
    assert d["b_cases"] == 6 and d["leak_cases"] == 0
    assert d["pattern"] == "mixed_isolated_ahead_without_leaks" and d["verdict"] == "INCONCLUSIVE"


def test_pattern_c_both_fail_is_inconclusive():
    out = _all("a", "a")
    for c in CASES[:4]:
        out[c] = [("b", "b")] * R
    d = _decision(_payload(out))
    assert d["pattern"] == "C_both_fail" and d["verdict"] == "INCONCLUSIVE"


def test_both_failing_with_one_baseline_win_is_not_the_kill_verdict():
    out = _all("b", "b")
    out["k0"] = [("a", "b")] * R
    d = _decision(_payload(out))
    assert d["c_cases"] == 1 and d["verdict"] == "INCONCLUSIVE"


def test_pattern_d_strong_baseline_beats_isolated_is_no_distinct_advantage():
    out = _all("a", "a")
    out["k0"] = [("a", "b")] * R
    d = _decision(_payload(out))
    assert d["pattern"] == "D_baseline_beats_isolated" and d["verdict"] == "NO_DISTINCT_ADVANTAGE"
    out["k1"] = [("a", "b")] * R  # isolated accuracy 0.75, baseline 1.0
    assert _decision(_payload(out))["verdict"] == "NO_DISTINCT_ADVANTAGE"


def test_model_invalid_answers_count_as_wrong_and_errors_are_excluded():
    out = _all("a", "a")
    out["k0"] = [(None, "a")] + [("a", "a")] * (R - 1)  # unparseable baseline reply: wrong, not a leak
    out["k1"] = [("ERR", "a")] + [("a", "a")] * (R - 1)  # provider error: excluded from the score
    payload = _payload(out)
    lines = {c["case_id"]: c for c in ha.analyze(payload)["per_case"]}
    assert lines["k0"]["direction"] == "isolation_better" and lines["k0"]["baseline_leaks"] == 0
    assert lines["k1"]["direction"] == "tie" and lines["k1"]["baseline_scored"] == R - 1
    d = _decision(payload)
    assert d["verdict"] == "NO_DISTINCT_ADVANTAGE"  # 1 net case, within the margin; gates allow 1/16 of each


def test_validity_gates():
    perfect = _all("a", "a")
    assert _decision(_payload(perfect, status="incomplete"))["verdict"] == "INCONCLUSIVE"
    assert _decision(_payload(perfect, repeats=3))["verdict"] == "INCONCLUSIVE"
    assert _decision(_payload(perfect, sha="0" * 64))["verdict"] == "INCONCLUSIVE"
    assert _decision(_payload(perfect, n_cases=9))["verdict"] == "INCONCLUSIVE"
    payload = _payload(perfect)
    payload["protocol_version"] = "v0.0"
    assert _decision(payload)["verdict"] == "INCONCLUSIVE"
    errors = dict(perfect)
    for c in CASES[:3]:
        errors[c] = [("ERR", "a")] + [("a", "a")] * (R - 1)  # 3/16 baseline errors > 12.5%
    d = _decision(_payload(errors))
    assert d["verdict"] == "INCONCLUSIVE" and "error rate" in d["reasons"][0]
    invalid = dict(perfect)
    for c in CASES[:3]:
        invalid[c] = [("a", None)] + [("a", "a")] * (R - 1)
    d = _decision(_payload(invalid))
    assert d["verdict"] == "INCONCLUSIVE" and "model-invalid rate" in d["reasons"][0]


def test_cost_is_the_median_pair_ratio_and_a_tie_at_very_different_cost_is_not_a_kill():
    payload = _payload(_all("a", "a"))
    for r in payload["results"]:
        if r["condition"] == "baseline":
            r["meter"] = {"total_input_tokens": 1000, "output_tokens": 10}
    d = _decision(payload)
    assert d["cost_ratio"] > ha.MAX_COST_RATIO and d["verdict"] == "INCONCLUSIVE"
    # one long baseline call does not move the median
    payload = _payload(_all("a", "a"))
    payload["results"][0]["meter"] = {"total_input_tokens": 100, "output_tokens": 5000}
    assert ha.cost_ratio(payload["results"])["ratio"] == pytest.approx(1.0)


def test_summary_metrics_strata_and_markdown(tmp_path, capsys):
    out = {"k0": [("b", "a")] * R, "k1": [(None, "a")] * R, "k2": [("a", "a")] * R}
    payload = _payload(out)
    s = ha.summarize(payload["results"])
    assert s["baseline"]["n"] == 3 * R and s["baseline"]["valid_structured_answers"] == 2 * R
    assert s["baseline"]["accuracy"] == pytest.approx(1 / 3)
    assert s["baseline"]["hindsight_leak_rate"] == pytest.approx(1 / 3)
    assert s["isolated"]["accuracy"] == 1.0 and s["isolated"]["thinking_tokens_total"] is None
    assert s["baseline"]["input_tokens_total"] == 300 * R and s["isolated"]["output_tokens_total"] == 30 * R
    md = ha.render_markdown(payload)
    assert "| case | baseline | isolated | correct at cutoff | baseline leak? | isolated leak? | direction |" in md
    assert f"| k0 | {', '.join(['b'] * R)} | {', '.join(['a'] * R)} | a | {R}/{R} | 0/{R} | isolation_better |" in md
    assert "| k1 | invalid, invalid | a, a | a | 0/2 | 0/2 | isolation_better |" in md
    assert "Descriptive strata" in md
    path = tmp_path / "r.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert ha.main([str(path)]) == 0
    assert "verdict:" in capsys.readouterr().out


def test_no_scored_cases_is_not_labelled_both_correct():
    out = {c: [("ERR", "ERR")] * R for c in CASES}
    d = _decision(_payload(out))
    assert d["pattern"] == "none_no_scored_cases" and d["verdict"] == "INCONCLUSIVE"


def test_strata_cover_the_registered_cases():
    from multiplicity_experiments.hindsight_eval import load_cases

    ids = {c.id for c in load_cases()}
    for family, groups in ha.STRATA.items():
        members = [i for group in groups.values() for i in group]
        assert sorted(members) == sorted(ids), family


def test_registered_values():
    assert ha.REGISTERED_REPEATS == 2
    assert ha.THRESHOLDS["max_error_rate"] == 0.125
    assert ha.THRESHOLDS["max_model_invalid_rate"] == 0.125
    assert ha.THRESHOLDS["min_isolated_accuracy"] == 0.85
    assert ha.THRESHOLDS["alpha_one_sided_sign_test"] == 0.05
    assert ha.THRESHOLDS["no_advantage_margin_cases"] == 1
    assert ha.THRESHOLDS["max_cost_ratio_median_pair"] == 1.25
