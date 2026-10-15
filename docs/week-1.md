# Week 1 acceptance checklist

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| CLI accepts a failing Python repository | `proofpatch REPOSITORY` | CLI + integration tests |
| Supervisor and focused specialists | LangGraph with five distinct node roles | `trace.jsonl` |
| Investigate real failures | Structured OpenAI diagnosis with logs and source | Provider contract tests; live run pending |
| Generate a proposed fix | Structured exact-match source edits | Per-attempt proposal JSON and patch |
| Reproduce before fixing | Baseline suite plus repeat of failed node IDs | Baseline/reproduction JSON + logs |
| Verify fixes and regressions | Focused rerun + unchanged suite identity | Verifier tests and real subprocess integration |
| Escalate insufficient evidence | Explicit reason and nonzero exit | Missing tests, collection errors, timeout, provider failure tests |
| Multiple deliberately broken tests | Three defects, five failing cases, four passing cases | `examples/buggy_stats` |
| Reproducible GitHub checks | Python 3.11–3.13 matrix, evidence upload | Actions workflow |

## Scope decisions

This is a small-repository prototype, not a deployed autonomous repair service. Only
existing Python source files can be changed; tests and configuration are protected.
The target's input snapshot is hashed, copied, and preserved. Patch validation is atomic:
every edit is validated and every changed file compiles before any file is written.

The offline demo provider has known answers for the bundled fixture. Its pytest runs are
real, but its agent responses are scripted. A verified demo is an integration test of the
workflow, not evidence that an LLM solved an unseen bug. Live mode is separately selectable
and never silently falls back to the demo.

Live model calls require a user-supplied key and explicit model selection. Provider contract
tests use a fake Responses client to verify structured outputs, incomplete/refused responses,
and call limits. They do not demonstrate provider availability or live model repair quality.

## Remaining milestones

Docker sandboxing, arbitrary project dependency provisioning, GitHub Actions URL ingestion,
MCP servers, priced cost reservations, transient retries, resumable checkpoints, MLflow,
PR approval workflows, a web dashboard, and comparative benchmarks are not part of this
Week 1 delivery. Artifact persistence does not imply resumable execution.

## Known evidence limits

- Tests and generated source run locally with user permissions. This cannot defend against
  malicious tests, malicious source patches, forged evidence, or prompt injection on its own.
- Reproduction reduces accidental flaky success but cannot prove deterministic behavior.
- Verification covers only the selected suite and one environment, not all possible regressions.
- Existing skips are allowed; converting any originally executed test into a skip is rejected.
- Test log files may contain project data. Review artifacts before sharing them publicly.
- Repository input is limited to 1,000 files / 10 MB; individual files to 1 MB; model context
  to 100 KB. Test log output is redirected to disk, but a disk quota awaits the Docker runner.
- Original source is never patched automatically. Review the diff before applying it yourself.

