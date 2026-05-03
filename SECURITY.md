# Security Policy

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, email the maintainers privately at one of:

- **Hamza** — _(contact via repo owner)_
- **Irtaza** — _(contact via repo owner)_
- **Hammad** — _(contact via repo owner)_

You can also use GitHub's [private security advisory](https://github.com/whereisjojii/TR1NITY/security/advisories/new) flow.

We aim to:

- Acknowledge your report within **72 hours**.
- Provide an initial assessment within **7 days**.
- Issue a fix or mitigation within **30 days** for high-severity issues.

## Supported versions

| Version                    | Supported                  |
| -------------------------- | -------------------------- |
| `main` (development)       | yes                        |
| Tagged releases (`v0.x.x`) | best-effort during pre-1.0 |
| `v1.0.0`+                  | yes                        |

## Scope

This policy covers the TR1NITY codebase only. Vulnerabilities in upstream dependencies (Wazuh, OpenSearch, ModSecurity, FastAPI, React, etc.) should be reported directly to those projects, although we appreciate notification so we can pin / patch.

## Out of scope

- Issues caused by running TR1NITY in unsupported configurations (custom forks, modified Docker images, untrusted plugins).
- Theoretical vulnerabilities without a reproducer.
- Best-practice violations that do not produce a concrete attack vector.

## Defensive-only commitment

TR1NITY is, and will remain, a defender-side platform. We will not publish or accept contributions that ship offensive capabilities (live-target exploitation, malware staging, credential harvesting). Synthetic attack _generators_ used within our own test pipeline (e.g. `make demo`) are explicitly scoped to the local test environment.
