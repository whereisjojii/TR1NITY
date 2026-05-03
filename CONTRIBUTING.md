# Contributing to TR1NITY

First — thank you for considering a contribution. TR1NITY is built by SOC analysts, for SOC analysts. This guide is written to keep your first PR painless.

---

## Ground rules

- **Defensive security only.** TR1NITY is a defender-side platform. Pull requests that add offensive tooling, malware samples, or live-target attack capabilities will be closed. Synthetic attack *generators* (used inside `make demo` to exercise the pipeline) are welcome.
- **Zero paid APIs.** Every external service we depend on must have a permanent free tier. If your contribution introduces an API call, document the free-tier limits in `docs/planning/03-build-pathway.md`.
- **Small, focused PRs.** One module change per PR. Cross-module refactors should be staged.
- **Repo size discipline.** No single file over 10 MB. No datasets, model weights, or container images committed — see [`.gitignore`](.gitignore).

---

## Setting up your dev environment

### Prerequisites

- **OS:** Ubuntu 22.04 LTS / Debian 12 / Fedora 40+ (or any Linux with Docker)
- **Docker Engine** 24+ and **Docker Compose** plugin v2.20+
- **Python** 3.11+
- **Node.js** 20+ and `pnpm` (for the `ui/` workspace)
- **Make**

### First-time setup

```bash
git clone https://github.com/whereisjojii/TR1NITY.git
cd TR1NITY

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# (Optional, for AI Assist development) install Vulkan + llama.cpp
# See docs/planning/03-build-pathway.md, Phase 5
```

### Running the stack locally

```bash
make up           # boot Docker Compose stack
make logs         # tail aggregated service logs
make demo         # generate a synthetic attack chain
make down         # stop everything
make clean        # nuke volumes (destructive)
```

---

## Branching & commits

- Branch naming: `feat/<short-slug>`, `fix/<short-slug>`, `docs/<short-slug>`, `chore/<short-slug>`.
- Work on `main` is forbidden — always branch off and PR back.
- One commit per logical change is preferred; squash on merge is fine.
- Conventional Commits style is encouraged but not required:
  - `feat(brain): add SIGMA rule auto-translator`
  - `fix(ingestor): handle malformed iptables timestamps`

---

## Pull requests

1. Open against `main`.
2. Fill in the [PR template](.github/PULL_REQUEST_TEMPLATE.md). Keep "What changed", "Why", "How tested" honest and short.
3. CI must pass (lint + tests + Docker build). See `.github/workflows/ci.yml`.
4. Reviewer will ask for changes; iterate.
5. Squash-and-merge on green CI.

---

## What's currently being worked on

See [`ROADMAP.md`](ROADMAP.md) and the GitHub Project board. Each phase has its own milestone tag (`v0.1.0-foundation` → `v1.0.0`). If you want to claim a phase, open an issue first so we don't double up.

---

## Code style

- **Python:** `ruff` for lint and format (config: `pyproject.toml`). `mypy` for type-checking.
- **TypeScript / React:** `eslint` + `prettier` (config in `ui/`).
- **YAML / Markdown:** lint via pre-commit.
- **No `Any` / `getattr` shortcuts** in Python. If you need them, the type model is wrong — please fix the type model instead.

---

## Reporting bugs

- Use the **Bug Report** issue template.
- Include exact reproduction steps, container logs (`make logs > /tmp/log.txt`), the deployment profile (Demo / Standard / Full AI), and your hardware.

---

## Reporting security issues

**Do not file a public issue for a vulnerability.** Email the maintainers privately. See [`SECURITY.md`](SECURITY.md).

---

## License

By contributing to TR1NITY you agree that your contribution will be licensed under the [MIT License](LICENSE).
