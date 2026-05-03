# Changelog

All notable changes to TR1NITY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial repository scaffold: README, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.
- Architecture overview (`ARCHITECTURE.md`) and roadmap (`ROADMAP.md`).
- Phase-1 academic-style project documentation (PDF) under `docs/report/`.
- Three planning documents (feasibility, final scope, build pathway) under `docs/planning/`.
- Issue templates and pull-request template.
- Aggressive `.gitignore` enforcing the "no datasets / no model weights / no Docker volumes" rule.
- Service layout placeholders (`services/{ingestor,correlator,ai-assist,api}`, `ui/`, `deploy/`, `scripts/`, `tests/`, `configs/`).

## [v0.1.0-foundation] — Phase 0 (planned)

### Planned
- Docker Compose skeleton with Wazuh manager + indexer + 4 FastAPI hello-world services.
- GitHub Actions CI (lint + test + Docker build).
- MkDocs Material documentation site.
- Pre-commit hooks (ruff, prettier, file-size guard).
- Makefile with `make up`, `make down`, `make logs`, `make demo`, `make test`.

[Unreleased]: https://github.com/whereisjojii/TR1NITY/compare/v0.1.0-foundation...HEAD
[v0.1.0-foundation]: https://github.com/whereisjojii/TR1NITY/releases/tag/v0.1.0-foundation
