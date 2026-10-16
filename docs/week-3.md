# Week 3: guardrails, recovery, and observability

The default live-model budget is **$0.50 per incident**. Live mode requires the
operator to supply the selected model's current input and output prices in USD per
million tokens. Before every call, ProofPatch reserves the cost of the entire 4,096-token
output allowance and the UTF-8 input bytes plus 8,192 tokens of framing/schema room.
Returned token usage replaces the reservation. Failed calls, missing usage, and calls
interrupted by process death consume the full reservation. If actual usage exceeds the
cap, the incident escalates and makes no further model calls. These are
**operator-priced estimates**; the provider invoice may differ.

Transient connection, timeout, rate-limit, and server errors get at most two retries
with one- and two-second backoffs. Each attempt counts toward the 12-call limit and
budget. GitHub API downloads also retry transport failures and HTTP 429/5xx at most
twice. Malformed model responses and evidence failures stop immediately. OpenAI calls
have a 45-second timeout, pytest stages default to 60 seconds, and the active incident
stops before a new graph step after the 600-second deadline. The two-repair-attempt
limit remains in force.

## Checkpoint recovery

`checkpoints.sqlite` stores application state after every graph node. A separate model
ledger is committed **before** each API call, so a call whose billing is unknown after
a crash cannot regain budget. `trace.jsonl`, `llm-calls.jsonl`, and `mcp-tools.jsonl`
record transitions, call outcomes and costs, and tool durations.

On `--resume`, ProofPatch recreates the disposable working tree from the same source.
If verification was interrupted, it reapplies the saved proposal and checks the diff
against the saved patch. Changed source, model, prices, scope, timeout, or GitHub run ID
block recovery. Completed baseline and reproduction stages are reused. Recovery applies
only to interrupted **running** incidents; an escalated or completed decision is final.
Elapsed active execution counts toward the deadline; time between processes does not.

```bash
proofpatch examples/buggy_stats --provider demo --trusted-local \
  --output artifacts/incident-123
# After an unexpected process interruption, use the same inputs and output:
proofpatch examples/buggy_stats --provider demo --trusted-local \
  --output artifacts/incident-123 --resume
```

For GitHub recovery, manually dispatch **Investigate GitHub failure** with the same URL
and inputs, setting `resume_from_run_id` to the earlier investigation run whose artifact
contains `checkpoints.sqlite`. The workflow downloads that artifact before calling
`--resume`. A missing or mismatched checkpoint fails closed.

## Human approval

Successful test evidence yields `approval.status=pending` and a SHA-256 digest of
`verified.patch`. No `approved.patch` exists until a human decides. The local commands
are `proofpatch approve OUTPUT --actor NAME` and
`proofpatch reject OUTPUT --actor NAME --reason TEXT`. Approval checks the patch digest,
records actor and time in `report.json` and `approval-events.jsonl`, then exports the
approved patch. Protected test/configuration files remain ineligible for edits.

On GitHub, **Review a verified patch (manual)** downloads a successful investigation's
artifact, records the authenticated GitHub actor, and uploads a separate decision
artifact. The investigation cannot approve itself. This gate controls release of the
patch artifact; ProofPatch does not yet create a PR.

## MLflow and failure injection

Normal CLI runs create nested MLflow spans for the incident and every graph node in
`OUTPUT/mlruns`. The pinned MLflow client uses a local file backend for this prototype.
Spans include phase, outcome, execution mode, and resume status; they omit source,
logs, credentials, and prompts. `--no-mlflow` disables spans when using another
collector. The JSON audit remains available either way.

`python scripts/check_guardrails.py` produces escalation artifacts for a blocked model
budget, unavailable MCP server, and elapsed deadline. Tests also inject transient API
timeouts, malformed responses, excessive token usage, interrupted repair and
verification, changed source on resume, and tampered patches. GitHub **Evidence checks**
uploads these reports and runs real Docker/MCP checks without a live model key.

```bash
proofpatch https://github.com/OWNER/REPO/actions/runs/RUN_ID \
  --provider openai --model MODEL_ID \
  --input-price-per-million INPUT_USD \
  --output-price-per-million OUTPUT_USD \
  --budget-usd 0.50 --deadline 600 --output artifacts/incident-123
```

Set `GITHUB_TOKEN` and `OPENAI_API_KEY` using environment variables or a secret manager.
The GitHub manual form accepts the same model and prices. Live repair quality and actual
provider invoices have not been benchmarked here.

Sources: [MLflow manual tracing](https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/manual-tracing),
[MLflow lightweight client](https://www.mlflow.org/docs/latest/genai/tracing/lightweight-sdk/),
[GitHub artifact download](https://github.com/actions/download-artifact).
