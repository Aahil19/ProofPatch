from pathlib import Path

import pytest

from proofpatch.models import Diagnosis, Edit, Proposal
from proofpatch.providers import DemoProvider
from proofpatch.workflow import Workflow
from proofpatch.workspace import inventory

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "buggy_stats"


def test_real_pytest_failure_to_verified_patch(tmp_path):
    original = inventory(FIXTURE)
    output = tmp_path / "evidence"
    result = Workflow(FIXTURE, output, DemoProvider(), ["tests"]).run()
    assert result.status == "verified", result.reason
    assert len(result.runs[0].failures) == 5
    assert len(result.runs[-1].collected) == 9
    assert set(result.runs[-1].outcomes.values()) == {"passed"}
    assert inventory(FIXTURE) == original
    assert (output / "verified.patch").is_file()
    assert {e["agent"] for e in result.trace} == {
        "supervisor",
        "reproducer",
        "investigator",
        "repair",
        "verifier",
    }


class ScriptedProvider:
    name = "test-scripted"

    def __init__(self, proposals):
        self.proposals = iter(proposals)
        self.usage = []

    def investigate(self, context):
        return Diagnosis(summary="Test diagnosis", suspect_files=["app.py"], evidence=[])

    def repair(self, context, diagnosis, feedback):
        return next(self.proposals)


def repo(tmp_path, source="def value(x):\n    return x + 1\n", test=None):
    target = tmp_path / "repo"
    target.mkdir()
    (target / "app.py").write_text(source)
    (target / "tests").mkdir()
    (target / "tests" / "test_app.py").write_text(
        test
        or (
            "from app import value\n"
            "def test_failure():\n    assert value(0) == 0\n"
            "def test_regression():\n    assert value(1) == 2\n"
        )
    )
    return target


def proposal(new, path="app.py", old="return x + 1"):
    return Proposal(rationale="Test patch", edits=[Edit(path=path, old=old, new=new)])


def test_rejects_regression_then_retries_from_baseline(tmp_path):
    provider = ScriptedProvider([proposal("return x"), proposal("return 0 if x == 0 else x + 1")])
    result = Workflow(repo(tmp_path), tmp_path / "out", provider, ["tests"]).run()
    assert result.status == "verified", result.reason
    assert result.attempts == 2
    assert result.runs[3].failures == ["tests/test_app.py::test_regression"]


def test_exhausted_attempts_escalate(tmp_path):
    result = Workflow(
        repo(tmp_path),
        tmp_path / "out",
        ScriptedProvider([proposal("return x"), proposal("return x")]),
        ["tests"],
    ).run()
    assert result.status == "escalated"
    assert result.attempts == 2
    assert not (tmp_path / "out" / "verified.patch").exists()


def test_protected_test_edit_escalates(tmp_path):
    change = proposal("assert value(0) == 1", "tests/test_app.py", "assert value(0) == 0")
    result = Workflow(repo(tmp_path), tmp_path / "out", ScriptedProvider([change]), ["tests"]).run()
    assert result.status == "escalated"
    assert "Protected" in result.reason


@pytest.mark.parametrize(
    "test,reason",
    [
        ("def test_ok():\n    assert True\n", "No valid failing"),
        ("", "No valid failing"),
        ("import nonexistent_proofpatch_module\n", "No valid failing"),
        ("def test_skip():\n    import pytest\n    pytest.skip('skip')\n", "No valid failing"),
    ],
)
def test_insufficient_baseline_escalates(tmp_path, test, reason):
    target = repo(tmp_path)
    (target / "tests" / "test_app.py").write_text(test)
    result = Workflow(target, tmp_path / "out", ScriptedProvider([]), ["tests"]).run()
    assert result.status == "escalated"
    assert reason in result.reason
    assert result.attempts == 0


def test_timeout_escalates(tmp_path):
    target = repo(tmp_path, test="import time\ndef test_hang():\n    time.sleep(10)\n")
    result = Workflow(target, tmp_path / "out", ScriptedProvider([]), ["tests"], timeout=0.2).run()
    assert result.status == "escalated"
    assert result.runs[0].timed_out


def test_provider_error_produces_report(tmp_path):
    class Broken(ScriptedProvider):
        def investigate(self, context):
            raise TimeoutError("injected API timeout")

    result = Workflow(repo(tmp_path), tmp_path / "out", Broken([]), ["tests"]).run()
    assert result.status == "escalated"
    assert "injected API timeout" in result.reason
    assert (tmp_path / "out" / "report.md").is_file()


def test_will_not_overwrite_existing_evidence(tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(FileExistsError):
        Workflow(FIXTURE, output, DemoProvider(), ["tests"]).run()


def test_custom_named_test_module_is_protected(tmp_path):
    target = repo(tmp_path)
    (target / "tests" / "test_app.py").rename(target / "spec.py")
    (target / "pytest.ini").write_text("[pytest]\npython_files = spec.py\n")
    change = proposal("assert value(0) == 1", "spec.py", "assert value(0) == 0")
    result = Workflow(target, tmp_path / "out", ScriptedProvider([change]), ["."]).run()
    assert result.status == "escalated"
    assert "Protected" in result.reason
