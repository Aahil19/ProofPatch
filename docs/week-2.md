# Week 2: GitHub failures through MCP and Docker

## Deliverable

Pass a GitHub Actions run URL to `proofpatch`, or paste it into the **Investigate GitHub
failure** workflow. The pipeline retrieves GitHub's failure context, downloads the recorded
revision, reproduces its Python failures in Docker via MCP, investigates, proposes a patch,
and verifies or escalates using the Week 1 evidence gates.

This release supports small Python/pytest projects on github.com. It does not execute an
arbitrary Actions workflow or automatically reproduce its entire service/dependency environment.

## Run entirely on GitHub

1. Open **Actions → Seeded failure (intentional) → Run workflow** on `main`.
2. The fixture intentionally produces five failures. Its completion triggers **Investigate
   GitHub failure**, using a scripted provider, real GitHub API requests, actual MCP stdio
   transport, and real Docker execution. No OpenAI key is needed for this integration demo.
3. Open the investigation run and download `proofpatch-github-investigation`. Inspect
   `github-incident.json`, `report.json`, `mcp-tools.jsonl`, and `verified.patch`.

For your own run, manually dispatch **Investigate GitHub failure** with the run URL,
project subdirectory, `openai` provider, and model ID. Add an `OPENAI_API_KEY` repository
Actions secret first. This uses your API credits; the dollar budget cap remains Week 3.
The workflow's read-only `GITHUB_TOKEN` can access this repository. Other private repositories
require a separately configured credential with appropriate read access; the default workflow
does not silently grant broader access.

The automatic trigger is limited to the named demonstration workflow, this repository,
and `main`. Controller code is checked out from trusted `main`. The failing revision is
downloaded as data and tested in containers; its installation scripts, Dockerfile, and
Actions workflow are never executed on the host. There is no `pull_request_target` trigger.

## Local invocation

```bash
python -m pip install -c requirements.lock -e '.[dev]'
docker build -t proofpatch-runner:0.2 docker
export GITHUB_TOKEN='your-read-token'  # Prefer your secret manager; never commit it.
export OPENAI_API_KEY='your-api-key'
proofpatch https://github.com/OWNER/REPO/actions/runs/123456 \
  --model YOUR_MODEL_ID --subdir . --tests tests --output artifacts/incident-123456
```

An optional `/attempts/N` suffix selects a particular rerun attempt. Otherwise the current
attempt is resolved once and pinned for job selection. Query strings, alternate hosts,
job URLs, non-failed runs, fork runs, oversized archives, and unsafe archive entries are rejected.
Expired/missing logs, authentication failures, and unsupported reproduction generate an escalation.

The repository archive is requested by the full recorded commit SHA, not the moving branch.
Repository file hashes, run ID, attempt, subdirectory, commit SHA, and immutable Docker image ID
are retained in the report. Reproduced test IDs must match `FAILED ...py::...` entries in CI logs;
unrelated local failures cannot establish that the supplied incident was repaired.

## Restricted MCP tool contract

The official MCP Python SDK's supported v1 line is pinned at `mcp==1.30.0`. Its built-in
FastMCP server exposes exactly four tools over stdio. The graph uses a persistent real MCP
client session; no additional LangChain adapter is required.

| Tool | Inputs | Controls |
| --- | --- | --- |
| `get_ci_logs` | None | Returns only this incident's prefetched GitHub context; no arbitrary URL fetching |
| `read_file` | Repository-relative Python path | Snapshot allowlist, containment/symlink checks, 100 KB per-file cap |
| `run_tests` | Fixed stage label and selected pytest paths/node IDs | Incident test scope, no shell/flags, unique stage labels, at most six runs, Docker only |
| `get_diff` | None | Original snapshot comparison, no added/deleted files, protected-test/config checks, 30 KB cap |

Every tool invocation records its arguments, status, duration, and error in `mcp-tools.jsonl`.
The controller invokes tools at explicit graph steps: source/log reads feed investigation,
pytest runs produce reproduction/verification evidence, and the diff validates the proposed patch.
The model does not receive an unrestricted shell or determine whether verification passed.

The generated `mcp-config.json` is operator-owned session configuration, not repository
configuration. To connect a compatible MCP host to a prepared incident workspace, launch
`proofpatch-mcp --config /absolute/path/to/mcp-config.json`. Do not reuse configuration after
the CLI exits: its disposable workspace has been removed. This server is intentionally not
an unauthenticated HTTP service and is not a multi-tenant sandbox manager.

## Docker execution boundary

Each test run gets a fresh container with networking disabled, UID/GID 65534, read-only root,
read-only source/support bind mounts, all capabilities dropped, no-new-privileges, 512 MB
memory (no extra swap), one CPU, 128 PIDs, limited open files, and a 64 MB temporary filesystem.
No host output directory is writable from inside the container. Evidence is returned as a
bounded JSON envelope through stdout. The host writes the artifacts after parsing it.

The container runs a fixed Python/pytest entry point. It receives neither API credentials nor
the Docker socket. Timeouts forcibly remove the named container; teardown also removes it.
Unavailable Docker or a missing prebuilt image escalates, never falling back to local execution.
The image is resolved to an immutable local image ID before use; runs never implicitly pull images.

The default image is Python 3.12 plus pytest. Dependency provisioning is deliberately explicit:
build a reviewed image from a trusted Dockerfile and pass `--image YOUR_IMAGE`. The CLI will not
install packages from an untrusted repository or copy CI secrets into containers. Projects needing
external pytest plugins, network services, writable source trees, or special environment variables
may escalate until the runner supports them. Container isolation protects the host under normal
Docker assumptions; it cannot guarantee correctness of evidence emitted by malicious test code.

## Validation

### Recorded GitHub evidence

Controller revision `e6b4aa22c1c141258ac98d13f11d4f6245d606df` was validated by
[Evidence checks](https://github.com/Aahil19/ProofPatch/actions/runs/38663516554):
the Python 3.11, 3.12, and 3.13 jobs and the real Docker/MCP job all passed.

The [manual URL investigation](https://github.com/Aahil19/ProofPatch/actions/runs/38663779004)
consumed [this failed run](https://github.com/Aahil19/ProofPatch/actions/runs/38661748932)
at source revision `4d1fa0ed7a0a187028cc13e2881ea6570ad23c23`, with
`subdir=examples/buggy_stats` and `provider=demo`. It completed in 42 seconds including
environment setup, using one repair attempt:

| Stage | Passed | Failed |
| --- | ---: | ---: |
| Baseline | 4 | 5 |
| Reproduction | 0 | 5 |
| Focused verification | 5 | 0 |
| Regression verification | 9 | 0 |

The run uploads `proofpatch-github-investigation`, containing the proposed patch, GitHub
provenance, test evidence, and MCP audit. These results establish the integration path;
the repair responses were scripted and do not measure live model performance.

### Automated coverage

- The normal matrix runs parsing, GitHub API mock tests, archive/path restrictions, real MCP
  handshake/read/diff tests, and the existing evidence-gate tests on Python 3.11–3.13.
- A separate Docker job executes real MCP-to-container repair, verifies non-root/no-network/
  read-only/secret-isolation controls, and checks container removal after timeout.
- The intentionally failed Actions workflow and its follow-on investigation exercise the
  real GitHub API, exact-revision download, logs, MCP transport, Docker tests, and artifacts.
- Scripted responses in the integration demo are explicitly labeled. No live LLM success
  rate or $0.50 budget compliance is claimed.

## Source references

- [Official MCP Python SDK v1 documentation](https://py.sdk.modelcontextprotocol.io/v1/)
- [GitHub workflow runs API](https://docs.github.com/en/rest/actions/workflow-runs)
- [GitHub workflow jobs and logs API](https://docs.github.com/en/rest/actions/workflow-jobs)
- [Docker container runtime controls](https://docs.docker.com/engine/containers/run/)
