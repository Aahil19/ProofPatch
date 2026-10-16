# Evidence model and acceptance criteria

ProofPatch's central invariant is simple: a provider proposal is never proof. Only executable,
identity-preserving test evidence can move an incident to `verified`.

## Verification gates

An incident is verified only when:

- the baseline run is valid and includes at least one failed pytest node ID;
- an untouched copy reproduces exactly those failed node IDs;
- focused execution collects exactly the original failed IDs and all of them pass;
- the selected regression suite exits successfully;
- regression collection contains exactly the baseline test IDs;
- every baseline test that executed as pass or fail now passes;
- protected files and repository contents match the expected candidate snapshot.

The run escalates on collection errors, missing or malformed evidence, timeouts, skips replacing
failures, flaky reproduction, changed test identities, invalid edits, repository mutation,
provider errors, or exhausted repair attempts.

## Fixture acceptance case

`examples/buggy_stats` contains three independent defects exercised by nine tests. The expected
baseline is five failed and four passed tests. The scripted fixture provider repairs only
`stats.py`; focused verification must pass all five former failures and regression verification
must pass all nine tests. The original example stays deliberately broken so the demonstration
is repeatable.

## Scope

The verified label always names its scope: selected test targets, captured environment, exact
source hashes, and execution mode. It does not assert behavior that the selected suite did not
exercise. This distinction is preserved in both the human report and machine-readable schema.
