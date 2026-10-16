"""Failure injection verifies controls act before unsafe or unaffordable work."""

import shutil
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import mlflow
import pytest

from proofpatch.approval import decide
from proofpatch.guardrails import BudgetExceeded, CostBudget
from proofpatch.models import Diagnosis
from proofpatch.providers import DemoProvider, OpenAIProvider
from proofpatch.workflow import Workflow

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "buggy_stats"


class Responses:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def completed(input_tokens=100, output_tokens=100):
    return SimpleNamespace(
        status="completed",
        usage=SimpleNamespace(
            model_dump=lambda: {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        ),
        output_parsed=Diagnosis(summary="cause", suspect_files=[], evidence=[]),
    )


def provider(responses, **kwargs):
    return OpenAIProvider(
        "operator-priced-model",
        client=SimpleNamespace(responses=responses),
        input_rate="1",
        output_rate="1",
        sleep=lambda _: None,
        **kwargs,
    )


def test_budget_blocks_call_before_api_invocation():
    responses = Responses([completed()])
    subject = provider(responses, budget_usd="0.001")
    with pytest.raises(BudgetExceeded, match="would be exceeded"):
        subject.investigate({"large": "x" * 2000})
    assert responses.calls == 0
    assert subject.usage == []


def test_timeout_retries_twice_and_charges_unknown_attempts():
    responses = Responses([TimeoutError("injected timeout"), TimeoutError("again"), completed()])
    subject = provider(responses)
    assert subject.investigate({}).summary == "cause"
    assert responses.calls == 3
    assert [entry["status"] for entry in subject.usage] == [
        "transient_error",
        "transient_error",
        "completed",
    ]
    assert subject.budget.spent > 0


def test_retry_stops_when_next_reservation_exceeds_cap():
    responses = Responses([TimeoutError("injected timeout"), completed()])
    reservation = CostBudget("1", "1", "1").quote(260, 4096)
    subject = provider(responses, budget_usd=str(reservation * Decimal("1.5")))
    with pytest.raises(BudgetExceeded):
        subject.investigate({})
    assert responses.calls == 1


def test_malformed_model_response_escalates_without_retry():
    responses = Responses(
        [SimpleNamespace(status="completed", usage=None, output_parsed=None), completed()]
    )
    subject = provider(responses)
    with pytest.raises(ValueError, match="unstructured"):
        subject.investigate({})
    assert responses.calls == 1
    assert subject.usage[0]["status"] == "unstructured_response"


def test_wrong_structured_schema_does_not_retry_or_echo_model_text():
    responses = Responses(
        [
            SimpleNamespace(
                status="completed",
                usage=None,
                output_parsed={"summary": "secret-marker", "unexpected": 1},
            ),
            completed(),
        ]
    )
    subject = provider(responses)
    with pytest.raises(ValueError, match="invalid structured output") as error:
        subject.investigate({})
    assert "secret-marker" not in str(error.value)
    assert responses.calls == 1
    assert subject.usage[0]["status"] == "invalid_schema"


def test_excess_actual_token_usage_halts_future_calls():
    responses = Responses([completed(input_tokens=1_000_000), completed()])
    subject = provider(responses)
    with pytest.raises(BudgetExceeded, match="after billing"):
        subject.investigate({})
    assert responses.calls == 1
    assert subject.usage[0]["cost_usd"] > 0.5


def test_unknown_inflight_call_is_charged_on_restore():
    subject = provider(Responses([]))
    subject.restore_usage([{"status": "started", "reserved_usd": 0.25, "call": 1}])
    assert subject.calls == 1
    assert subject.usage[0]["status"] == "unknown_after_restart"
    assert subject.budget.report()["charged_usd"] == 0.25


def test_deadline_prevents_new_agent_step(tmp_path):
    workflow = Workflow(FIXTURE, tmp_path / "out", DemoProvider(), ["tests"], deadline=0.000001)
    result = workflow.run()
    assert result.status == "escalated"
    assert "deadline" in result.reason
    assert result.attempts == 0


def test_resume_after_interrupted_repair_skips_reproduction(tmp_path):
    class Interrupted(DemoProvider):
        def repair(self, context, diagnosis, feedback):
            raise KeyboardInterrupt("injected process interruption")

    output = tmp_path / "out"
    with pytest.raises(KeyboardInterrupt):
        Workflow(FIXTURE, output, Interrupted(), ["tests"]).run()
    result = Workflow(FIXTURE, output, DemoProvider(), ["tests"]).run(resume=True)
    assert result.status == "verified"
    assert result.resumed
    assert [run.label for run in result.runs].count("baseline") == 1


def test_resume_after_interrupted_verifier_restores_exact_patch(tmp_path):
    class Interrupted(Workflow):
        def verify(self, state):
            raise KeyboardInterrupt("injected process interruption")

    output = tmp_path / "out"
    with pytest.raises(KeyboardInterrupt):
        Interrupted(FIXTURE, output, DemoProvider(), ["tests"]).run()
    result = Workflow(FIXTURE, output, DemoProvider(), ["tests"]).run(resume=True)
    assert result.status == "verified", result.reason
    assert result.attempts == 1
    assert [run.label for run in result.runs] == [
        "baseline",
        "reproduction",
        "attempt-1-focused",
        "attempt-1-regression",
    ]


def test_resume_rejects_changed_source_without_overwriting_report(tmp_path):
    class Interrupted(DemoProvider):
        def repair(self, context, diagnosis, feedback):
            raise KeyboardInterrupt("injected process interruption")

    source = shutil.copytree(FIXTURE, tmp_path / "source")
    output = tmp_path / "out"
    with pytest.raises(KeyboardInterrupt):
        Workflow(source, output, Interrupted(), ["tests"]).run()
    (source / "stats.py").write_text((source / "stats.py").read_text() + "\n# changed\n")
    before = (output / "report.json").read_bytes()
    with pytest.raises(ValueError, match="differs from checkpoint"):
        Workflow(source, output, DemoProvider(), ["tests"]).run(resume=True)
    assert (output / "report.json").read_bytes() == before


def test_human_gate_checks_patch_digest_and_records_decision(tmp_path):
    output = tmp_path / "out"
    result = Workflow(FIXTURE, output, DemoProvider(), ["tests"]).run()
    assert result.status == "verified"
    assert result.approval["status"] == "pending"
    assert not (output / "approved.patch").exists()
    approved = decide(output, "reviewer", True)
    assert approved.approval["status"] == "approved"
    assert (output / "approved.patch").read_bytes() == (output / "verified.patch").read_bytes()
    assert "Human approval: approved by reviewer" in (output / "report.md").read_text()
    with pytest.raises(ValueError, match="pending"):
        decide(output, "reviewer", True)


def test_tampered_patch_cannot_pass_human_gate(tmp_path):
    output = tmp_path / "out"
    Workflow(FIXTURE, output, DemoProvider(), ["tests"]).run()
    (output / "verified.patch").write_text("tampered")
    with pytest.raises(ValueError, match="digest"):
        decide(output, "reviewer", True)


def test_rejection_records_reason_without_releasing_patch(tmp_path):
    output = tmp_path / "out"
    Workflow(FIXTURE, output, DemoProvider(), ["tests"]).run()
    with pytest.raises(ValueError, match="reason"):
        decide(output, "reviewer", False)
    rejected = decide(output, "reviewer", False, "evidence is too narrow")
    assert rejected.approval["status"] == "rejected"
    assert not (output / "approved.patch").exists()
    assert "evidence is too narrow" in (output / "approval-events.jsonl").read_text()


def test_mlflow_trace_contains_agent_spans_without_source_text(tmp_path):
    output = tmp_path / "out"
    result = Workflow(FIXTURE, output, DemoProvider(), ["tests"], mlflow_enabled=True).run()
    assert result.status == "verified", result.reason
    traces = mlflow.search_traces(return_type="list", flush=True)
    assert traces
    names = {span.name for span in traces[0].data.spans}
    assert {"incident", "supervisor", "reproducer", "investigator", "repair", "verifier"} <= names
