"""Contestant isolation: separate worlds, private state, untouched sources."""

from __future__ import annotations

from harness.canonical import tree_hash
from harness.runner import RunConfig, run
from scripted_agents import RecordingAgent, WriterAgent


def test_agents_have_isolated_workspaces_and_state(mini_scenario, runs_dir):
    reader = RecordingAgent("reader")
    result = run(mini_scenario, [WriterAgent("alpha"), WriterAgent("beta"), reader], RunConfig(runs_dir=runs_dir))
    for seq, files in reader.files_at.items():
        assert not any(f.startswith("notes/") for f in files), (seq, files)
    final = result.run_dir / "final_state"
    alpha_notes = sorted(p.name for p in (final / "alpha" / "workspace" / "notes").iterdir())
    beta_notes = sorted(p.name for p in (final / "beta" / "workspace" / "notes").iterdir())
    assert alpha_notes == ["alpha-1.md", "alpha-2.md", "alpha-3.md"]
    assert beta_notes == ["beta-1.md", "beta-2.md", "beta-3.md"]
    assert sorted(p.name for p in (final / "alpha" / "state").iterdir()) == ["memory-1.txt", "memory-2.txt", "memory-3.txt"]
    assert list((final / "reader" / "state").iterdir()) == []
    # The world part of every workspace is identical; only agent edits differ.
    assert tree_hash(final / "reader" / "workspace") != tree_hash(final / "alpha" / "workspace")


def test_state_dir_is_private_and_outside_benchmark(mini_scenario, runs_dir):
    a, b = RecordingAgent("a"), RecordingAgent("b")
    run(mini_scenario, [a, b], RunConfig(runs_dir=runs_dir))
    sa, sb = a.contexts[0].state_dir, b.contexts[0].state_dir
    assert sa != sb
    for d in (sa, sb):
        assert mini_scenario.base_dir not in d.parents
        assert runs_dir not in d.parents
    assert not sa.exists()  # temporary lanes are removed; final state is copied into the run dir


def test_run_leaves_scenario_sources_untouched(mini_scenario, runs_dir):
    before = mini_scenario.compute_content_hashes()
    run(mini_scenario, [WriterAgent("w"), RecordingAgent("r")], RunConfig(runs_dir=runs_dir))
    assert mini_scenario.compute_content_hashes() == before
    mini_scenario.verify()  # still matches the frozen hashes


def test_separate_runs_do_not_share_state(mini_scenario, runs_dir):
    first = RecordingAgent("r")
    run(mini_scenario, [WriterAgent("w"), first], RunConfig(runs_dir=runs_dir))
    second = RecordingAgent("r")
    run(mini_scenario, [second], RunConfig(runs_dir=runs_dir))
    assert first.files_at == second.files_at
