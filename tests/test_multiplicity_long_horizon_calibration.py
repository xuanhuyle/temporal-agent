"""Calibration generator: pressure levels are reachable and every episode passes the static validator."""

from __future__ import annotations

from multiplicity_experiments import long_horizon_calibration as cal


def test_pressure_levels_validate_and_hit_targets():
    for n, lo, hi in ((27, 0.72, 0.80), (57, 1.48, 1.60), (95, 2.45, 2.58), (153, 3.95, 4.08)):
        for seed in range(5):
            ep = cal.make_episode(f"T{n}", seed, n)  # validate(): schedule, entities, wording, probes, no leakage
            assert lo <= ep["R"] <= hi and cal.simulate_compactions(ep) == cal.COMPACTION_STAGES
            assert len(ep["scored"]) == cal.N_SCORED and len(ep["dev_probes"]) == 2 * cal.N_SCORED
