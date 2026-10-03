import json

import pytest

from multiplicity_experiments import hindsight_analysis as ha


def _row(case, condition, choice, *, repeat=0, correct="a", later="b", tokens=(100, 10)):
    return {
        "case_id": case,
        "condition": condition,
        "repeat": repeat,
        "choice": choice,
        "confidence": 0.9 if choice else None,
        "parse_mode": "json" if choice else "none",
        "correct": choice == correct,
        "hindsight_leak": choice == later,
        "correct_at_cutoff": correct,
        "later_answer": later,
        "error": None,
        "prompt_chars": 500 if condition == "baseline" else 400,
        "meter": {"total_input_tokens": tokens[0], "output_tokens": tokens[1]},
    }


def _payload(pairs, status="complete"):
    """pairs: list of (case, baseline_choice, isolated_choice[, repeat])."""
    rows = []
    for p in pairs:
        case, base, iso = p[:3]
        repeat = p[3] if len(p) > 3 else 0
        rows.append(_row(case, "baseline", base, repeat=repeat))
        rows.append(_row(case, "isolated", iso, repeat=repeat))
    return {"status": status, "results": rows}


def _verdict(payload):
    return ha.analyze(payload)["decision"]


def test_mcnemar_exact_values():
    assert ha.mcnemar_exact(0, 0)["p_one_sided_isolated_better"] == 1.0
    assert ha.mcnemar_exact(5, 0)["p_one_sided_isolated_better"] == pytest.approx(1 / 32)
    assert ha.mcnemar_exact(4, 0)["p_one_sided_isolated_better"] == pytest.approx(1 / 16)
    assert ha.mcnemar_exact(6, 1)["p_one_sided_isolated_better"] == pytest.approx(8 / 128)
    assert ha.mcnemar_exact(0, 3)["p_two_sided"] == pytest.approx(0.25)


def test_pattern_a_both_perfect_is_no_distinct_advantage():
    d = _verdict(_payload([(f"k{i}", "a", "a") for i in range(8)]))
    assert d["verdict"] == "NO_DISTINCT_ADVANTAGE"
    assert d["pattern"] == "A_both_correct"


def test_pattern_b_consistent_leaks_across_cases_is_supported_for_next_test():
    pairs = [(f"k{i}", "b", "a") for i in range(5)] + [(f"k{i}", "a", "a") for i in range(5, 8)]
    d = _verdict(_payload(pairs))
    assert d["verdict"] == "SUPPORTED_FOR_NEXT_TEST"
    assert d["pattern"] == "B_isolated_beats_baseline" and d["b"] == 5 and d["b_leak"] == 5


def test_small_isolation_edge_is_inconclusive_not_supported():
    pairs = [("k0", "b", "a"), ("k1", "b", "a")] + [(f"k{i}", "a", "a") for i in range(2, 8)]
    assert _verdict(_payload(pairs))["verdict"] == "INCONCLUSIVE"


def test_one_leak_is_within_the_no_advantage_margin():
    pairs = [("k0", "b", "a")] + [(f"k{i}", "a", "a") for i in range(1, 8)]
    assert _verdict(_payload(pairs))["verdict"] == "NO_DISTINCT_ADVANTAGE"


def test_leaks_from_a_single_case_do_not_support_the_capability():
    pairs = [("k0", "b", "a", r) for r in range(6)] + [(f"k{i}", "a", "a", 0) for i in range(1, 8)]
    d = _verdict(_payload(pairs))
    assert d["b"] == 6 and d["b_distinct_cases"] == 1
    assert d["verdict"] == "INCONCLUSIVE"


def test_non_leak_baseline_errors_alone_do_not_support_the_capability():
    pairs = [(f"k{i}", "c", "a") for i in range(6)] + [("k6", "a", "a"), ("k7", "a", "a")]
    d = _verdict(_payload(pairs))
    assert d["b"] == 6 and d["b_leak"] == 0
    assert d["verdict"] == "INCONCLUSIVE"


def test_pattern_c_both_fail_is_inconclusive():
    pairs = [(f"k{i}", "b", "b") for i in range(4)] + [(f"k{i}", "a", "a") for i in range(4, 8)]
    d = _verdict(_payload(pairs))
    assert d["pattern"] == "C_both_fail" and d["verdict"] == "INCONCLUSIVE"


def test_pattern_d_baseline_beats_isolated_is_no_distinct_advantage():
    pairs = [(f"k{i}", "a", "b") for i in range(3)] + [(f"k{i}", "a", "a") for i in range(3, 8)]
    d = _verdict(_payload(pairs))
    assert d["pattern"] == "D_baseline_beats_isolated" and d["verdict"] == "NO_DISTINCT_ADVANTAGE"


def test_incomplete_run_or_invalid_answers_fail_the_validity_gate():
    perfect = [(f"k{i}", "a", "a") for i in range(8)]
    assert _verdict(_payload(perfect, status="incomplete"))["verdict"] == "INCONCLUSIVE"
    two_invalid = [("k0", None, "a"), ("k1", None, "a")] + perfect[2:]
    d = _verdict(_payload(two_invalid))
    assert d["verdict"] == "INCONCLUSIVE" and "validity gate" in d["reasons"][0]
    one_invalid = [("k0", None, "a")] + perfect[1:]  # 1/8 = 12.5% is within the gate; the pair is excluded
    d = _verdict(_payload(one_invalid))
    assert d["verdict"] == "NO_DISTINCT_ADVANTAGE" and d["pair_categories"]["invalid"] == 1


def test_a_tie_at_very_different_cost_is_not_no_distinct_advantage():
    payload = _payload([(f"k{i}", "a", "a") for i in range(8)])
    for r in payload["results"]:
        if r["condition"] == "baseline":
            r["meter"] = {"total_input_tokens": 1000, "output_tokens": 10}
    d = _verdict(payload)
    assert d["cost_ratio"] > ha.MAX_COST_RATIO and d["verdict"] == "INCONCLUSIVE"


def test_summary_metrics_and_markdown(tmp_path, capsys):
    pairs = [("k0", "b", "a"), ("k1", None, "a"), ("k2", "a", "a")]
    payload = _payload(pairs)
    s = ha.summarize(payload["results"])
    assert s["baseline"]["n"] == 3 and s["baseline"]["valid_structured_answers"] == 2
    assert s["baseline"]["accuracy"] == pytest.approx(1 / 3)
    assert s["baseline"]["hindsight_leak_rate"] == pytest.approx(1 / 3)
    assert s["isolated"]["accuracy"] == 1.0
    assert s["baseline"]["input_tokens_total"] == 300 and s["isolated"]["output_tokens_total"] == 30
    md = ha.render_markdown(payload)
    assert "| case | baseline | isolated | correct at cutoff | baseline leak? | isolated leak? |" in md
    assert "| k0 | b | a | a | 1/1 | 0/1 |" in md
    assert "| k1 | invalid | a | a | 0/1 | 0/1 |" in md
    path = tmp_path / "r.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert ha.main([str(path)]) == 0
    assert "verdict:" in capsys.readouterr().out


def test_thresholds_are_the_pre_registered_values():
    assert ha.THRESHOLDS == {
        "max_invalid_rate": 0.125,
        "min_isolated_accuracy": 0.85,
        "alpha_one_sided": 0.05,
        "min_discordant_cases": 2,
        "no_advantage_margin": 1,
        "max_cost_ratio": 1.25,
    }
