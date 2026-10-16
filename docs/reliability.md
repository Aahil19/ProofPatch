# Guardrails, recovery, approval, and tracing

The reliability controls are executable policy, not instructions in an agent prompt.

## Limits and retries

Live model runs require explicit USD rates per million input and output tokens. ProofPatch
reserves the maximum response cost before each call and blocks a call that could exceed the
incident cap. A completed call is reconciled with returned usage; an interrupted or failed call
keeps its full reservation because it may have been billed.

Default limits are a $0.50 incident budget, 12 model calls, two repair attempts, 4,096 output
tokens per call, two transient application retries with exponential backoff, and a 600-second
active deadline. The OpenAI SDK's automatic retries are disabled so every attempt is visible.

## Durable recovery

`checkpoints.sqlite` stores the incident, graph phase, evidence context, feedback, policy,
elapsed deadline, and append-only model usage after every node. `--resume` is accepted only when
the repository hashes, targets, provider policy, timeout, attempt limit, deadline, and CI run
identity still match. An in-flight call is charged at its reserved amount before execution can
continue.

## Human review

Passing verification creates `verified.patch` and an approval state of `pending`. It does not
create a commit or pull request. The manual review workflow checks the patch digest, records the
GitHub actor, and creates `approved.patch` only for an approval decision. Rejections require a
reason. Review events are append-only JSONL records.

## Observability and failure injection

`trace.jsonl` records every agent transition, route, duration, and error. `llm-calls.jsonl`
records reservations, retries, status, token usage, and cost. `mcp-tools.jsonl` records restricted
tool activity. Optional MLflow spans mirror the incident and agent hierarchy without contacting
a remote tracking service by default.

The CI failure-injection job exercises budget refusal, malformed or unavailable dependencies,
MCP outages, and deadline behavior without an API key. Each case must stop or escalate with a
machine-readable reason instead of claiming a repair.
