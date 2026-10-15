import json
from pathlib import Path

from proofpatch.ingest import investigate_run
from proofpatch.providers import DemoProvider
from proofpatch.workflow import Workflow


def test_ingestion_errors_write_escalation_without_running_code(tmp_path):
    class Unavailable:
        def incident(self, run):
            raise ValueError("GitHub HTTP 403")

        def close(self):
            self.closed = True

    api = Unavailable()
    output = tmp_path / "out"
    result = investigate_run(
        "https://github.com/u/r/actions/runs/123", output, DemoProvider(), ["tests"], github=api
    )
    assert result.status == "escalated"
    assert "403" in result.reason
    assert json.loads((output / "report.json").read_text())["attempts"] == 0
    assert api.closed


def test_unrelated_local_failure_cannot_verify_ci_incident(tmp_path):
    root = Path(__file__).resolve().parents[1] / "examples" / "buggy_stats"
    result = Workflow(
        root,
        tmp_path / "out",
        DemoProvider(),
        ["tests"],
        ci_context={"logs": [{"text": "FAILED tests/test_other.py::test_other"}]},
    ).run()
    assert result.status == "escalated"
    assert "matched" in result.reason
    assert result.attempts == 0
