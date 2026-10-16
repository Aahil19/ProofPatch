# GitHub, MCP, and Docker integrations

ProofPatch accepts a completed GitHub Actions run URL and investigates the failure at the exact
recorded commit. The URL path always executes tests through the restricted MCP server and Docker
runner; there is no fallback to host execution.

## Restricted MCP tools

| Tool | Contract |
| --- | --- |
| `get_ci_logs` | Return captured failed-job logs and immutable GitHub provenance |
| `read_file` | Read a bounded regular file from the copied repository |
| `run_tests` | Execute pytest in a fresh restricted container and return structured evidence |
| `get_diff` | Return the current source-only unified diff from the disposable workspace |

Paths must be repository-relative. Traversal, symlinks, hidden files, files outside the initial
inventory, oversized reads, arbitrary commands, unapproved pytest arguments, and test or config
edits are rejected. Every tool call is recorded in `mcp-tools.jsonl`.

## GitHub ingestion

The client pins the workflow attempt, retrieves metadata and failed-job logs, downloads the
commit archive, and validates its shape before extraction. The evidence bundle records the
repository, run ID, attempt, commit SHA, source archive hash, and Docker image ID. Reproduced
pytest IDs must be present as failed entries in the CI logs.

Public repositories can be read without a token subject to GitHub's anonymous limits. Private
repositories and higher rate limits require `GITHUB_TOKEN` or `GH_TOKEN` with read-only access to
Actions and contents. Live provider mode additionally requires `OPENAI_API_KEY`.

## Container policy

The default image is intentionally small and pinned by digest at runtime. It contains Python,
pytest, and the ProofPatch evidence plugin. Target dependencies are not installed dynamically.
For projects with extra dependencies, build and review a dedicated image rather than granting
network access to the incident container.

See [architecture](architecture.md) for the full trust boundary.
