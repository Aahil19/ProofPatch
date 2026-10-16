"""Produce reviewable guardrail-injection evidence without an API key or Docker."""

import json
from pathlib import Path
from types import SimpleNamespace

from proofpatch.providers import DemoProvider, OpenAIProvider
from proofpatch.workflow import Workflow

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "buggy_stats"
ARTIFACTS = ROOT / "artifacts" / "guardrail-injections"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


class NoCall:
    def __init__(self):
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        raise AssertionError("Budget should have stopped this call")


client = NoCall()
budget_provider = OpenAIProvider(
    "injected-model",
    client=SimpleNamespace(responses=client),
    budget_usd="0.001",
    input_rate="1",
    output_rate="1",
)
budget = Workflow(FIXTURE, ARTIFACTS / "budget", budget_provider, ["tests"]).run()
assert budget.status == "escalated" and "budget cap" in budget.reason
assert client.calls == 0


class Unavailable:
    def __enter__(self):
        raise ConnectionError("injected MCP server unavailable")

    def __exit__(self, *args):
        return False


mcp = Workflow(
    FIXTURE,
    ARTIFACTS / "mcp-outage",
    DemoProvider(),
    ["tests"],
    tool_factory=lambda *_: Unavailable(),
).run()
assert mcp.status == "escalated" and "MCP server unavailable" in mcp.reason

deadline = Workflow(
    FIXTURE, ARTIFACTS / "deadline", DemoProvider(), ["tests"], deadline=0.000001
).run()
assert deadline.status == "escalated" and "deadline" in deadline.reason

summary = {
    "cost_cap": {"status": budget.status, "llm_api_calls": client.calls, "reason": budget.reason},
    "mcp_outage": {"status": mcp.status, "reason": mcp.reason},
    "deadline": {"status": deadline.status, "reason": deadline.reason},
    "notes": "All failures are injected; no live model or external MCP server was called.",
}
(ARTIFACTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
