# ProofPatch

[![Week 1 evidence checks](https://github.com/Aahil19/ProofPatch/actions/workflows/ci.yml/badge.svg)](https://github.com/Aahil19/ProofPatch/actions/workflows/ci.yml)

**AI that must show its work before calling a fix verified.**

ProofPatch is a Week 2 prototype for repairing small Python repositories with failing
pytest tests. A LangGraph supervisor routes work through a reproducer, investigator,
repair agent, and deterministic verifier. It produces a reviewable patch and evidence
bundle while leaving the input repository untouched.

> Status: Week 2 implementation. The bundled demo uses scripted agent responses and
> real pytest execution. It demonstrates the reliability pipeline, **not** an LLM repair
> success rate. The OpenAI provider is implemented; live model quality requires a separate
> credentialed run. GitHub Actions URL ingestion, a restricted MCP server, and Docker
> execution are implemented. A dashboard, priced budget caps, and resumable approvals remain planned.

## Paste a GitHub Actions run URL

Open [Actions → Investigate GitHub failure](https://github.com/Aahil19/ProofPatch/actions/workflows/investigate.yml),
choose **Run workflow**, and paste a completed failed run URL. Set the project's subdirectory
(usually `.`), choose `openai`, and supply your model ID. Add `OPENAI_API_KEY` as a repository
Actions secret first. The workflow builds the trusted runner image and uploads the decision,
GitHub provenance, test evidence, tool audit, and proposed patch.

For the bundled fixture, select `demo` and `examples/buggy_stats`; no API key is needed.
[Seeded failure (intentional)](https://github.com/Aahil19/ProofPatch/actions/workflows/seeded-failure.yml)
creates a real failed run and automatically triggers its investigation. That workflow is
supposed to be red; the evidence checks should be green.

From a machine with Docker running:

```bash
python -m pip install -c requirements.lock -e '.[dev]'
docker build -t proofpatch-runner:0.2 docker
# Set GITHUB_TOKEN with read access to Actions and repository contents when required.
# Live mode also requires OPENAI_API_KEY.
proofpatch https://github.com/OWNER/REPO/actions/runs/RUN_ID \
  --provider openai --model YOUR_MODEL_ID --subdir .
```

URL investigations always use **MCP → Docker**. They download the recorded commit SHA,
pin the workflow attempt, fetch failed-job logs, and require reproduced failures to match
pytest failure IDs in those logs. There is no automatic fallback to host execution.
See [Week 2 setup, tool contracts, and limitations](docs/week-2.md).

## Try it

**Entirely on GitHub:** open [Actions → Evidence checks](https://github.com/Aahil19/ProofPatch/actions/workflows/ci.yml),
choose **Run workflow**, then open the run summary. Download the evidence artifact for
any Python version to inspect the before/after logs and verified patch. Ordinary pushes
and pull requests also run this demo automatically.

**Locally:**

Python 3.11–3.13 on Linux or macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c requirements.lock -e '.[dev]'
proofpatch examples/buggy_stats --provider demo --trusted-local
```

To use the same fixture with real MCP transport and Docker locally:

```bash
docker build -t proofpatch-runner:0.2 docker
proofpatch examples/buggy_stats --provider demo --execution docker
```

The demo starts with **5 failed / 4 passed** tests across three seeded bugs. It reproduces
the five failures, proposes a source-only patch, then requires **5/5 focused tests** and
**9/9 regression tests** to pass. Each invocation creates a fresh `artifacts/<id>/` folder.

```text
ProofPatch — VERIFIED
Reproduced failures passed; selected regression suite retained all tests.
Report: .../artifacts/<id>/report.md
```

Read `report.md`, inspect `verified.patch`, and open the stage logs and JSON evidence.
The deliberately broken example stays broken so the demonstration can be repeated.

## Live investigation and repair

To try a real model **on GitHub**, add `OPENAI_API_KEY` as a repository Actions secret
under **Settings → Secrets and variables → Actions**. Then open
[Actions → Live model demo (manual)](https://github.com/Aahil19/ProofPatch/actions/workflows/live-demo.yml),
choose **Run workflow**, and enter your model ID. This uses your API credits, runs against
the bundled fixture, and uploads its evidence even when the incident escalates. It never
runs automatically and does not use the scripted demo provider. The dollar budget cap is
not yet implemented. Never paste the key into an issue, source file, or workflow input.

For a local live run:

Install the target project's dependencies in the same environment first. Use an explicit
model ID supported by your OpenAI account and structured outputs:

```bash
export OPENAI_API_KEY='your-key'  # Prefer your secret manager; never commit a key.
proofpatch /path/to/trusted/python-project \
  --provider openai --model YOUR_MODEL_ID \
  --tests tests --trusted-local --output /path/outside/project/incident-001
```

Live mode sends Python source, Python tests, and failure log excerpts to OpenAI. Review
the repository for sensitive content first. `.env`, key files, common build folders, and
hidden directories are excluded from the copied workspace. This is not a comprehensive
secret scanner. API credentials are excluded from the test subprocess environment.

The investigator returns a structured diagnosis. A separate repair call receives that
diagnosis, source, and evidence, and returns exact-match edits. Only pytest results can
set the incident to `verified`; a model cannot set that status.

## Architecture

The system follows a supervisor-and-specialists architecture: failure context enters the
orchestrator, focused agents gather evidence and propose a patch, and verification gates
the handoff to a human. Dashed connections mark
planned capabilities.

```mermaid
flowchart TD
    CI["GitHub CI failure: logs, repository, commit SHA"] --> S
    CLI["CLI: repository or Actions run URL"] --> S
    S["Supervisor: LangGraph orchestration"]
    S --> I["Investigator: locate the failure"]
    S --> R["Reproducer: rerun failing tests"]
    S --> P["Repair agent: propose a minimal patch"]
    S --- M["Restricted MCP tools: logs, file reads, tests, diff"]
    M --- D["Disposable Docker test containers"]
    I --> V
    R --> V
    P --> V
    V["Verification: tests, diff constraints, integrity checks"] --> G{"Evidence sufficient and checks pass?"}
    G -->|Yes| H["Review-ready patch and evidence: human review"]
    G -->|No: retry available| S
    G -->|No: blocked or attempts exhausted| E["Escalate to human with failure evidence"]
    H -.-> A["Explicit approval before PR creation or application — planned"]
    C["Shared controls: limits, timeouts, protected files, audit trace"] --- S
    B["Priced cost caps and resumable approval gates — planned"] -.-> C
```

The branches describe responsibilities, not concurrent execution. The graph runs
**reproduce → investigate → repair → verify**, returning to the supervisor between steps.
Reproduction comes first so model calls receive observed failures rather than an assumption.
The supervisor, reproducer, and verifier are deterministic nodes. The investigator and
repair agent have distinct model roles.
Unsuccessful verification can route back to repair, with concrete failure feedback and a
fresh copy of the original source; at most two repair attempts are allowed.

See [the architecture and implementation mapping](docs/architecture.md) for component
boundaries, the human handoff, and planned extensions. Passing the gate means the selected
checks passed; it is not a blanket declaration that a patch is safe.

## What “verified” means

All of the following must hold:

1. The selected baseline suite actually executes and contains failing test calls.
2. The same failing node IDs fail again before any patch is applied.
3. Every originally failing test passes after the patch (a skip does not count).
4. The selected full regression suite exits cleanly and retains exactly the same test IDs.
5. Every originally passed or failed test passes; previously skipped tests may remain skipped.
6. Tests, configuration, and other protected files are unchanged; test execution did not
   mutate the copied repository.

Collection errors, missing evidence, empty suites, flaky reproduction, timeouts, provider
errors, invalid patches, and exhausted attempts escalate. “Verified” is scoped to the
selected tests and environment; it is not a proof of general correctness.

## Evidence bundle

| File | Purpose |
| --- | --- |
| `report.md` / `report.json` | Decision, reason, diagnosis, test identities, source hashes, usage |
| `trace.jsonl` | Every agent transition, timestamp, duration, and error |
| `baseline.*` / `reproduction.*` | Before-patch test outcomes and logs |
| `proposal-N.json` / `attempt-N.patch` | Rationale, exact edits, proposed diff for every attempt |
| `attempt-N-focused.*` / `attempt-N-regression.*` | After-patch outcomes and logs |
| `verified.patch` | Created only after all verification gates pass |

Existing evidence directories are never overwritten. Exit codes: `0` verified, `1`
escalated, `2` invalid CLI/configuration. Proposed patches are never automatically applied
to your original checkout, committed, pushed, or submitted as pull requests.

## Run the checks

```bash
ruff check .
ruff format --check .
pytest -q
python scripts/check_demo.py --output artifacts/ci-demo
python scripts/check_escalation.py --output artifacts/ci-escalation
```

GitHub Actions runs these checks on Python 3.11, 3.12, and 3.13, then uploads the actual
demo evidence as a workflow artifact. No API key is needed for CI. See
[the Week 1 acceptance checklist](docs/week-1.md) for scope and limitations.

## Boundaries and roadmap

**Week 1 is trusted-local execution only.** A disposable directory and a subprocess are
not a sandbox. Target tests and proposed Python patches execute with your OS permissions;
do not run this prototype on unknown repositories. The local runner is POSIX-only, has a
per-command timeout, kills its process group on timeout, and disables automatic pytest
plugin loading. Projects requiring external pytest plugins, editable package installation,
services, or special environment variables need further runner support.

For URL ingestion and `--execution docker`, tests run in restricted disposable containers:
no network, non-root user, read-only root/source/support mounts, dropped capabilities,
no-new-privileges, and CPU/memory/PID/tmpfs limits. The Docker socket and API credentials
are never mounted or passed into the test container. Container isolation is not a complete
defense against hostile code or a compromised Docker host; use a disposable runner for
untrusted repositories. The default image contains Python and pytest only; build a reviewed
custom image with additional dependencies when necessary.

The prototype caps live calls at 12, output tokens at 4,096 per call, repair attempts at 2,
and model input context at 100 KB. API errors escalate immediately (SDK retries disabled).
Token usage is recorded, but **the $0.50 budget cap is not yet implemented** and no dollar
cost is inferred. Do not treat call limits as a spending guarantee.

- Week 2 implemented: restricted Docker execution, four MCP tools, GitHub Actions failure ingestion.
- Week 3: priced budget reservations, transient retries, persistence/recovery, approval
  gates for PR creation, MLflow tracing, and broader failure injection.
- Week 4: 30+ unseen seeded cases, single-agent baseline comparison, dashboard, demo video,
  and an honest evaluation report. No 70% repair-rate claim is made today.

## Implementation references

- [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
