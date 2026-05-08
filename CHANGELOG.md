# Changelog

All notable changes to TR1NITY will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 4 · v0.5.0-feedback
- **Three-layer FP scoring** (`services/api/app/fp/`) — composite `fp_score` is now `max(L1 whitelist, L2 classifier, L3 suppression, analyst feedback)` with an explainable `fp_layers` breakdown returned on every incident document.
  - **Layer 1 — YAML whitelist** (`services/api/app/fp/whitelist.py` + `whitelist.yaml`): operator-authored deterministic rules with optional TTL. Bundled examples cover authorized vulnerability scanners and internal monitoring health probes. Override path via `TR1NITY_API_FP_WHITELIST` (`off` disables Layer 1 entirely).
  - **Layer 2 — sklearn classifier** (`services/api/app/fp/classifier.py` + `features.py` + `train.py`): logistic-regression classifier trained on analyst "Mark FP" clicks via `make retrain`. The runtime gracefully degrades (returns `0.0`) when no model is loaded, so the api ships with the `requirements-ml.txt` extras as opt-in.
  - **Layer 3 — Suppression rules** (`services/api/app/fp/suppressions.py`): analyst-authored CRUD rules with TTL and audit trail (author + reason). Persisted alongside feedback in SQLite.
- **SQLite-backed feedback DB** (`services/api/app/fp/db.py`) — `fp_feedback` table snapshots the feature vector at click-time for reproducible classifier training; `suppressions` table stores Layer-3 rules. Default path `services/api/data/feedback.sqlite` (override via `TR1NITY_API_FP_DB`); empty path runs in-memory.
- **HTTP API** —
  - `GET /api/runbooks` and `GET /api/runbooks/{technique_id}` (with parent-technique fallback, e.g. `T1110.999` → `T1110`).
  - `GET /api/suppressions`, `POST /api/suppressions`, `GET /api/suppressions/{id}`, `DELETE /api/suppressions/{id}` — auto-prunes expired rules on every list.
  - `POST /api/incidents/{id}/mark-fp` — extended to snapshot the incident's feature vector to the SQLite feedback DB so Layer 2 can train on it.
  - `GET /api/incidents` and `GET /api/incidents/{id}` — every response now carries `fp_score`, `fp_layers[]`, and a `runbook_url` auto-attached by primary ATT&CK technique.
- **16 ATT&CK runbooks** (`docs/runbooks/`) — Markdown with YAML frontmatter (`technique`, `tactic`, `severity`, `references`) covering brute force (T1110, T1110.001, T1110.003), valid accounts (T1078), exploit public-facing app (T1190), active scanning (T1595), network service discovery (T1046), file & directory discovery (T1083), command-and-scripting interpreter (T1059, T1059.001), credential dumping (T1003), data destruction / ransomware (T1486), phishing (T1566), application-layer C2 (T1071), obfuscated files (T1027), remote system discovery (T1018). All runbooks follow the same four-section structure (Triage → Investigation → Containment → Eradication & lessons).
- **Cockpit UI** —
  - New **Runbook tab** on the incident detail page (`ui/src/components/RunbookPanel.tsx`), rendered with `react-markdown` + `remark-gfm`. Auto-fetched by the incident's primary technique.
  - New **FP-layer breakdown badge** on the Overview tab (`ui/src/components/FPLayerBadge.tsx`) showing every layer that contributed to the score and the per-layer detail (rule name, suppression id, classifier probability).
  - New **Suppressions page** at `/cockpit/suppressions` (`ui/src/pages/SuppressionsPage.tsx`) — form for creating Layer-3 rules with JSON match expression, TTL, score, author, audit reason; list view with delete action.
  - Sidebar adds a 4th nav item (key `4`) for Suppressions; version label bumped to `v0.5.0 · Phase 4`.
- **Operator command** — `make retrain` rebuilds the Layer-2 classifier from the SQLite feedback DB. Refuses to train below the `MIN_SAMPLES` (10) and `MIN_PER_CLASS` (3) thresholds. Writes a JSON training report next to the model.
- **Docker Compose** — `api` service now mounts `services/api/data` so the SQLite feedback DB and trained model survive container restarts.
- **Tests** — 38 new pytest tests (whitelist matcher, SQLite DB, suppressions, classifier graceful-degradation, composite scorer, retrain CLI, runbook router, suppression router, layered incident composition); 6 new vitest tests (RunbookPanel, FPLayerBadge, SuppressionsPage form). Total: **191** backend (42 ingestor + 58 correlator + 4 ai-assist + 87 api) + **13** UI tests, all green.

### Added — Phase 3 · v0.4.0-cockpit
- **`services/api` upgraded from Phase-0 hello-world to a Cockpit gateway.** All Phase-0 routes (`/`, `/healthz`, `/readyz`, `/ws` echo) are preserved; the Phase-3 surface is mounted under `/api/*` and `/ws/incidents`.
- **HTTP API** —
  - `GET /api/incidents` (queue with FP-score sort + severity / source / technique filters)
  - `GET /api/incidents/{id}`
  - `POST /api/incidents/{id}/mark-fp`
  - `POST /api/incidents/refresh` (triggers a correlator tick + WS broadcast)
  - `GET /api/incidents/{id}/similar` (Phase-3 deterministic IP / technique heuristic; Phase-5 swaps in ChromaDB cosine similarity)
  - `GET /api/cases` / `POST /api/cases` / `GET /api/cases/{id}` / `PATCH /api/cases/{id}` / `POST /api/cases/{id}/notes` / `DELETE /api/cases/{id}`
  - `GET /api/attack/heatmap`
- **WebSocket** — `/ws/incidents` sends a hello + snapshot on connect, broadcasts `incident.new` events on every refresh, prunes dead clients.
- **In-process `CockpitStore`** — thread-safe FP-feedback ledger, full case CRUD with note timeline, recent-incidents buffer with dedup. Designed so Phase 4 can swap in Postgres without touching routers.
- **Upstream clients** — `CorrelatorClient` (proxies `/incidents` and `/correlate`) and `OpenSearchIncidentReader` (read-only fallback when the correlator restarts and clears its in-memory cache).
- **Incident composition** (`services/api/app/incidents.py`) — merges correlator + recent-buffer + OpenSearch sources, dedupes by id, attaches `fp_score` and `fp_feedback` decoration, sorts (by FP / severity / created / last-event), filters by severity / source / technique. Also computes the ATT&CK heatmap.
- **`ui/` cockpit** — React 18 + Vite 5 + TypeScript + Tailwind 3, no shadcn-runtime dependency (custom primitives styled with Tailwind). Pages: alert queue, single-pane incident view (Overview / Timeline / Raw / Similar tabs), ATT&CK heatmap (kill-chain ordered, frequency-graded), case manager, help. Vim shortcuts: `j/k`, `g g`, `G`, `o`/Enter, `f`/`t`, `c`, `r`, `1`/`2`/`3`/`?`. Live updates via `/ws/incidents` with 15-second polling fallback.
- **Tests** — 49 new pytest tests for the api surface (store, incident composition, heatmap, similar ranking, all HTTP routers, WebSocket fan-out, error paths) plus vitest tests for the UI utilities and Vim hook.

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
