"""External pytest plugin; name must not collide with pytest's builtin 'capture'."""

import json
import os
from pathlib import Path

_data = {"collected": [], "outcomes": {}, "errors": []}


def pytest_collection_finish(session):
    _data["collected"] = [item.nodeid for item in session.items]


def pytest_collectreport(report):
    if report.failed:
        _data["errors"].append(str(report.longrepr))


def pytest_runtest_logreport(report):
    outcomes = _data["outcomes"]
    if report.failed:
        outcomes[report.nodeid] = "failed" if report.when == "call" else "error"
    elif report.skipped and outcomes.get(report.nodeid) not in {"failed", "error"}:
        outcomes[report.nodeid] = "skipped"
    elif report.when == "call" and report.passed:
        outcomes[report.nodeid] = "passed"


def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["PROOFPATCH_EVIDENCE"]).write_text(json.dumps(_data), encoding="utf-8")
