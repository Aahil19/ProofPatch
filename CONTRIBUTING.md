# Contributing

ProofPatch accepts focused issues and pull requests that preserve its evidence contract. Before
opening a change, explain the failure mode, the expected behavior, and which verification gate
demonstrates the result.

## Local checks

```bash
python -m pip install -c requirements.lock -e '.[dev]'
ruff check .
ruff format --check .
pytest -q
```

Changes to orchestration, verification, patch validation, or execution isolation should include
a test that would fail if the control were removed. Benchmark changes must retain an honest
description of scripted versus model-generated behavior and regenerate `benchmarks/results.json`
through `scripts/run_benchmark.py`.

Never include API keys, private repository logs, or evidence containing secrets in an issue,
commit, or workflow artifact.
