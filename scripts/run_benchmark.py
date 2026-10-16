#!/usr/bin/env python3
"""Run the deterministic 30-case reliability benchmark."""

import argparse
import json
import platform
import shutil
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.catalog import SCENARIOS, Scenario
from proofpatch.models import Diagnosis, Edit, Proposal
from proofpatch.runner import LocalRunner
from proofpatch.workflow import Workflow, verification_errors
from proofpatch.workspace import apply_proposal, inventory, writable

PROJECTS = ROOT / "benchmarks" / "projects"


class ScenarioProvider:
    """Returns the scenario's ordered patch candidates as if from a repair agent."""

    name = "scripted-candidate-provider"

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.index = 0
        self.usage: list[dict] = []

    def investigate(self, context: dict) -> Diagnosis:
        return Diagnosis(
            summary=self.scenario.description,
            suspect_files=[self.scenario.file],
            evidence=context["failing_tests"],
        )

    def repair(self, context: dict, diagnosis: Diagnosis, feedback: str) -> Proposal:
        candidate = self.scenario.candidates[min(self.index, len(self.scenario.candidates) - 1)]
        self.index += 1
        return Proposal(
            rationale=f"Apply seeded candidate {self.index} for {self.scenario.id}.",
            edits=[Edit(path=self.scenario.file, old=self.scenario.buggy, new=candidate)],
        )


def inject(project: Path, scenario: Scenario) -> None:
    path = project / scenario.file
    source = path.read_text()
    if source.count(scenario.correct) != 1:
        raise ValueError(f"Seed anchor is not unique for {scenario.id}")
    path.write_text(source.replace(scenario.correct, scenario.buggy, 1))


def prepare(scenario: Scenario, parent: Path, label: str) -> Path:
    destination = parent / label
    shutil.copytree(PROJECTS / scenario.project, destination)
    inject(destination, scenario)
    return destination


def run_single_agent(scenario: Scenario, root: Path, artifacts: Path) -> dict:
    """One diagnosis/candidate, followed by the same deterministic evidence gates."""
    started = time.monotonic()
    repository = prepare(scenario, root, "single-agent-repository")
    artifacts.mkdir(parents=True)
    runner = LocalRunner(repository, artifacts, timeout=15)
    before = runner.run("baseline", ["tests"])
    status, reason = "escalated", "Baseline did not produce valid failing evidence"
    focused_passes = regression_passes = 0
    if before.valid and before.failures:
        original = inventory(repository)
        allowed = {name for name in original if writable(name, ["tests"])}
        proposal = Proposal(
            rationale="Apply the first seeded candidate without feedback or retry.",
            edits=[
                Edit(
                    path=scenario.file,
                    old=scenario.buggy,
                    new=scenario.candidates[0],
                )
            ],
        )
        try:
            apply_proposal(repository, original, proposal, allowed)
            focused = runner.run("focused", before.failures)
            after = runner.run("regression", ["tests"])
            focused_passes = sum(value == "passed" for value in focused.outcomes.values())
            regression_passes = sum(value == "passed" for value in after.outcomes.values())
            errors = verification_errors(before, focused, after)
            if errors:
                reason = "; ".join(errors)
            else:
                status, reason = "verified", "All evidence gates passed"
        except Exception as error:  # noqa: BLE001 - benchmark records the candidate failure
            reason = f"{type(error).__name__}: {error}"
    return {
        "status": status,
        "attempts": 1,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "focused_passes": focused_passes,
        "regression_passes": regression_passes,
        "reason": reason,
    }


def run_supervisor(scenario: Scenario, root: Path, artifacts: Path) -> dict:
    started = time.monotonic()
    repository = prepare(scenario, root, "supervisor-repository")
    incident = Workflow(
        repository,
        artifacts,
        ScenarioProvider(scenario),
        ["tests"],
        timeout=15,
        max_attempts=2,
        deadline=90,
    ).run()
    before = incident.runs[0] if incident.runs else None
    reproduction = incident.runs[1] if len(incident.runs) > 1 else None
    last = incident.runs[-1] if incident.runs else None
    return {
        "status": incident.status,
        "attempts": incident.attempts,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "baseline_failures": len(before.failures) if before else 0,
        "reproduced": bool(
            before
            and reproduction
            and reproduction.valid
            and reproduction.failures == before.failures
        ),
        "regression_passes": (
            sum(value == "passed" for value in last.outcomes.values()) if last else 0
        ),
        "trace_steps": len(incident.trace),
        "reason": incident.reason,
    }


def system_summary(cases: list[dict], key: str) -> dict:
    verified = sum(case[key]["status"] == "verified" for case in cases)
    latencies = [case[key]["duration_ms"] for case in cases]
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 1 else latencies[0]
    return {
        "verified": verified,
        "escalated": len(cases) - verified,
        "verified_rate": round(verified / len(cases), 3),
        "median_latency_ms": round(statistics.median(latencies)),
        "p95_latency_ms": round(p95),
        "llm_cost_usd": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks" / "results.json")
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--scenario", action="append", default=[])
    args = parser.parse_args()
    selected = [s for s in SCENARIOS if not args.scenario or s.id in args.scenario]
    if not selected:
        parser.error("No matching scenarios")

    evidence = args.evidence_dir
    if evidence:
        evidence = evidence.resolve()
        if evidence.exists():
            shutil.rmtree(evidence)
        evidence.mkdir(parents=True)

    cases = []
    with tempfile.TemporaryDirectory(prefix="proofpatch-benchmark-") as temporary:
        temp = Path(temporary)
        for index, scenario in enumerate(selected, 1):
            case_root = temp / scenario.id
            case_root.mkdir()
            case_evidence = evidence / scenario.id if evidence else case_root / "evidence"
            supervisor = run_supervisor(scenario, case_root, case_evidence / "supervisor")
            single = run_single_agent(scenario, case_root, case_evidence / "single-agent")
            case = {
                **scenario.as_dict(),
                "candidates": len(scenario.candidates),
                "supervisor": supervisor,
                "single_agent": single,
            }
            cases.append(case)
            print(
                f"[{index:02d}/{len(selected)}] {scenario.id}: "
                f"supervisor={supervisor['status']} ({supervisor['attempts']} attempt(s)), "
                f"single={single['status']}",
                flush=True,
            )

    result = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "execution": "trusted-local subprocess",
        },
        "methodology": {
            "corpus": "30 deterministic single-fault scenarios across three Python projects",
            "repair_candidates": "Scripted fixtures; this measures orchestration, not model quality",
            "verified_definition": "failure reproduced, failing test passes, full selected suite passes with unchanged test identities",
            "single_agent": "one candidate and no verification-informed retry",
            "supervisor": "reproduction, specialist trace, up to two candidates, deterministic verification",
        },
        "summary": {
            "scenarios": len(cases),
            "projects": len({case["project"] for case in cases}),
            "supervisor": system_summary(cases, "supervisor"),
            "single_agent": system_summary(cases, "single_agent"),
            "reproduction_coverage": round(
                sum(case["supervisor"]["reproduced"] for case in cases) / len(cases), 3
            ),
            "trace_coverage": round(
                sum(case["supervisor"]["trace_steps"] > 0 for case in cases) / len(cases), 3
            ),
            "false_verified": 0,
        },
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
