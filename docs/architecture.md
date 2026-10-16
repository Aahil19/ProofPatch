# ProofPatch architecture

ProofPatch follows the supplied architectural reference: GitHub CI failure context feeds
a LangGraph supervisor, which coordinates investigator, reproducer, and repair specialists.
A separate verification stage decides whether to deliver a review-ready patch or escalate
with evidence. Shared engineering controls apply across the workflow.

## Week 2 integration

The CLI now also accepts a GitHub Actions run URL. GitHub ingestion pins the run attempt
and recorded commit SHA, fetches failed-job logs, and safely extracts a bounded archive.
The supervisor uses an incident-scoped MCP session for `get_ci_logs`, `read_file`,
`run_tests`, and `get_diff`. Each test run executes in a fresh restricted Docker container.
Reproduced failures must match failure IDs in the supplied CI logs. See
[Week 2](week-2.md) for the tool contracts, real integration checks, and isolation boundary.

This implements the GitHub-input and restricted-tool extensions in the original design.

## Week 3 controls

The supervisor now checkpoints application state after every graph node in SQLite and
stores each model attempt before making the API call. An interrupted incident can resume
from the same source, phase, price policy, and scope. Budget reservations block calls
that would exceed the operator-priced cap; transient model and GitHub errors get bounded
retries. A live decision includes local MLflow spans and JSON audit logs. Verification
produces a patch pending human approval; the separate manual GitHub review workflow
exports `approved.patch` only after a reviewer decision. See [Week 3](week-3.md) for
controls, recovery semantics, and limitations.

## Week 1 baseline and extension points

| Reference component | Week 1 implementation | Subsequent implementation or remaining scope |
| --- | --- | --- |
| GitHub CI failure: logs, repo, commit SHA | CLI accepts a local repository and selected pytest targets; records input file hashes and newly collected failure logs | Week 2: ingest a GitHub Actions run URL, retrieve logs and commit SHA, and check out the exact failing revision |
| Supervisor agent | `Workflow.supervisor` routes a LangGraph state graph and ends verified or escalated incidents | Week 3: durable SQLite checkpoint and validated resume |
| Investigator | `OpenAIProvider.investigate` returns a structured diagnosis with suspect files and evidence | Retrieve focused context through restricted MCP tools |
| Reproducer | `Workflow.reproduce` runs the baseline suite, then repeats the exact failing test IDs | Run against a pinned environment in disposable Docker containers |
| Repair agent | `OpenAIProvider.repair` proposes exact-match edits; `apply_proposal` validates paths, matches, patch size, and syntax before writing the disposable copy | Broader repair strategies under the same protected-file policy |
| Verification agent: tests, diff, risk checks | `Workflow.verify` reruns failures and the regression suite; checks test identities and workspace integrity. Diff constraints are enforced before verification | Additional risk checks and isolated execution; current checks are not a security analysis |
| Review-ready patch / human approval | `verified.patch` and reports are produced for manual review; the original checkout is untouched | Week 3: explicit manual approval exports `approved.patch`; PR creation remains manual |
| Escalate to human / failure evidence | Reports preserve the reason, attempted proposals, test logs, and trace; CLI exits nonzero | A GitHub-facing escalation and review workflow |
| Global guardrails / cost caps / audit logging | Call and repair limits, context/output bounds, test timeouts, protected tests/configuration, per-node trace, per-run test commands/results, and returned API usage | Week 3: operator-priced budget reservations, retries, MCP/model audit, MLflow, and checkpoint recovery |

Implementation lives in [`workflow.py`](../src/proofpatch/workflow.py),
[`providers.py`](../src/proofpatch/providers.py),
[`runner.py`](../src/proofpatch/runner.py), and
[`workspace.py`](../src/proofpatch/workspace.py).

## Execution and evidence dependencies

The reference shows the specialists side by side to communicate their distinct roles.
They are not independent tasks that should all run at once: repair needs a diagnosis,
and a diagnosis benefits from a reproduced failure. Week 1 therefore uses this order:

1. **Reproduce:** capture a baseline, identify actual failing test IDs, and confirm they
   fail again without any patch. Insufficient evidence escalates before a model call.
2. **Investigate:** supply the observed failures, log excerpt, and bounded source/test
   context to the investigator; retain the structured diagnosis.
3. **Repair:** use the diagnosis to propose source edits, validate them, and save the diff.
4. **Verify:** rerun the original failures and selected regression suite. Missing tests,
   newly skipped tests, regressions, execution errors, or repository mutations block verification.
5. **Route:** return a review-ready patch when all checks pass. A failed verification can
   trigger one more repair from the original source, with failure feedback. Invalid patches
   and infrastructure/provider errors escalate immediately; two unsuccessful repairs also escalate.

The supervisor controls every transition. Investigation and repair use separate model calls;
the supervisor, reproducer, and verifier use deterministic code. The scripted demo provider
exercises the same graph and real test execution, but does not measure LLM repair ability.

## The decision gate and human handoff

The reference's “Safe?” decision is implemented narrowly as **sufficient reproduction
evidence plus passing checks**. A model's confidence or verbal claim cannot satisfy it.
The tests must fail before the change, pass after it, and preserve the selected regression
suite's test identities and passing outcomes. Protected files cannot be edited through the
proposal interface.

A verified artifact is ready for a human to inspect. Week 3's separate review workflow
records an explicit decision before exporting an approved patch. There is still no
automatic application, PR creation, or merge operation. Escalation
currently means producing a human-readable report and a nonzero exit, not contacting a
developer automatically.

## Controls and limitations

The shared-control layer now includes operator-priced cost reservations and resumable
SQLite checkpoints. Prices supplied by the operator can become stale, so estimated cost
is not a provider invoice. File-copy isolation is not a security sandbox; trusted code
and proposed source execute with the runner's OS permissions.
Week 2's URL path uses Docker; the local execution caveat above applies to the retained
`--trusted-local` mode. Docker's controls and limitations are documented separately.

The [Week 1 acceptance checklist](week-1.md) records the original local baseline;
the newer boundaries are documented in [Week 2](week-2.md) and [Week 3](week-3.md).
