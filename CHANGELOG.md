# Changelog

All notable changes to TR1NITY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 2 · v0.3.0-correlation
- **Incident model** (`services/correlator/app/incident.py`) with `Incident` and `IncidentMember`, severity promotion (max-of-members), and `to_index_doc()` serializer for OpenSearch.
- **Sliding-window grouping** (`services/correlator/app/grouping.py`) — events sharing a `source.ip` within `INCIDENT_WINDOW_SECONDS` (default 15 min) and below `INCIDENT_MAX_EVENTS` (default 500) collapse into one incident; events without an IP become single-event incidents.
- **MITRE ATT&CK chain promotion** (`services/correlator/app/attack.py`) — deduped, kill-chain-ordered technique IDs and tactics; human-readable summary chain rendered onto every incident.
- **In-process SIGMA-style engine** (`services/correlator/app/sigma/`) — strict subset of the SIGMA spec: equality + `contains` / `startswith` / `endswith` / `re` modifiers, list-as-OR, condition combinators (`and` / `or` / `not` / `1 of <prefix>*` / `1 of them`). Bundled rule pack covers Wazuh SSH brute-force, WAF SQLi, WAF path traversal, firewall portscan.
- **Threat-intel cache** (`services/correlator/app/intel/`) — `Provider` protocol, TTL-bounded `IntelCache` (caches positive AND negative results), bundled file-based starter (`app/intel/data/ioc.json`); free feeds only, no paid APIs.
- **Pluggable consumer + sinks** (`services/correlator/app/consumer/`, `app/sinks/`) — `InMemoryEventConsumer` (DRY_RUN + tests), `OpenSearchEventConsumer` (high-water-mark polling against `tr1nity-events-*`), `StdoutIncidentSink` (DRY_RUN), `OpenSearchIncidentSink` (writes to daily `tr1nity-incidents-YYYY.MM.dd`).
- **Pipeline orchestrator** (`services/correlator/app/pipeline.py`) — wires consumer → SIGMA → grouping → ATT&CK + intel enrichment → sinks; exposes `last_incidents` for `/incidents`.
- **HTTP API** — `POST /correlate` runs one tick; `GET /incidents` returns the latest tick's incidents; `POST /ingest-test` pushes events into the in-memory consumer for demos and integration tests.
- **Docs rewrite** — `docs/modules/correlation.md` documents the full pipeline, configuration knobs, and tests.
- **Tests** — 57 passing tests (`pytest`) covering grouping, ATT&CK ordering, the SIGMA engine (parser + matcher), intel caching, both sinks (with `httpx.MockTransport`), the OpenSearch consumer, full pipeline, and HTTP endpoints.

### Added — Phase 1 · v0.2.0-ingest
- **ECS 8.11 schema** (`services/ingestor/app/ecs.py`) covering event/host/source/destination/user/network/http/url/rule/threat/tr1nity blocks with `to_index_doc()` serializer.
- **Wazuh parser** (`app.sources.wazuh`) — converts Wazuh alert JSON to ECS, maps `rule.level 0–15 → severity 0–4 → ECS 0–7`, extracts MITRE tactic/technique metadata.
- **Firewall parser** (`app.sources.firewall`) — auto-detects iptables kernel logs, pfSense filterlog CSV, OPNsense CSV in a single batch endpoint.
- **ModSecurity / WAF parser** (`app.sources.modsec`) — converts ModSec v3 audit docs to ECS, classifies SQLi / XSS / RCE / LFI / SSRF / scanner attempts to MITRE techniques.
- **Sinks** — `OpenSearchSink` (raw httpx, NDJSON `_bulk`, daily `tr1nity-events-YYYY.MM.dd` index, per-item status accounting, network/auth failure handling) and `StdoutSink` (used by `DRY_RUN=true` and tests).
- **Routers** — `POST /ingest/wazuh`, `POST /ingest/syslog`, `POST /ingest/waf` with optional bearer-token auth (`ENABLE_AUTH=true`, constant-time compare) and partial-failure 202 / full-failure 422 semantics.
- **Config** (`pydantic-settings`) — typed env-var loader with `SecretStr` for credentials, body-size + batch-size guardrails.
- **Synthetic attack chain demo** — `make demo` / `python scripts/demo/synth_attack.py` fires firewall → WAF → Wazuh events with the same source IP, ready for Phase 2 correlation.
- **Filebeat template** (`deploy/filebeat/filebeat.yml`) for shipping iptables / pfSense / ModSec logs over HTTP into the ingestor.
- **Tests** — 42 passing tests (`pytest`) covering ECS schema, all three parsers, both sinks (with httpx `MockTransport`), and HTTP endpoint contracts including auth.

### Added — Phase 0 · v0.1.0-foundation
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
