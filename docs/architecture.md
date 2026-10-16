# Architecture and trust boundaries

ProofPatch separates probabilistic work from deterministic evidence. The model-facing
investigator and repair roles can diagnose and propose; neither role can set an incident's
final status. The verifier alone evaluates pytest evidence, repository integrity, and patch
scope before the supervisor routes the incident to review or escalation.

## Components

| Component | Responsibility | Trust boundary |
| --- | --- | --- |
| Ingestion | Resolve local input or a GitHub Actions URL to an immutable source snapshot and CI context | Remote content is treated as untrusted data |
| Supervisor | Route explicit LangGraph states, attempts, completion, and escalation | Deterministic policy |
| Reproducer | Execute the selected baseline and re-run the exact failing node IDs | Test results must satisfy the evidence schema |
| Investigator | Produce a structured diagnosis from source, tests, and observed failures | Provider output is untrusted until validated |
| Repair agent | Propose up to eight exact-match edits to allowed Python source | Cannot edit tests, config, hidden files, or unknown paths |
| Verifier | Run focused and regression suites; compare test identities and repository inventory | Deterministic gate |
| Review gate | Record an actor decision and export an approved patch | Explicit human action |
| MCP boundary | Offer four restricted tools to GitHub URL investigations | Docker executor owns test and diff operations |

## Execution order

The graph intentionally runs the reproducer before the investigator. Diagnosis then reflects
observed behavior rather than an assumption from a stale CI message. After a failed candidate,
the repair role receives the verifier's test evidence and starts again from the original failing
snapshot. Candidate patches never accumulate.

```text
ingest → reproduce → investigate → repair → verify
                                      ↑         │
                                      └── retry ┘
                                                ├── verified → human review
                                                └── escalated → evidence report
```

## GitHub and Docker path

An Actions run URL is parsed with a strict GitHub URL format and resolved through the GitHub
API. ProofPatch records the repository, commit SHA, workflow attempt, failed-job logs, and
downloaded archive. Fork-origin runs are rejected. The source archive is checked for traversal,
symlinks, excessive file counts, and excessive size before extraction.

The test runner container uses a read-only root filesystem, read-only source and support
mounts, a writable temporary workspace, no network, a non-root UID, dropped Linux capabilities,
`no-new-privileges`, and explicit CPU, memory, process, and tmpfs limits. The Docker socket and
API credentials are never mounted inside the test container.

## Data and persistence

The input checkout is inventoried and copied into a disposable workspace. Every stage appends
machine-readable evidence to the incident directory. SQLite stores graph state and model usage
at stage boundaries, allowing a validated resume when repository hashes and run configuration
still match. MLflow tracing is optional and uses a local file store by default.

The detailed contracts are documented in [integrations](integrations.md),
[reliability controls](reliability.md), and the [evidence model](evidence-model.md).
