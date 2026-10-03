from multiplicity import (
    AgentState,
    FactReasoner,
    Mutation,
    TemporalMultiplicityKernel,
)


def current_state():
    state = AgentState(seq=1)
    state = state.with_fact("vibration", "high", known_at=1, source="sensor")
    state = state.with_fact("temperature", "normal", known_at=1, source="sensor")
    state = state.with_seq(3)
    state = state.with_fact(
        "inspection_result",
        "bearing_failure",
        known_at=3,
        source="inspection",
    )
    return state


def test_snapshot_is_content_addressed_and_immutable():
    kernel = TemporalMultiplicityKernel()
    state = current_state()

    first = kernel.snapshot(state)
    second = kernel.snapshot(state)

    assert first.state_id == second.state_id
    assert kernel.get_state(first.state_id) == state


def test_historical_fork_physically_removes_later_knowledge():
    kernel = TemporalMultiplicityKernel()
    current = kernel.snapshot(current_state())

    past = kernel.fork(current.state_id, epistemic_cutoff=1)

    assert past.state.seq == 1
    assert past.state.known_facts() == {
        "vibration": "high",
        "temperature": "normal",
    }
    assert "inspection_result" not in past.state.known_facts()


def test_current_and_historical_forks_reach_different_diagnoses():
    kernel = TemporalMultiplicityKernel()
    current = kernel.snapshot(current_state())

    current_branch = kernel.fork(current.state_id)
    historical_branch = kernel.fork(current.state_id, epistemic_cutoff=1)

    runner = FactReasoner()
    current_run = kernel.run(
        current_branch.branch_id,
        task="diagnose-machine",
        runner=runner,
    )
    historical_run = kernel.run(
        historical_branch.branch_id,
        task="diagnose-machine",
        runner=runner,
    )

    assert current_run.result.answer == "bearing_failure"
    assert historical_run.result.answer == "misalignment"


def test_compare_surfaces_branch_specific_knowledge_and_answers():
    kernel = TemporalMultiplicityKernel()
    current = kernel.snapshot(current_state())
    a = kernel.fork(current.state_id)
    b = kernel.fork(current.state_id, epistemic_cutoff=1)

    runner = FactReasoner()
    kernel.run(a.branch_id, task="diagnose-machine", runner=runner)
    kernel.run(b.branch_id, task="diagnose-machine", runner=runner)

    comparison = kernel.compare(a.branch_id, b.branch_id)

    assert comparison.answers[a.branch_id] == "bearing_failure"
    assert comparison.answers[b.branch_id] == "misalignment"
    assert (
        comparison.knowledge_only[a.branch_id]["inspection_result"]
        == "bearing_failure"
    )
    assert "inspection_result" not in comparison.knowledge_only[b.branch_id]


def test_fork_can_mutate_assumptions_without_changing_parent_snapshot():
    kernel = TemporalMultiplicityKernel()
    parent = kernel.snapshot(current_state())

    fork = kernel.fork(
        parent.state_id,
        mutations=(Mutation("beliefs.vendor_reliable", False),),
    )

    assert dict(fork.state.beliefs)["vendor_reliable"] is False
    assert "vendor_reliable" not in dict(
        kernel.get_state(parent.state_id).beliefs
    )


def test_cutoff_cannot_exceed_parent_time():
    kernel = TemporalMultiplicityKernel()
    parent = kernel.snapshot(current_state())

    try:
        kernel.fork(parent.state_id, epistemic_cutoff=10)
    except ValueError as exc:
        assert "later than parent" in str(exc)
    else:
        raise AssertionError("expected ValueError")
