# TR1NITY Architecture

> **TL;DR** — Three log streams (Wazuh, firewall, WAF) → one normalized OpenSearch index (`tr1nity-events-*`) → correlation engine ("The Brain") → analyst cockpit (React) → optional AI-drafted reports (Foundation-Sec-8B). Six modules, four FastAPI services, one Docker Compose file.

For the academic-style version of this document with citations and Gantt chart, see [`docs/report/tr1nity_report.pdf`](docs/report/tr1nity_report.pdf).

---

## High-level diagram

```
                        ┌─────────── Source Layer ────────────┐
                        │  Wazuh Agent     iptables / pfSense │
                        │  ModSecurity     Suricata (optional)│
                        └──────────────────┬──────────────────┘
                                           │ webhook / syslog / EVE JSON
                          ┌────────────────▼────────────────┐
                          │  Module 1 — Ingestion           │
                          │  (FastAPI ingestor + Filebeat)  │
                          │  Maps everything to ECS schema  │
                          └────────────────┬────────────────┘
                                           │  ECS-shaped JSON
                          ┌────────────────▼────────────────┐
                          │  Wazuh Indexer / OpenSearch     │
                          │  Index: tr1nity-events-*        │
                          └────────────────┬────────────────┘
                                           │
            ┌──────────────────────────────┼──────────────────────────────┐
            │                              │                              │
   ┌────────▼────────┐         ┌───────────▼───────────┐         ┌────────▼────────┐
   │ Module 2 —      │         │ Module 3 — AI Assist  │         │ Module 5 —      │
   │ The Brain       │  reads  │ (FastAPI ai-assist)   │  reads  │ The Cockpit     │
   │ (correlator)    ◄─────────│ Foundation-Sec-8B Q4  ◄─────────│ (React + WS)    │
   │                 │         │ via llama.cpp+Vulkan  │         │                 │
   └────────┬────────┘         └───────────┬───────────┘         └────────┬────────┘
            │                              │                              │
            │   incidents                  │   drafts                     │   user
            │                              │                              │   feedback
            └────────────┬─────────────────┴──────────────┬───────────────┘
                         │                                │
                ┌────────▼────────┐              ┌────────▼────────┐
                │ ChromaDB (RAG)  │              │ Module 4 —      │
                │ ATT&CK + NVD +  │              │ FP Handling     │
                │ SIGMA + runbooks│              │ (3-layer)       │
                └─────────────────┘              └────────┬────────┘
                                                          │
                                                 ┌────────▼────────┐
                                                 │ PostgreSQL      │
                                                 │ Cases + audit + │
                                                 │ FP feedback +   │
                                                 │ runbook history │
                                                 └─────────────────┘

                          ┌────────────────────────────────┐
                          │  Module 6 — Knowledge & Report │
                          │  Compliance PDFs · weekly KPIs │
                          │  Backup/Restore · Runbook UI   │
                          └────────────────────────────────┘
```

A rendered, blue-themed PDF version of this diagram is included in the Phase-1 report on page 9.

---

## Service inventory (Phase 0 → v1.0)

| Service                                | Tech                                | Port              | Purpose                                                                          |
| -------------------------------------- | ----------------------------------- | ----------------- | -------------------------------------------------------------------------------- |
| `wazuh-manager`                        | Wazuh 4.x (upstream image)          | 1514, 1515, 55000 | HIDS server                                                                      |
| `wazuh-indexer`                        | Wazuh Indexer (OpenSearch fork)     | 9200              | Event store                                                                      |
| `wazuh-dashboard`                      | Wazuh Dashboard                     | 5601              | Wazuh-native UI (dev only; we replace with the Cockpit)                          |
| `postgres`                             | Postgres 16                         | 5432              | Cases, audit, FP feedback, runbook history                                       |
| `chromadb`                             | ChromaDB (in-process Python lib)    | —                 | Vector store for RAG                                                             |
| `ingestor`                             | FastAPI + Pydantic                  | 8001              | Receives webhook / syslog → ECS → OpenSearch                                     |
| `correlator`                           | FastAPI + asyncio                   | 8002              | Periodic loop: temporal grouping, entity resolution, ATT&CK, threat-intel, SIGMA |
| `ai-assist`                            | FastAPI + `llama.cpp` (Vulkan)      | 8003              | Async drafting of post-incident reports, runbooks, compliance summaries          |
| `api`                                  | FastAPI + WebSocket                 | 8000              | Public REST + WebSocket; serves the static React build                           |
| `ui` (build artefact, served by `api`) | React + Vite + Tailwind + shadcn/ui | —                 | The Cockpit                                                                      |

Total RAM at full tilt: ~9 GB (Wazuh manager + indexer ~3 GB + Foundation-Sec-8B Q4 ~5 GB + the rest <1 GB). Headroom on a 16 GB host: ~7 GB.

---

## Data flow — life of an alert

1. **Adversary action** — port scan, brute-force, SQL injection, lateral movement, etc.
2. **Source emit** — Wazuh agent (host telemetry), firewall (network), ModSecurity (web application).
3. **Ingestion** — `ingestor` accepts webhook from Wazuh, syslog from firewall (UDP 514), Filebeat shipment from ModSecurity. Each format has a dedicated parser; output is a single ECS-shaped JSON document.
4. **Normalize** — Common fields: `@timestamp`, `event.module`, `source.ip`, `destination.ip`, `user.name`, `host.name`, `event.severity`, `threat.tactic`, `threat.technique`, `tr1nity.raw` (original payload).
5. **Index** — Document written to `tr1nity-events-YYYY.MM.DD` with ISM (Index State Management) hot → warm → cold → delete lifecycle (default: 7d hot, 30d warm, 90d cold close, 180d delete).
6. **Correlate** — Every 30 seconds the `correlator` queries the last 5 minutes, groups events by `(source.ip, destination.ip OR user.name, host.name)`, materializes an _incident_ document with all source events linked, ATT&CK techniques tagged, and threat-intel auto-attached.
7. **Enrich** — Cached lookups against AbuseIPDB / OTX / NVD / abuse.ch / GeoLite2. 24-hour TTL per IOC keeps free-tier limits happy.
8. **FP score** — Three layers: (i) deterministic YAML whitelist, (ii) sklearn classifier learning from analyst "Mark FP" clicks, (iii) analyst-authored suppression rules. Each incident gets `fp_score` ∈ \[0, 1\].
9. **Cockpit** — Incident appears in the analyst queue, sorted ascending by `fp_score` (high-confidence first). Single-pane investigation view shows raw payload, enrichment sidebar, entity timeline, similar past incidents (semantic search via ChromaDB).
10. **Triage** — Analyst marks FP, opens case, deploys SIGMA rule, or closes resolved.
11. **AI draft (async)** — On case closure, `ai-assist` drafts the post-incident report (Markdown), grounded by ChromaDB-retrieved context. Analyst reviews, edits, saves.
12. **Audit + report** — Every action is journaled into PostgreSQL. Weekly metrics (alert volume, FP rate, MTTR, top firing rules, ATT&CK coverage delta) auto-generate. Compliance PDFs (PCI-DSS, ISO 27001, NIST CSF) export on demand.

---

## Storage

| Data                                                     | Where                            | Retention                                                    |
| -------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------ |
| Raw events                                               | OpenSearch `tr1nity-events-*`    | 7d hot, 30d warm, 90d cold close, 180d delete (configurable) |
| Incidents (correlated)                                   | OpenSearch `tr1nity-incidents-*` | 365d default                                                 |
| Cases, audit, FP feedback, runbook history               | PostgreSQL                       | Forever                                                      |
| RAG vectors (ATT&CK, NVD, SIGMA, runbooks, post-mortems) | ChromaDB (persistent on disk)    | Forever; rebuilt on demand                                   |
| ML models (FP classifier)                                | `models/` (gitignored)           | Versioned; published as GitHub Releases                      |
| Threat-intel cache                                       | Redis (or in-process LRU)        | 24h TTL per IOC                                              |

---

## What's deliberately not here

For the rationale on these cuts, see [`docs/planning/02-final-scope.md`](docs/planning/02-final-scope.md):

- No multi-class network-flow ML on production traffic (CICIDS2017-style).
- No self-rewriting SIGMA rule generator.
- No UEBA module (no baseline data to support it).
- No Markov-chain kill-chain prediction.
- No bundled TheHive / Cortex / MISP servers (we ship lightweight equivalents and an opt-in TheHive _adapter_).
- No always-on LLM enrichment of every alert (the LLM drafts post-incidents, never triages real-time).

---

## Pointers

- Per-module deep dives: [`docs/planning/03-build-pathway.md`](docs/planning/03-build-pathway.md).
- Phase-by-phase delivery plan: [`ROADMAP.md`](ROADMAP.md).
- Use cases, test cases, market value, citations: [`docs/report/tr1nity_report.pdf`](docs/report/tr1nity_report.pdf).
