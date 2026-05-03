# TR1NITY Roadmap

> **Cadence beats perfection.** Every phase ends with a tagged release and a runnable `make` command. Worst-case, an early phase still ships value.

This file is the short, version-controlled scoreboard for the build.

---

## Phase 0 — Foundation (Week 1) → `v0.1.0-foundation`

**Goal:** runnable empty stack. Nothing useful happens yet, but `make up` boots clean on any 16 GB host.

- [ ] Repository scaffolded (this PR)
- [ ] Docker Compose: Wazuh manager + Wazuh indexer + Postgres + ChromaDB + 4 FastAPI hello-worlds
- [ ] GitHub Actions CI (lint + test + Docker build)
- [ ] MkDocs Material site (auto-deploys to GitHub Pages)
- [ ] Pre-commit hooks (ruff, prettier, file-size guard)
- [ ] Makefile (`make up`, `make down`, `make logs`, `make test`, `make demo`)
- [ ] `.env.example` with every variable documented

**Demo command:** `make up && curl http://localhost:8000/healthz`.

---

## Phase 1 — Multi-Source Ingestion (Weeks 2–3) → `v0.2.0-ingest`

**Goal:** all three log sources flow into a single normalized index.

- [ ] Wazuh webhook receiver in `ingestor` (decodes Wazuh alerts → ECS)
- [ ] Async syslog server (UDP 514) parsing iptables and pfSense formats
- [ ] ModSecurity audit log parser (JSON or CEF)
- [ ] (Optional) Suricata EVE JSON tail
- [ ] Unified ECS schema: `@timestamp`, `event.module`, `source.ip`, `destination.ip`, `user.name`, `host.name`, `event.severity`, `tr1nity.raw`
- [ ] OpenSearch index `tr1nity-events-*` with ISM lifecycle policy
- [ ] Synthetic generator: `make demo` produces a Wazuh + firewall + WAF triplet for the same source IP
- [ ] Test: a single OpenSearch query for `source.ip:<x>` returns all three events

**Demo command:** `make up && make demo && open "http://localhost:5601/_dashboards/app/dashboards#/view/tr1nity"`.

---

## Phase 2 — The Brain (Weeks 4–7) → `v0.3.0-brain`

**Goal:** raw events become correlated incidents.

- [ ] `correlator` periodic 30s loop
- [ ] Temporal grouping (5-minute sliding window) per `(source.ip, target, user)`
- [ ] Entity resolution (same attacker across Wazuh + firewall + WAF)
- [ ] MITRE ATT&CK tagging (Wazuh native rule map + SIGMA-derived map for non-Wazuh)
- [ ] Threat-intel enrichment (AbuseIPDB, AlienVault OTX, NVD, abuse.ch, GeoLite2) with 24h cache
- [ ] SIGMA rule import via `pySigma` (3,000+ community rules)
- [ ] SIGMA rule "test before deploy" against last-7-days data
- [ ] Runbook auto-attachment by ATT&CK technique

**Demo command:** `make demo && curl localhost:8002/incidents | jq '.[0]'` shows one incident with 3 source events + ATT&CK + AbuseIPDB attached.

---

## Phase 3 — The Cockpit (Weeks 8–11) → `v0.4.0-cockpit`

**Goal:** an analyst can fully investigate without opening a second tool.

- [ ] React + Vite + Tailwind + shadcn/ui project
- [ ] Alert queue with FP score sort
- [ ] Single-pane investigation panel (raw + enrichment + timeline + similar incidents)
- [ ] MITRE ATT&CK Navigator-style heatmap
- [ ] "Similar past incidents" semantic search via ChromaDB
- [ ] Lightweight built-in case manager (alternative to TheHive)
- [ ] Vim-style keyboard shortcuts (`j/k` navigate, `o` open, `f` mark FP, `c` create case)
- [ ] WebSocket live updates from `correlator`

**Demo command:** `make up && open http://localhost:8000` → triage 5 incidents in <2 min using only the keyboard.

---

## Phase 4 — FP Loop & Runbooks (Weeks 12–13) → `v0.5.0-feedback`

**Goal:** the platform learns from analyst feedback.

- [ ] Layer 1: deterministic YAML whitelist (vulnerability scanners, monitoring tools, etc.)
- [ ] Layer 2: sklearn FP classifier — features from alert metadata; trains on analyst "Mark FP" clicks; weekly `make retrain`
- [ ] Layer 3: analyst-authored suppression rules with TTL and audit trail
- [ ] 15+ Markdown runbooks (T1110.001 brute force, T1078 valid accounts, T1190 web exploit, etc.)
- [ ] Auto-attach runbook to incident by primary ATT&CK technique

**Demo command:** mark 50 alerts as FP → `make retrain` → held-out sample shows reduced FP score on similar alerts.

---

## Phase 5 — AI Assist (Weeks 14–15) → `v0.6.0-ai`

**Goal:** AI drafts the boring documents the analyst doesn't want to write.

- [ ] `llama.cpp` build with Vulkan backend
- [ ] Foundation-Sec-8B-Instruct Q4_K_M deployment
- [ ] ChromaDB ingest of ATT&CK + NVD + SigmaHQ + runbooks + resolved cases
- [ ] Async drafting endpoints: incident report, runbook, CVE explanation, weekly compliance summary
- [ ] `MOCK_LLM=true` deterministic-template fallback for users without a GPU
- [ ] Drafts queue UI ("Ready to review" badge per incident)

**Demo command:** close a case in the UI → 30 s later, "Draft ready" badge appears with a complete Markdown post-mortem.

---

## Phase 6 — Polish, Reporting, Launch (Week 16) → `v1.0.0`

**Goal:** v1.0 is presentable, demonstrable, restoreable.

- [ ] Compliance PDF generator (PCI-DSS, ISO 27001, NIST CSF) via WeasyPrint / ReportLab
- [ ] Weekly metrics report (alert volume, FP rate, MTTR, top-firing rules, ATT&CK coverage delta)
- [ ] `make backup` + `make restore` round-trip
- [ ] README polish with demo GIF
- [ ] 90-second demo video
- [ ] v1.0.0 launch announcement

---

## Success metrics (target at v1.0)

| Metric                                      | Target   |
| ------------------------------------------- | -------- |
| Quickstart from `git clone` to first alert  | < 15 min |
| FP rate after 2 weeks of analyst feedback   | < 30 %   |
| Time-to-triage (vs. unfederated baseline)   | −70 %    |
| Outside contributors at 90 days post-launch | ≥ 3      |
| GitHub stars at 90 days post-launch         | ≥ 500    |

---

## Status legend

- [ ] Pending
- [~] In progress (current session)
- [x] Done (merged to `main`)
