# Security policy

## Supported version

Security fixes are applied to the current `main` branch.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature for this repository when available. Do not
open a public issue containing an exploit, credential, private CI log, or sensitive repository
content. Include the affected component, reproduction conditions, impact, and a minimal proof of
concept that does not target third-party systems.

## Execution warning

Trusted-local mode runs target tests with the current user's operating-system permissions. Docker
mode reduces exposure with no network, a non-root user, a read-only root filesystem, dropped
capabilities, and resource limits, but container isolation is not a complete defense against
hostile code or a compromised Docker daemon. Use disposable infrastructure for untrusted input.
