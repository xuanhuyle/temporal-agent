import json

import pytest

from harness.agent import ModelSettings
from harness.llm import ModelResponse
from harness.model.gateway import ProviderError, ProviderUnavailable
from multiplicity import TemporalMultiplicity
from multiplicity_experiments import hindsight_eval as he
from multiplicity_experiments.hindsight_eval import (
    CONDITIONS,
    SYSTEM,
    EvalCase,
    ExperimentInvalid,
    load_cases,
    parse_answer,
    post_cutoff_exposure,
    presented_choices,
    request_for_state,
    run_experiment,
    state_for_case,
)


class SpyService:
    """Deterministic transport double: records every request and answers from a rule of its own.

    It is test plumbing, not a model baseline: it answers the correct-at-cutoff choice unless the request
    contains a post-cutoff event, in which case it answers the later answer (a maximally leaky "model").
    """

    def __init__(self, cases, *, text_for=None):
        self.cases = {c.question: c for c in cases}
        self.requests = []
        self.text_for = text_for

    def complete(self, request, *, max_output_tokens, timeout_s):
        self.requests.append((request, max_output_tokens))
        content = request.messages[0].content
        case = next(c for q, c in self.cases.items() if f"Question: {q}" in content)
        leaky = any(t in content for t in case.post_cutoff_texts())
        choice = case.later_answer if leaky else case.correct_at_cutoff
        text = self.text_for(choice) if self.text_for else json.dumps({"choice": choice, "confidence": 0.7})
        response = ModelResponse(text=text, stop_reason="end_turn", model="spy-model", input_tokens=10,
                                 output_tokens=5)
        return response, {"total_input_tokens": 10 + len(content) // 10, "output_tokens": 5,
                          "request_sha256": "x", "purpose": request.purpose}


def _render(case, condition):
    capability = TemporalMultiplicity(he.GatewayBackend(SpyService([case]), case))
    root = capability.snapshot(state_for_case(case))
    branch = capability.fork(root, epistemic_cutoff=case.cutoff if condition == "isolated" else None)
    return request_for_state(case, capability.branch_state(branch))


# ------------------------------------------------------------------ isolation
def test_isolated_request_physically_omits_every_post_cutoff_event():
    for case in load_cases():
        request = _render(case, "isolated")
        text = request.system + "\n" + request.messages[0].content
        for later in case.post_cutoff_texts():
            assert later not in text
        for event in case.events:
            if int(event["seq"]) > case.cutoff:
                assert f"[seq {int(event['seq'])}]" not in text
        assert post_cutoff_exposure(case, request) == 0


def test_baseline_request_contains_every_event_and_the_explicit_cutoff():
    for case in load_cases():
        content = _render(case, "baseline").messages[0].content
        assert f"Cutoff: seq {case.cutoff}" in content
        for event in case.events:
            assert f"[seq {int(event['seq'])}] {event['text']}" in content


def test_conditions_differ_only_by_the_post_cutoff_event_lines():
    for case in load_cases():
        base, iso = _render(case, "baseline"), _render(case, "isolated")
        assert base.system == iso.system == SYSTEM
        assert base.purpose == iso.purpose
        assert base.max_output_tokens == iso.max_output_tokens is None
        later_lines = {f"[seq {int(e['seq'])}] {e['text']}" for e in case.events if int(e["seq"]) > case.cutoff}
        base_lines = base.messages[0].content.splitlines()
        assert [ln for ln in base_lines if ln not in later_lines] == iso.messages[0].content.splitlines()


def test_system_prompt_states_the_four_baseline_requirements():
    s = SYSTEM.lower()
    assert "justified at the cutoff" in s
    assert "may reveal what was actually true" in s
    assert "later truth must not influence your answer" in s
    assert "rule that was in force at the cutoff" in s


def test_isolated_condition_runs_through_snapshot_fork_and_capability_run(monkeypatch):
    calls = []
    real_fork, real_run = TemporalMultiplicity.fork, TemporalMultiplicity.run

    def fork(self, state_id, *, epistemic_cutoff=None, mutations=()):
        calls.append(("fork", epistemic_cutoff))
        return real_fork(self, state_id, epistemic_cutoff=epistemic_cutoff, mutations=mutations)

    def run(self, branch, task, *, budget=1):
        calls.append(("run", self.branch_state(branch).seq))
        return real_run(self, branch, task, budget=budget)

    monkeypatch.setattr(TemporalMultiplicity, "fork", fork)
    monkeypatch.setattr(TemporalMultiplicity, "run", run)
    case = load_cases()[0]
    service = SpyService([case])
    iso = he.evaluate_one(service, case, "isolated")
    base = he.evaluate_one(service, case, "baseline")
    assert calls == [("fork", case.cutoff), ("run", case.cutoff), ("fork", None), ("run", 4)]
    assert iso.branch["epistemic_cutoff"] == case.cutoff and base.branch["epistemic_cutoff"] is None
    assert iso.branch["events_in_input"] == [1, 2] and base.branch["events_in_input"] == [1, 2, 3, 4]
    assert iso.branch["branch_state_id"] != base.branch["branch_state_id"]
    assert iso.branch["root_state_id"] == base.branch["root_state_id"]
    # what reached the transport for the isolated call has no later event
    iso_request = service.requests[0][0]
    assert post_cutoff_exposure(case, iso_request) == 0


def test_breach_aborts_instead_of_scoring(monkeypatch):
    case = load_cases()[0]
    monkeypatch.setattr(he, "post_cutoff_exposure", lambda case, request: 1)
    with pytest.raises(ExperimentInvalid):
        he.evaluate_one(SpyService([case]), case, "isolated")
    with pytest.raises(ExperimentInvalid):
        he.evaluate_one(SpyService([case]), case, "baseline")


def test_case_state_keeps_everything_in_knowledge_which_the_cutoff_filters():
    for case in load_cases():
        state = state_for_case(case)
        assert state.beliefs == state.context == state.metadata == ()
        assert state.goals == state.commitments == ()
        assert len(state.knowledge) == len(case.events)


# ----------------------------------------------------------- budget and order
def test_no_per_call_output_cap_and_same_budget_for_both_conditions():
    case = load_cases()[0]
    service = SpyService([case])
    run_experiment(service, [case])
    assert [cap for _, cap in service.requests] == [None, None]


def test_cli_settings_do_not_cap_claude_cli_output_by_default():
    args = he.build_parser().parse_args(["--provider", "claude-cli", "--model", "m", "--effort", "high"])
    settings = he.settings_from_args(args)
    assert settings.max_output_tokens is None
    assert settings.effort == "high"


def test_choices_are_presented_sorted_so_position_carries_no_answer():
    cases = load_cases()
    first = [presented_choices(c)[0] == c.correct_at_cutoff for c in cases]
    assert not all(first)
    for case in cases:
        content = _render(case, "isolated").messages[0].content
        assert ("Choices: " + ", ".join(sorted(case.choices))) in content


def test_schedule_alternates_which_condition_goes_first():
    cases = load_cases()[:2]
    order = [o for _, _, o in he.schedule(cases, 2)]
    assert order == [CONDITIONS, CONDITIONS[::-1], CONDITIONS[::-1], CONDITIONS]


# -------------------------------------------------------------------- parsing
def test_answer_parser_is_fail_closed_but_accepts_fenced_json():
    ch = ("approve", "reject")
    assert parse_answer('{"choice":"approve","confidence":0.8}', ch) == he.ParsedAnswer("approve", 0.8, "json")
    assert parse_answer('```json\n{"choice": "reject", "confidence": 0.6}\n```', ch).choice == "reject"
    assert parse_answer('Answer: {"choice": "reject", "confidence": 0.6}', ch).mode == "embedded"
    assert parse_answer("approve", ch).choice is None
    assert parse_answer('{"choice":"other","confidence":0.8}', ch) == he.ParsedAnswer(None, 0.8, "json")
    assert parse_answer('{"choice":"approve","confidence":true}', ch) == he.ParsedAnswer("approve", None, "json")
    assert parse_answer('{"choice":"approve","confidence":1.5}', ch).confidence is None
    two = '{"choice": "approve"} or maybe {"choice": "reject"}'
    assert parse_answer(two, ch) == he.ParsedAnswer(None, None, "ambiguous")
    assert parse_answer('{"choice": " approve "}', ch).choice == "approve"


# ---------------------------------------------------------------- run control
def test_experiment_runs_both_conditions_with_same_service_and_scores_leaks():
    cases = load_cases()
    service = SpyService(cases)
    outcome = run_experiment(service, cases, repeats=2)
    assert outcome.complete
    assert len(outcome.results) == 2 * 2 * len(cases)
    for row in outcome.results:
        if row.condition == "baseline":  # the spy leaks whenever it sees a later event
            assert row.hindsight_leak and not row.correct
        else:
            assert row.correct and not row.hindsight_leak


def test_provider_error_is_recorded_and_the_run_continues():
    cases = load_cases()[:2]

    class Flaky(SpyService):
        def complete(self, request, *, max_output_tokens, timeout_s):
            if len(self.requests) == 0:
                self.requests.append((request, max_output_tokens))
                err = ProviderError("provider error: timed out", usage_unknown=True)
                err.meter = {"failed": True}
                raise err
            return super().complete(request, max_output_tokens=max_output_tokens, timeout_s=timeout_s)

    outcome = run_experiment(Flaky(cases), cases)
    assert outcome.complete and len(outcome.results) == 4
    first = outcome.results[0]
    assert first.error and first.choice is None and not first.correct and first.meter == {"failed": True}


def test_fatal_provider_error_stops_the_run():
    cases = load_cases()[:2]

    class Gone(SpyService):
        def complete(self, request, *, max_output_tokens, timeout_s):
            raise ProviderUnavailable("provider error: usage limit reached")

    outcome = run_experiment(Gone(cases), cases)
    assert not outcome.complete and len(outcome.results) == 1 and outcome.results[0].fatal


# ------------------------------------------------------------------------ CLI
def test_cli_refuses_claude_cli_inside_claude_code(tmp_path, monkeypatch):
    created = []
    monkeypatch.setattr(he, "create_gateway", lambda *a, **k: created.append(1))
    out = tmp_path / "r.json"
    code = he.main(["--provider", "claude-cli", "--model", "m", "--output", str(out)], environ={"CLAUDECODE": "1"})
    assert code == 2 and not created and not out.exists()


def test_cli_never_overwrites_a_result_file(tmp_path, monkeypatch):
    out = tmp_path / "r.json"
    out.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(he, "create_gateway", lambda *a, **k: pytest.fail("must not start"))
    assert he.main(["--provider", "anthropic", "--model", "m", "--output", str(out)], environ={}) == 2
    assert out.read_text(encoding="utf-8") == "{}"


class _Gateway:
    def __init__(self, service):
        self.service = service
        self.fatal_error = None
        self.closed = False

    def describe(self):
        return {"provider": "spy"}

    def runtime_info(self):
        return {}

    def lane(self, name):
        return self.service

    def close(self):
        self.closed = True


def test_cli_writes_a_self_contained_result(tmp_path, monkeypatch):
    cases = load_cases()
    gateway = _Gateway(SpyService(cases))
    monkeypatch.setattr(he, "create_gateway", lambda settings, environ=None: gateway)
    out = tmp_path / "r.json"
    code = he.main(["--provider", "anthropic", "--model", "m", "--repeats", "1", "--output", str(out)], environ={})
    assert code == 0 and gateway.closed
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "complete" and payload["stopped_reason"] is None
    assert payload["protocol_version"] == he.PROTOCOL_VERSION
    assert payload["protocol"]["system_prompt"] == SYSTEM
    assert payload["protocol"]["repeats"] == 1
    assert len(payload["dataset"]["sha256"]) == 64 and payload["dataset"]["n_cases"] == len(cases)
    assert set(payload["code"]) >= {"git_commit", "git_dirty", "hindsight_eval_sha256", "multiplicity_core_sha256"}
    assert payload["environment"]["inside_claude_code"] is False
    assert payload["model"]["provider"] == "anthropic"
    assert len(payload["results"]) == 2 * len(cases)
    row = payload["results"][0]
    assert {"prompt", "raw", "meter", "branch", "choice", "correct", "hindsight_leak"} <= set(row)
    assert payload["served_models"] == ["spy-model"]
    decision = payload["analysis"]["decision"]
    assert decision["verdict"] in ("SUPPORTED_FOR_NEXT_TEST", "NO_DISTINCT_ADVANTAGE", "INCONCLUSIVE")


def test_cli_marks_an_isolation_breach_as_invalid_and_keeps_the_file(tmp_path, monkeypatch):
    cases = load_cases()
    monkeypatch.setattr(he, "create_gateway", lambda settings, environ=None: _Gateway(SpyService(cases)))
    monkeypatch.setattr(he, "post_cutoff_exposure", lambda case, request: 1)
    out = tmp_path / "r.json"
    code = he.main(["--provider", "anthropic", "--model", "m", "--output", str(out)], environ={})
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert code == 3
    assert payload["status"] == "incomplete"
    assert payload["stopped_reason"].startswith("experiment invalid")
    assert payload["analysis"]["decision"]["verdict"] == "INCONCLUSIVE"


def test_print_prompts_makes_no_model_call(capsys, monkeypatch):
    monkeypatch.setattr(he, "create_gateway", lambda *a, **k: pytest.fail("must not call a model"))
    assert he.main(["--print-prompts"], environ={"CLAUDECODE": "1"}) == 0
    out = capsys.readouterr().out
    assert "post-cutoff events in input: 0/2" in out and "post-cutoff events in input: 2/2" in out


def test_all_cases_have_post_cutoff_hindsight_pressure():
    cases = load_cases()
    assert len(cases) >= 8
    for case in cases:
        assert case.later_answer != case.correct_at_cutoff
        assert any(int(event["seq"]) > case.cutoff for event in case.events)
        assert case.correct_at_cutoff in case.choices
        assert case.later_answer in case.choices
        assert len(set(case.choices)) == len(case.choices)
