# Changelog

All notable changes to TR1NITY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial repository scaffold: README, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.
- Architecture overview (`ARCHITECTURE.md`) and roadmap (`ROADMAP.md`).
- Issue templates and pull-request template.
- Aggressive `.gitignore` enforcing the "no datasets / no model weights / no Docker volumes" rule.
- Service layout (`services/{ingestor,correlator,ai-assist,api}`, `ui/`, `deploy/`, `scripts/`, `tests/`, `configs/`).
- Docker Compose skeleton with Wazuh manager + indexer (profile-gated), Postgres, ChromaDB, and four FastAPI services.
- Hello-world FastAPI services for `ingestor`, `correlator`, `ai-assist`, `api` with `/healthz`, `/readyz`, smoke tests, and Dockerfiles.
- GitHub Actions CI (hygiene + per-service lint/test + Docker Compose syntax check).
- MkDocs Material documentation site (`mkdocs.yml`, `docs/`).
- Pre-commit hooks (ruff, prettier, large-file guard, paid-API guard).
- Makefile with `make up`, `make down`, `make ps`, `make logs`, `make test`, `make lint`, `make docs`.

[Unreleased]: https://github.com/whereisjojii/TR1NITY/compare/v0.1.0-foundation...HEAD
[v0.1.0-foundation]: https://github.com/whereisjojii/TR1NITY/releases/tag/v0.1.0-foundation
