"""Oracle agent: proves a scenario is solvable and the scorer reaches 1.0.

Built by the evaluator from ground truth. It is never registered as a
contestant and never available through ``harness.agents``.
"""

from __future__ import annotations

from evaluation.ground_truth import GroundTruth
from harness.agent import Agent, AgentEvent, AgentResponse, HistoricalState, ReopenAction
from harness.tools import ToolBox


class OracleAgent(Agent):
    kind = "oracle"
    role = "oracle"

    def __init__(self, gt: GroundTruth, name: str = "oracle") -> None:
        super().__init__(name)
        self._gt = gt

    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse:
        actions = []
        for r in self._gt.reconsiderations:
            if r.trigger_event != event.event_id:
                continue
            for target in r.affected_targets:
                actions.append(
                    ReopenAction(
                        target=target,
                        rationale=f"oracle: {r.id}",
                        evidence=(r.trigger_event,),
                        historical_state=HistoricalState(**{k: v for k, v in r.historical_state.items()}),
                    )
                )
            if r.remediation is None:
                continue
            for op in r.remediation.reference:
                if op["op"] == "write_file":
                    content = self._gt.file_bytes(op["source"]).decode("utf-8")
                    tools.write_file(op["path"], content)
                else:
                    tools.delete_file(op["path"])
        return AgentResponse(actions=actions)

