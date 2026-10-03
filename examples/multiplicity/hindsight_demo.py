from multiplicity import AgentState, FactReasoner, TemporalMultiplicityKernel


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

kernel = TemporalMultiplicityKernel()
current = kernel.snapshot(state)
now = kernel.fork(current.state_id)
past = kernel.fork(current.state_id, epistemic_cutoff=1)

runner = FactReasoner()
kernel.run(now.branch_id, task="diagnose-machine", runner=runner)
kernel.run(past.branch_id, task="diagnose-machine", runner=runner)

comparison = kernel.compare(now.branch_id, past.branch_id)

print("Current-self answer:", comparison.answers[now.branch_id])
print("Past-self answer:", comparison.answers[past.branch_id])
print("Knowledge only current self:", comparison.knowledge_only[now.branch_id])
print("Knowledge only past self:", comparison.knowledge_only[past.branch_id])
