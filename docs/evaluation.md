# Evaluation report

## Result

ProofPatch's supervisor policy verified **27 of 30** seeded failures (90%). A single-attempt
baseline using the same first candidate verified **21 of 30** (70%). All 30 supervisor runs
reproduced the initial failure and emitted an agent trace. Three cases intentionally exhausted
both candidates and escalated. No run was labelled verified without passing focused and
regression evidence.

| Metric | ProofPatch supervisor | Single-attempt baseline |
| --- | ---: | ---: |
| Verified repairs | 27 / 30 | 21 / 30 |
| Verified repair rate | 90% | 70% |
| Escalations | 3 | 9 |
| Median local latency | 0.77 s | 0.56 s |
| 95th percentile local latency | 1.15 s | 0.56 s |
| LLM cost | $0 | $0 |

The latency values are from the committed macOS/Python 3.11 snapshot and will vary by machine.
The full machine-readable result is in [`benchmarks/results.json`](../benchmarks/results.json),
and the [interactive dashboard](https://aahil19.github.io/ProofPatch/) exposes every case.

## Corpus

The corpus contains three dependency-free Python projects with ten independent functions and ten
tests each:

| Project | Domain | Scenarios |
| --- | --- | ---: |
| `textops` | normalization, parsing, formatting, privacy, slicing | 10 |
| `dataops` | arithmetic, statistics, ordering, aggregation, matrices | 10 |
| `apiops` | HTTP semantics, response parsing, pagination, backoff | 10 |

Each scenario replaces one known-correct source fragment with a deterministic defect. The
baseline suite then contains exactly one failing test and nine passing tests. Seven scenarios per
project have a correct first candidate, two have an incorrect first candidate followed by a
correct second candidate, and one contains two incorrect candidates to exercise escalation.

## Systems compared

The **single-attempt baseline** observes the failing suite, applies the first candidate once,
and runs the same focused and regression gates. It does not reproduce the failure separately and
does not retry from verifier feedback.

The **ProofPatch supervisor** independently reproduces the failing node ID, records investigator
and repair transitions, applies the first candidate to a disposable copy, and executes focused
plus regression verification. On six cases, the first candidate fails and its evidence is used
for one bounded retry from the original failing snapshot. All six second candidates verify.
Three other cases fail both attempts and escalate with preserved evidence.

## Interpretation

This evaluation measures the reliability layer under controlled candidate quality. Candidate
patches and diagnoses are scripted fixtures, so the 90% result must not be interpreted as an LLM
repair success rate. The 20-point difference demonstrates that verification-informed retry can
recover correct candidates without weakening the evidence contract. The three safe escalations
demonstrate that the system refuses to convert persistent failure into a success claim.

The benchmark is deterministic in scenario content but real in execution: every outcome is
produced by pytest, exact node IDs are compared before and after the patch, source edits go
through the production patch validator, and the supervisor runs through the production LangGraph
workflow.

## Reproduce the report

```bash
python -m pip install -c requirements.lock -e '.[dev]'
python scripts/run_benchmark.py \
  --output artifacts/benchmark-results.json \
  --evidence-dir artifacts/benchmark/evidence
```

The output JSON includes environment metadata, methodology, aggregate metrics, and all 30 case
records. The evidence directory contains production-format incident reports, traces, pytest logs,
structured outcomes, proposals, and diffs. CI uploads both as the `proofpatch-benchmark` artifact.

## Limitations and next evaluation

- The projects are small, dependency-free, and each scenario contains one seeded defect.
- Candidate ordering is fixed and known to the harness.
- Trusted-local subprocess execution is used for benchmark speed; Docker isolation is validated
  separately by the integration suite.
- Costs are zero because no language model is called.
- Generalization to unseen repositories and model-generated candidates remains unmeasured.

A model-quality study should freeze this harness, replace only the scripted provider, use held-out
repositories whose fixes are hidden from the model, report confidence intervals across repeated
runs, and publish model identifiers, prompts, token usage, prices, timeouts, and all escalations.
