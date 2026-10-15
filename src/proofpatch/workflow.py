import json
import tempfile
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from proofpatch.models import Incident, TestRun
from proofpatch.providers import Provider
from proofpatch.runner import LocalRunner
from proofpatch.workspace import apply_proposal, hashes, inventory, restore, writable


class State(TypedDict):
    next: str


def verification_errors(before: TestRun, focused: TestRun, after: TestRun) -> list[str]:
    errors = []
    if not focused.valid or focused.exit_code != 0:
        errors.append("Original failing tests did not all pass")
    if set(focused.collected) != set(before.failures):
        errors.append("Focused test identities changed")
    if any(focused.outcomes.get(test) != "passed" for test in before.failures):
        errors.append("A formerly failing test was skipped, absent, or still failing")
    if not after.valid or after.exit_code != 0:
        errors.append("Regression suite did not pass cleanly")
    if set(before.collected) != set(after.collected):
        errors.append("Regression suite test identities changed")
    required = {test for test, outcome in before.outcomes.items() if outcome != "skipped"}
    if any(after.outcomes.get(test) != "passed" for test in required):
        errors.append("A previously executed test no longer passes")
    return errors


class Workflow:
    def __init__(
        self,
        repository: Path,
        output: Path,
        provider: Provider,
        targets: list[str],
        timeout: float = 60,
        max_attempts: int = 2,
        tool_factory=None,
        ci_context: dict | None = None,
    ):
        self.repository, self.output, self.provider = repository, output, provider
        self.targets, self.timeout, self.max_attempts = targets, timeout, max_attempts
        self.incident = Incident(provider=provider.name, scope=targets)
        self.feedback = ""
        self.context = {}
        self.phase = "reproducer"
        self.tool_factory = tool_factory
        self.ci_context = ci_context
        if tool_factory:
            self.incident.execution = "docker-via-mcp"
        if ci_context:
            self.incident.provenance = {k: v for k, v in ci_context.items() if k != "logs"}

    def _save(self):
        self.incident.usage = self.provider.usage
        if getattr(getattr(self, "runner", None), "image", None):
            self.incident.provenance["runner_image_id"] = self.runner.image
        (self.output / "report.json").write_text(self.incident.model_dump_json(indent=2) + "\n")
        (self.output / "trace.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in self.incident.trace)
        )

    def _node(self, name, function):
        def wrapped(state):
            start = time.monotonic()
            event = {"agent": name, "started_at": datetime.now(UTC).isoformat()}
            try:
                result = function(state)
                event["status"] = "ok"
            except Exception as error:  # noqa: BLE001 - node boundary must persist escalation evidence
                self.incident.status = "escalated"
                self.incident.reason = f"{name}: {type(error).__name__}: {error}"
                result = {"next": "escalate"}
                event["status"] = "error"
                event["error"] = self.incident.reason
            event["duration_s"] = round(time.monotonic() - start, 3)
            event["next"] = result.get("next", "supervisor")
            self.incident.trace.append(event)
            self._save()
            return result

        return wrapped

    def supervisor(self, state):
        if self.incident.status != "running":
            return {"next": "finish"}
        return {"next": self.phase}

    def reproduce(self, state):
        baseline = self.runner.run("baseline", self.targets)
        self.incident.runs.append(baseline)
        if not baseline.valid or not baseline.failures:
            raise ValueError("No valid failing test evidence; inspect baseline logs")
        reproduction = self.runner.run("reproduction", baseline.failures)
        self.incident.runs.append(reproduction)
        if (
            not reproduction.valid
            or set(reproduction.collected) != set(baseline.failures)
            or reproduction.failures != baseline.failures
        ):
            raise ValueError("Original failures could not be reproduced consistently")
        if inventory(self.work) != self.original:
            raise ValueError("Tests mutated repository files during reproduction")
        self.baseline = baseline
        if self.ci_context:
            from proofpatch.github import failed_test_ids

            known = failed_test_ids(self.ci_context, self.ci_context.get("subdir", "."))
            if not set(baseline.failures).issubset(known):
                raise ValueError(
                    "Local failures could not be matched to pytest FAILED entries in the CI logs"
                )
        # Protect discovered test modules too, including custom pytest naming conventions.
        self.allowed.difference_update(test.split("::")[0] for test in baseline.collected)
        source = {
            name: self.runner.read_file(name) if self.tool_factory else data.decode("utf-8")
            for name, data in self.original.items()
            if name in self.allowed
        }
        test_source = {
            name: self.runner.read_file(name) if self.tool_factory else data.decode("utf-8")
            for name, data in self.original.items()
            if name.endswith(".py") and name not in self.allowed
        }
        self.context = {
            "source": source,
            "tests": test_source,
            "failing_tests": baseline.failures,
            "failure_log": (self.output / baseline.log).read_text()[-20_000:],
        }
        if self.tool_factory:
            self.context["ci"] = self.runner.get_ci_logs()
        if len(json.dumps(self.context)) > 100_000:
            raise ValueError("Repository context exceeds Week 1's 100 KB model input limit")
        self.phase = "investigator"
        return {"next": "supervisor"}

    def investigate(self, state):
        self.incident.diagnosis = self.provider.investigate(self.context)
        self.phase = "repair"
        return {"next": "supervisor"}

    def repair(self, state):
        self.incident.attempts += 1
        # Retry from the identical baseline, never stack unverified patches.
        restore(self.work, self.original)
        proposal = self.provider.repair(self.context, self.incident.diagnosis, self.feedback)
        (self.output / f"proposal-{self.incident.attempts}.json").write_text(
            proposal.model_dump_json(indent=2) + "\n"
        )
        patch = apply_proposal(self.work, self.original, proposal, self.allowed)
        if self.tool_factory:
            patch = self.runner.get_diff()
        name = f"attempt-{self.incident.attempts}.patch"
        (self.output / name).write_text(patch)
        self.incident.patch = name
        self.expected = inventory(self.work)
        self.phase = "verifier"
        return {"next": "supervisor"}

    def verify(self, state):
        focused = self.runner.run(
            f"attempt-{self.incident.attempts}-focused", self.baseline.failures
        )
        after = self.runner.run(f"attempt-{self.incident.attempts}-regression", self.targets)
        self.incident.runs.extend([focused, after])
        if inventory(self.work) != self.expected:
            raise ValueError("Repository contents changed during verification")
        errors = verification_errors(self.baseline, focused, after)
        if errors:
            self.feedback = (
                "; ".join(errors) + "\n" + (self.output / after.log).read_text()[-10_000:]
            )
            if self.incident.attempts < self.max_attempts:
                self.phase = "repair"
            else:
                self.incident.status = "escalated"
                self.incident.reason = "Repair attempts exhausted: " + "; ".join(errors)
        else:
            self.incident.status = "verified"
            self.incident.reason = (
                "Reproduced failures passed; selected regression suite retained all tests."
            )
            (self.output / "verified.patch").write_text(
                (self.output / self.incident.patch).read_text()
            )
            self.incident.patch = "verified.patch"
        return {"next": "supervisor"}

    def run(self) -> Incident:
        if not self.repository.is_dir():
            raise ValueError("Repository directory does not exist")
        if self.output == self.repository or self.repository in self.output.parents:
            raise ValueError("Output must be outside the target repository")
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            self.original = inventory(self.repository)
            self.incident.source_sha256 = hashes(self.original)
            self.allowed = {name for name in self.original if writable(name, self.targets)}
            with tempfile.TemporaryDirectory(prefix="proofpatch-") as temp, ExitStack() as stack:
                self.work = Path(temp)
                self.work.chmod(0o755)
                restore(self.work, self.original)
                self.runner = (
                    stack.enter_context(self.tool_factory(self.work, self.output, self.timeout))
                    if self.tool_factory
                    else LocalRunner(self.work, self.output, self.timeout)
                )
                graph = StateGraph(State)
                for name, func in [
                    ("supervisor", self.supervisor),
                    ("reproducer", self.reproduce),
                    ("investigator", self.investigate),
                    ("repair", self.repair),
                    ("verifier", self.verify),
                ]:
                    graph.add_node(name, self._node(name, func))
                graph.add_edge(START, "supervisor")
                graph.add_conditional_edges(
                    "supervisor",
                    lambda s: s["next"],
                    {
                        "reproducer": "reproducer",
                        "investigator": "investigator",
                        "repair": "repair",
                        "verifier": "verifier",
                        "finish": END,
                        "escalate": END,
                    },
                )
                for name in ("reproducer", "investigator", "repair", "verifier"):
                    graph.add_edge(name, "supervisor")
                graph.compile().invoke({"next": "reproducer"}, {"recursion_limit": 30})
        except Exception as error:  # noqa: BLE001 - preserve a report for infrastructure failures
            self.incident.status = "escalated"
            self.incident.reason = f"{type(error).__name__}: {error}"
        self._save()
        self._markdown()
        return self.incident

    def _markdown(self):
        i = self.incident
        lines = [
            f"# ProofPatch — {i.status.upper()}",
            "",
            i.reason,
            "",
            f"Provider: `{i.provider}` · Repair attempts: {i.attempts}",
            "",
            f"Verification scope: selected tests; execution: `{i.execution}`.",
            "",
            "| Stage | Passed | Failed | Skipped | Exit | Seconds |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for run in i.runs:
            counts = [list(run.outcomes.values()).count(x) for x in ("passed", "failed", "skipped")]
            lines.append(
                f"| [{run.label}]({run.log}) | {counts[0]} | {counts[1]} | {counts[2]} "
                f"| {run.exit_code} | {run.duration_s} |"
            )
        lines += [
            "",
            "## Agent trace",
            "",
            *[f"- {e['agent']}: {e['status']} ({e['duration_s']}s)" for e in i.trace],
            "",
        ]
        if i.patch:
            lines += [f"Proposed patch: [{i.patch}]({i.patch})", ""]
        lines += [
            "Machine-readable evidence: [report.json](report.json).",
            "",
            "No dollar-cost claim is made. Live token usage is recorded when returned by the API.",
        ]
        (self.output / "report.md").write_text("\n".join(lines) + "\n")
