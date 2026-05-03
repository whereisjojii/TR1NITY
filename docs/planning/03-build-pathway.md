# TR1NITY — Complete Build Pathway

**Project name:** TR1NITY (formerly SENTINEL-CORE — retired)
**Builder:** Solo, you. Hardware: Ryzen 7 3700X / 16 GB / RX 590 (server) + i5-13th / 8 GB (dev workstation)
**License model:** 100% free / open-source — **zero paid APIs, zero paid services, zero subscriptions**
**Deployment target:** Single Docker Compose stack, runnable on any machine ≥ 16 GB RAM

This document covers exactly what you asked for:
1. Free-only API/service audit (proof nothing requires paid access)
2. GitHub storage strategy (how 30 GB on your PC stays under 100 MB in the repo)
3. **Explicit re-confirmation** that unified Wazuh + Firewall + WAF logs, correlation, and FP handling are core and uncut
4. Step-by-step build pathway — week-by-week, with day-level detail for the early weeks

---

## SECTION 0 — The non-negotiable core (re-confirmation)

> **Stating this up front so it is unambiguous: the unified-log + correlation + false-positive handling pipeline is THE REASON TR1NITY EXISTS. None of it is cut. None of it is deferred. It is built FIRST.**

### Wazuh logs + Firewall logs + WAF logs in ONE place — *kept, core, built in Phase 1*

How: a single OpenSearch index (`tr1nity-events-*`) using a unified ECS-compatible JSON schema. All three sources land here:

- **Wazuh alerts** — pushed by Wazuh manager via its built-in indexer write path (already does this natively). TR1NITY's `ingestor` service also receives them via webhook for additional enrichment paths.
- **Firewall logs** — iptables / pfSense / OPNsense / UFW. Sent to TR1NITY's `ingestor` over syslog (UDP 514) → parsed → normalized to ECS schema → written to the same index.
- **WAF logs** — ModSecurity (CRS rules), Nginx WAF, OPNsense WAF. Sent to `ingestor` either via syslog or by Filebeat tailing the WAF log file → parsed (CEF or JSON) → normalized → same index.
- **(bonus, free)** Suricata EVE JSON if the user has it; same path.

Common schema fields every event gets, regardless of source:
```
@timestamp, source.ip, source.port, source.geo.country, source.asn,
destination.ip, destination.port, host.name, host.ip,
user.name, user.id, process.name, process.command_line,
event.action, event.category, event.outcome, event.module,    // <- which source
event.dataset,                                                  // <- wazuh/iptables/modsec/...
http.request.method, http.request.body.bytes, http.response.status_code,
url.full, url.domain, url.path,
file.hash.md5, file.hash.sha256, file.path,
mitre.technique.id, mitre.tactic.id,                          // <- attached by correlator
tr1nity.fp_score, tr1nity.priority, tr1nity.incident_id,      // <- TR1NITY enrichments
tr1nity.runbook_id, tr1nity.threat_intel.*,                   // <- TR1NITY enrichments
tr1nity.entity_resolution.*,                                  // <- correlator output
raw.message                                                    // <- always preserve original
```

This means an analyst querying "show me everything that touched 1.2.3.4 in the last 24 h" gets Wazuh HIDS alerts, firewall denies, *and* WAF blocks in one sorted timeline. **That is the entire point of the project.**

### Correlation — *kept, core, built in Phase 2 (Module 2 "The Brain")*

The `correlator` service runs every 30 s and does:

1. **Temporal grouping** — sliding 5-minute window per source IP / target / user. Multiple events → one `incident_id`.
2. **Entity resolution** — same actor across sources: the IP that brute-forced SSH (Wazuh) is the same IP the WAF blocked just now (ModSecurity) is the same IP the firewall keeps logging (iptables) → all merged into one incident.
3. **Cross-source kill-chain assembly** — the correlator can output: "incident #4711 = port scan (Suricata) → SSH brute force (Wazuh) → successful auth (Wazuh) → SQL probe (WAF) → outbound C2 (firewall)" — a single timeline an analyst can read in 10 seconds.
4. **MITRE ATT&CK tagging** on each event using Wazuh's built-in rule-to-technique mapping + a static SIGMA-tagged mapping for non-Wazuh sources.
5. **Auto-enrichment** with free threat intel (see Section 1) — every IP / hash / CVE gets context attached.
6. **Runbook attachment** — based on ATT&CK technique, the correlator attaches the relevant runbook ID to the incident.

### False positive handling — *kept, core, built in Phase 4 (Module 2 part B)*

Three layers, in order of trust:

**Layer 1 — Whitelist (deterministic, instant):**
- IP allowlist: internal scanners (Nessus, Tenable, Nmap from your security team), monitoring, backup servers
- Process allowlist: known-good binaries (Wazuh agent itself, monitoring agents, scheduled cron jobs)
- User allowlist: service accounts, known automation accounts
- Time-window allowlist: scheduled-scan windows (e.g. "every Tuesday 02:00–04:00 UTC, suppress port-scan alerts from internal scanner")
- Defined in `config/whitelist.yml` — version-controlled, easy to audit

**Layer 2 — Analyst feedback FP classifier (sklearn, learns from you):**
- Every alert in the UI has a "False positive" button (1-click)
- Click → feature vector appended to SQLite (`tr1nity-feedback.db`)
- Features: rule_id, rule_level, asset_criticality, source_geo_country, source_asn_reputation, time_of_day_bucket, day_of_week, is_internal_source, count_of_similar_alerts_last_24h, has_threat_intel_match, mitre_tactic
- A scikit-learn `RandomForestClassifier` retrains weekly via cron (`make retrain`)
- Inference: every new alert gets a `fp_score` (0.0–1.0) attached
- Dashboard auto-sorts by `fp_score` ascending so analysts see real threats first

**Layer 3 — Suppression rules (analyst-authored):**
- Analyst clicks "always suppress alerts matching: rule X + source ASN Y"
- Generates a YAML suppression rule reviewed by another analyst (or auto-applied if solo)
- Lives in `config/suppressions.yml`, hot-reloaded by `correlator`

**Result:** raw Wazuh+firewall+WAF noise of ~10,000 events/day → ~50 actionable incidents in the analyst queue.

**This stack — log unification + correlation + 3-layer FP handling — is what makes TR1NITY worth building. It's built first, it's tested first, it's the README's headline feature.**

---

## SECTION 1 — Free-only API & service audit (proof nothing costs money)

I went through every external integration in the scope and confirmed each has a usable free tier, OR is replaceable with a free alternative. **No paid API is required, period.**

| Service | Used for | Free tier capacity | TR1NITY's fit |
|---------|----------|--------------------|----------------|
| **AbuseIPDB** | IP reputation lookup | 1,000 IP checks/day, 100 block checks/day, **free forever, no CC required** | ✅ Sufficient. Aggressive caching: same IP queried within 24 h returns cached result. With dedup, 1,000/day covers ~5,000–10,000 unique alerts. |
| **AlienVault OTX** | IOC pulse subscription, IP/domain/hash reputation | Free, no daily limit (rate-limited per minute), free account | ✅ Primary IP/domain/hash enrichment source. |
| **NVD CVE API v2** | CVE descriptions + CVSS scores | Free, **no auth = 5 req per 30 s, with free API key = 50 req per 30 s** | ✅ Free API key is enough. Cache aggressively (CVE descriptions don't change). |
| **MITRE ATT&CK STIX** | 835 techniques + tactics + groups + software | Free, static JSON download from MITRE GitHub | ✅ Download once, ship in container, refresh quarterly. |
| **SigmaHQ rules** | 3,000+ community detection rules | Free, MIT/DRL license, GitHub repo | ✅ Git submodule, refresh on demand. |
| **MISP community feeds** | IOC feeds (CIRCL, Botvrij, etc.) | Many feeds are public, free, served as JSON/CSV | ✅ TR1NITY pulls feeds, indexes locally. No MISP server required. |
| **MalwareBazaar (abuse.ch)** | Malware sample hash lookup | Free public API | ✅ File-hash enrichment. |
| **URLhaus (abuse.ch)** | Malicious URL feed | Free public API | ✅ URL/domain enrichment. |
| **ThreatFox (abuse.ch)** | IOC feed | Free public API | ✅ Hash/IP/domain enrichment. |
| **GeoIP** | IP → country/city/ASN | **MaxMind GeoLite2** is free with monthly auto-update | ✅ Self-hosted DB; ships in container. |
| **Foundation-Sec-8B-Q4_K_M** | Security-specialized LLM | Free, Apache 2.0, runs locally via llama.cpp | ✅ No API cost; runs on your RX 590. |
| **VirusTotal** | File hash reputation (optional bonus) | Free tier: 4 requests/min, 500/day, **free public API key** | ⚠️ Optional. Off by default. Users can supply their own free key. |
| **Wazuh** | HIDS, agent, manager, indexer, dashboard | Free, GPLv2, no enterprise license | ✅ Foundation. |
| **OpenSearch** | Bundled with Wazuh | Free, Apache 2.0 | ✅ |
| **Filebeat / Logstash** | Log shipping | Free (Elastic License v2 or Apache for OSS variants) | ✅ Filebeat only; Logstash dropped (RAM). |
| **scikit-learn / pandas / numpy / FastAPI / React** | All stack libraries | All free, all OSS | ✅ |
| **Ollama / llama.cpp** | LLM runtime | Free, MIT | ✅ |
| **ChromaDB** | RAG vector store | Free, Apache 2.0, runs in-process | ✅ |
| **Docker / Docker Compose** | Containerization | Free for personal/individual & small teams | ✅ |
| **GitHub Actions** | CI/CD | Free for public repos: **2,000 min/month, unlimited storage** for releases | ✅ |
| **Docker Hub / GHCR** | Image registry | Docker Hub: free 1 GB / unlimited pulls; **GHCR: unlimited storage for public images** | ✅ Use GHCR (free unlimited for public). |
| **Sentry / Grafana / Prometheus** (optional ops monitoring) | Self-monitoring | Self-hosted = free | ✅ Optional in v1.5. |

**Net: zero recurring cost.** The most "expensive" thing in TR1NITY's external dependency tree is your home electricity bill running the desktop PC.

### What if AbuseIPDB's 1,000/day isn't enough?

Cache hit-rate analysis: a typical home/lab environment sees the same ~50–200 unique source IPs across 10,000 events/day (most events repeat from the same scanner ASNs). With 24 h caching, **expected daily AbuseIPDB calls: ~50–200**. You will not hit the limit. If a user's environment has more, the correlator gracefully falls back to OTX-only enrichment for that IP.

---

## SECTION 2 — GitHub storage strategy (how 30 GB stays under 100 MB)

GitHub's hard rules (verified from docs.github.com):
- **Single file warning at 50 MiB**, hard reject at **100 MiB**.
- Recommended `.git/` size **≤ 10 GB** for repo health.
- **GitHub Releases**: binary assets up to ~2 GB each, **unlimited storage**, unlimited bandwidth on public repos.
- **GitHub Container Registry (GHCR)**: **unlimited free storage for public images**.
- **Git LFS free tier**: 1 GB storage + 1 GB bandwidth/month — too small for our datasets.

### What goes WHERE

```
Total local disk on your PC:           ~30 GB
├─ The TR1NITY repo (`.git` + source)   ~50 MB    ← what gets `git push`ed
├─ User-downloaded datasets             ~10 GB    ← NOT in repo
├─ Trained ML models (pickle)           ~150 MB   ← Releases asset
├─ Foundation-Sec-8B Q4 GGUF            ~5 GB     ← user pulls via Ollama, NOT in repo
├─ MITRE ATT&CK STIX                    ~40 MB    ← in repo (git submodule from MITRE)
├─ SigmaHQ rules                        ~15 MB    ← git submodule from SigmaHQ
├─ GeoLite2 DB (city)                   ~70 MB    ← downloaded by setup script (license restriction)
├─ Docker images cached                 ~10 GB    ← user pulls from GHCR
├─ OpenSearch indices (over time)       ~5–10 GB  ← user-generated
└─ Ollama model cache                   ~5 GB     ← user-pulled
```

### IN the repo (the only things `git push`ed):

```
tr1nity/                                     ~50 MB total, comfortably under all limits
├── .github/
│   └── workflows/                           CI: lint, test, build images, push to GHCR
├── .gitignore                               aggressive: data/, models/, .venv/, node_modules/
├── .gitattributes                           LFS for icons/images >1MB only
├── README.md                                ~15 KB
├── ARCHITECTURE.md                          ~30 KB
├── LICENSE                                  MIT
├── docker-compose.yml                       single source of truth
├── docker-compose.demo.yml                  demo profile (mock LLM, sample data)
├── docker-compose.full.yml                  full AI mode (Ollama enabled)
├── .env.example                             no real secrets ever
├── Makefile                                 install / start / stop / retrain / backup / demo-attack
├── pyproject.toml                           Python deps for all services
├── services/
│   ├── ingestor/                            ~2,000 LOC Python
│   ├── correlator/                          ~3,000 LOC Python
│   ├── ai-assist/                           ~1,500 LOC Python
│   └── api/                                 ~2,000 LOC Python
├── ui/                                      React app source only (NOT node_modules, NOT dist/)
│   ├── src/                                 ~5,000 LOC TS/TSX
│   ├── package.json
│   └── vite.config.ts
├── config/
│   ├── tr1nity.yml                          all thresholds, paths, retention
│   ├── whitelist.yml                        FP whitelist
│   ├── suppressions.yml                     analyst-authored
│   └── runbooks/                            ~15 markdown files, ~500 KB total
├── docker/
│   ├── ingestor.Dockerfile
│   ├── correlator.Dockerfile
│   ├── ai-assist.Dockerfile
│   └── api.Dockerfile
├── scripts/
│   ├── download_datasets.sh                 fetches CICIDS/UNSW from official mirrors
│   ├── download_geolite.sh                  fetches MaxMind GeoLite2 with user's free license key
│   ├── train_fp_classifier.py               one-shot training script
│   ├── seed_attack.py                       synthetic attack-chain demo
│   └── ingest_sigmahq.py                    pull + translate SIGMA rules
├── extern/
│   ├── attack-stix-data/                    git submodule → mitre-attack/attack-stix-data
│   └── sigma/                               git submodule → SigmaHQ/sigma
├── tests/                                   pytest, integration tests with synthetic alerts
└── docs/                                    MkDocs site source
```

### NOT in the repo (distributed via other channels):

| Artifact | Size | Where it lives | How users get it |
|----------|------|-----------------|-------------------|
| **Docker images** (4 services + bundled) | ~10 GB | GHCR (`ghcr.io/<your-user>/tr1nity-*`) | `docker compose pull` |
| **Trained FP classifier `.pkl`** | ~50 MB | GitHub Release asset | `make pull-models` (or auto on first run) |
| **CICIDS2017 sample (10% subset)** | ~800 MB | GitHub Release asset (under the 2 GB limit) | `make download-data` |
| **CICIDS2017 full** | ~8 GB | NOT distributed by you. `scripts/download_datasets.sh` fetches from UNB's official URL. | Run script. |
| **UNSW-NB15** | ~2 GB | Same — `download_datasets.sh` fetches from UNSW. | Run script. |
| **Foundation-Sec-8B Q4 GGUF** | ~5 GB | NOT yours to redistribute. Reference Ollama model name in config. | `ollama pull fdtn-ai/foundation-sec-8b-instruct:Q4_K_M` |
| **MaxMind GeoLite2 DB** | ~70 MB | License requires per-user download. `scripts/download_geolite.sh` uses user's free license key. | One-time setup. |
| **Demo synthetic alerts** | ~2 MB | In repo (`tests/fixtures/`) | Already there. |

### `.gitignore` (the critical safety net)

```gitignore
# Data
data/
datasets/
*.csv
*.parquet
*.pcap

# Models / artifacts
models/
*.pkl
*.gguf
*.bin
*.safetensors

# Local secrets / config
.env
.env.local
config/local-*.yml

# Build outputs
ui/dist/
ui/node_modules/
**/__pycache__/
**/*.pyc
.venv/
venv/
build/
dist/

# OS / IDE
.DS_Store
.idea/
.vscode/

# Wazuh / OpenSearch local state
volumes/
ossec-data/

# Logs / DBs
*.log
*.sqlite
*.db
```

### Bonus — pre-commit hook to enforce repo size

Add a `pre-commit` hook that rejects any single file > 10 MB. Cheap insurance against accidentally committing a CSV.

### Final repo size projection at v1.0 launch

```
.git/ size:    ~80 MB        (well under 10 GB recommended ceiling)
Working tree:  ~50 MB        (no file > 10 MB)
LFS usage:     0             (no LFS at all — keep it simple)
Total push:    ~50 MB
```

This is a **healthy, fast-cloning repo**. New contributors clone in <30 seconds.

---

## SECTION 3 — Step-by-step build pathway

**Total duration:** 16 weeks at ~10–15 h/week (solo + day-job realistic). 10 weeks if full-time.
**Phase rule:** every phase ends with a *demo command* you can run that produces visible output. No phase ends with "still working on it."

I'll go granular for **Weeks 1–4** (where you're most likely to get stuck or lose motivation), then phase-level for the rest.

### Phase 0 — Repository foundation (Week 1)

The boring week. Skip it and you'll regret it in week 8.

**Day 1 — Create repo, license, README skeleton**
- Create `tr1nity` repo on GitHub, public, MIT license
- Commit `README.md` with project headline + architecture diagram placeholder + "Status: pre-alpha"
- Commit `ARCHITECTURE.md` (paste from this doc, refine over time)
- Commit `.gitignore`, `.gitattributes`, `.editorconfig`
- Push initial commit, tag `v0.0.0-init`

**Day 2 — Docker Compose skeleton**
- Create `docker-compose.yml` with: `wazuh-manager`, `wazuh-indexer`, `wazuh-dashboard`, `postgres` services, all stock images
- Configure `wazuh-indexer` with `OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g` (RAM cap)
- Run `docker compose up`, verify Wazuh dashboard loads at `http://localhost:5601`
- Write a `Makefile` with `make up`, `make down`, `make logs`, `make ps`
- Commit, push

**Day 3 — Service skeletons**
- Create `services/ingestor/`, `services/correlator/`, `services/ai-assist/`, `services/api/` directories
- Each: minimal FastAPI app with `/health` endpoint, `pyproject.toml`, `Dockerfile`
- Single shared `pyproject.toml` at repo root using `uv` or `poetry` workspaces
- Add the 4 services to `docker-compose.yml`, hello-world only
- `make up`, hit each `/health`, confirm 200 OK
- Commit, push

**Day 4 — CI**
- `.github/workflows/ci.yml`: on PR, run `ruff`, `mypy`, `pytest` (empty for now)
- `.github/workflows/build-images.yml`: on tag, build + push images to `ghcr.io/<user>/tr1nity-*`
- Add `pre-commit` hooks: `ruff`, `black`, file-size-check (10 MB max)
- Confirm CI green
- Commit, push

**Day 5 — Configuration system**
- Create `config/tr1nity.yml` with sample config (thresholds, paths, retention, FP thresholds)
- Pydantic-settings model in `services/api/config.py` that loads it
- Mount config via volume in docker-compose
- Each service reads its slice of config
- Commit, push

**Day 6–7 — Documentation site + buffer**
- Set up MkDocs in `docs/`
- First page: "What is TR1NITY?"
- Second page: "Architecture"
- Third page: "Hardware Requirements" (your 16 GB profile)
- GitHub Pages auto-deploy via Actions
- Buffer for whatever broke during Day 1–5
- Tag `v0.1.0-foundation`

**End of Phase 0 demo command:** `make up && curl localhost:5601 && curl localhost:8080/health`

---

### Phase 1 — Multi-source ingestion (Weeks 2–3) *[YOUR EXPLICIT REQUEST: unified Wazuh + firewall + WAF logs]*

**Week 2, Day 1–2 — Wazuh integration**
- Configure Wazuh agent on a test VM (or your laptop)
- Wazuh manager auto-writes to `wazuh-indexer`, index `wazuh-alerts-*`
- Verify alerts appear in Wazuh dashboard
- In `services/ingestor/`: build webhook receiver `POST /ingest/wazuh` that *also* receives Wazuh integrations output for richer context
- Define the unified ECS schema as Pydantic model in `services/ingestor/schema.py`
- Write `wazuh_to_ecs()` mapper

**Week 2, Day 3–4 — Firewall log ingestion**
- Set up syslog receiver in `ingestor` (Python `aiosyslogd` or build on `socketserver`) on UDP 514
- Parse iptables log format (regex)
- Parse pfSense filterlog format
- Map to ECS schema: `event.module=iptables`, `event.dataset=firewall.deny`, etc.
- Write to `tr1nity-events-*` index in OpenSearch
- Test: `logger -p local0.info "iptables: IN=eth0 SRC=1.2.3.4..."` from a test box

**Week 2, Day 5–7 — WAF log ingestion**
- Spin up a test ModSecurity (Nginx + CRS) container as the "monitored WAF"
- Configure ModSecurity to log JSON to `/var/log/modsec_audit.log`
- Add Filebeat container that tails the WAF log and forwards to `ingestor` via Logstash format → JSON
- Or simpler: ModSecurity → syslog → ingestor (same path as firewall)
- Parse CEF/JSON, map to ECS schema: `event.module=modsecurity`, `event.dataset=waf.block`
- Write to `tr1nity-events-*` index
- Test by running `curl -d "../../etc/passwd" http://localhost/test` against test WAF, confirm event lands in OpenSearch

**Week 3, Day 1–2 — Unified search verification**
- In Wazuh dashboard, create a single index pattern `tr1nity-events-*` covering all three sources
- Verify: query for `source.ip:1.2.3.4` returns Wazuh + firewall + WAF events together, sorted by time
- **This is the moment Section 0's promise is real.** Take a screenshot for the README.

**Week 3, Day 3–4 — Index lifecycle management**
- Configure ISM (Index State Management) policy: hot 7 days, warm 30 days, cold (close) at 90 days, delete at 180 days
- Apply to `tr1nity-events-*`
- This prevents your 500 GB SSD from being silently eaten over 6 months

**Week 3, Day 5–7 — Tests + docs + buffer**
- Pytest fixtures with sample Wazuh/iptables/ModSecurity payloads
- Test `wazuh_to_ecs()`, `iptables_to_ecs()`, `modsec_to_ecs()`
- Docs page: "Configuring your firewall to send logs to TR1NITY"
- Docs page: "Configuring ModSecurity to log to TR1NITY"
- Tag `v0.2.0-ingest`

**End of Phase 1 demo command:** `make demo-ingest` — ships sample Wazuh + iptables + ModSec events, all three appear in the same OpenSearch query.

---

### Phase 2 — The Brain: correlation + enrichment + ATT&CK + SIGMA (Weeks 4–7) *[YOUR EXPLICIT REQUEST: correlation]*

**Week 4 — Correlation core**
- `services/correlator/main.py`: async loop, polls OpenSearch every 30 s for events in last 5 min not yet assigned to incident
- Implement temporal grouping algorithm:
  - Group by `source.ip` within 5-min sliding window → candidate incident
  - Merge if same `destination.ip` or same `user.name`
  - Generate stable `incident_id` (UUID v5 hashed from earliest event)
- Write back to OpenSearch: each event gets `tr1nity.incident_id` field
- Create new index `tr1nity-incidents-*` storing one document per incident with: list of event IDs, earliest/latest timestamps, source IPs, target hosts, summary stats
- Pytest: fan-in 50 synthetic events from Wazuh+firewall+WAF for the same source IP, expect 1 incident

**Week 5 — Entity resolution + ATT&CK tagging**
- Entity resolution: build a normalizer that knows IP → ASN/geo, user → email/domain. Same-entity events merge across sources.
- ATT&CK tagging:
  - Wazuh events: read `rule.mitre.id` field (Wazuh provides this natively)
  - Firewall events: regex/heuristic mapping (e.g. multiple denies from same IP → T1046 Network Service Scanning)
  - WAF events: map ModSecurity rule IDs to ATT&CK techniques (CRS rules already have category metadata)
- Tag both event docs and incident docs

**Week 6 — Threat-intel enrichment**
- `enrichment/abuseipdb.py`: client with 24 h Redis-cache (or in-process LRU)
- `enrichment/otx.py`: OTX pulse + indicators API
- `enrichment/nvd.py`: CVE lookup with API key, indefinite cache
- `enrichment/abusech.py`: MalwareBazaar / URLhaus / ThreatFox
- `enrichment/geoip.py`: MaxMind GeoLite2 local DB
- Correlator calls these for every new incident, attaches results to the incident doc as `tr1nity.threat_intel.*`
- Rate-limit budget: stay under 1,000 AbuseIPDB calls/day with the 24 h cache

**Week 7 — SIGMA rule import + deploy + test**
- Add `extern/sigma` as git submodule → all SigmaHQ rules
- `scripts/ingest_sigmahq.py`: walks all `.yml` rules, parses with `pysigma`, translates to OpenSearch DSL, stores in `tr1nity-rules-*`
- `correlator` runs each rule periodically against last-N-minutes of events, generates derived alerts
- API endpoint `POST /rules/{id}/test` runs a SIGMA rule against a date range to estimate FP rate before deploy
- Tag `v0.3.0-brain`

**End of Phase 2 demo command:** `make demo-attack` — synthetic attack chain (port scan → brute force → WAF exploit → outbound C2) injected as Wazuh+firewall+WAF events; output is **one incident** with all 4 stages, correctly correlated, ATT&CK-tagged, threat-intel-enriched, in Wazuh dashboard / a temp UI.

---

### Phase 3 — The Cockpit: React analyst UI (Weeks 8–11)

**Week 8 — UI foundation**
- `npm create vite@latest ui -- --template react-ts`
- Add Tailwind, shadcn/ui, react-router, tanstack-query, zustand
- Theme: dark mode by default, light toggle
- Layout: left sidebar (queue), main panel (investigation), top bar (search + user)
- `services/api/`: REST endpoints `GET /alerts`, `GET /incidents`, `GET /incident/{id}`, `WS /events`

**Week 9 — Alert queue + filters**
- Alert queue: server-side paginated, sort by FP score asc / priority desc / age
- Filters: ATT&CK tactic, source (Wazuh/Firewall/WAF), priority, has-threat-intel-match
- WebSocket pushes new incidents in real-time
- Keyboard shortcuts: `j`/`k` next/prev, `o` open, `f` mark FP, `c` create case

**Week 10 — Investigation panel**
- Single-screen design (this is the killer feature):
  - Top: incident summary + ATT&CK tags + priority badge
  - Left tab: raw event list (chronological, expandable JSON)
  - Right sidebar: enrichment (threat intel / asset / identity / GeoIP) + entity timeline last 30d + similar-incidents (semantic search)
  - Bottom: comments / case status / runbook link
- Implement "similar past incidents" — use ChromaDB to embed every closed case and search by IOC overlap

**Week 11 — ATT&CK heatmap + lightweight case management**
- Embed MITRE ATT&CK Navigator (open-source)
- Color cells by detection coverage: green (covered by deployed SIGMA + Wazuh rule), yellow (covered, no recent test), red (uncovered)
- Click cell → see incidents under that technique
- Case management UI: create case → attach incidents → assign → status → resolve with markdown post-mortem
- Audit trail: every action logged
- Tag `v0.4.0-cockpit`

**End of Phase 3 demo command:** `make up && open http://localhost:8080` — full analyst workstation usable, all features visible.

---

### Phase 4 — FP feedback + runbooks (Weeks 12–13) *[YOUR EXPLICIT REQUEST: FP handling]*

**Week 12 — FP feedback loop (the 3-layer system from Section 0)**
- Whitelist YAML loader (`config/whitelist.yml`): hot-reload on change
- 1-click "Mark FP" button in UI → POST to `/api/feedback/fp` → SQLite
- Feature extractor: 12 features per alert (rule_id, level, asset_crit, geo, asn, time_bucket, day_of_week, internal_src, dedup_count_24h, has_ti_match, mitre_tactic, src_age_days)
- Train initial FP classifier on bootstrap data (synthetic + first analyst sessions)
- `make retrain` command: re-fits model, atomic pickle swap
- Cron-style trigger: weekly retrain
- Inference: every new event scored, `fp_score` written to OpenSearch

**Week 13 — Runbooks + suppression rules**
- `config/runbooks/`: 15 markdown runbooks (brute force, web exploitation, lateral movement, ransomware, credential theft, data exfil, C2, privilege esc, SQLi, XSS, port scan, DDoS, malware execution, insider threat, account compromise)
- Each runbook front-matter has `mitre_techniques: [Txxxx, Txxxx]` for auto-attach
- Correlator attaches `tr1nity.runbook_id` to each incident based on dominant ATT&CK technique
- UI shows runbook in collapsible panel inside investigation view
- Suppression rule editor: analyst clicks "always suppress matching: rule X + ASN Y" → writes to `config/suppressions.yml`
- Tag `v0.5.0-feedback`

**End of Phase 4 demo command:** mark 50 alerts as FP via UI, run `make retrain`, observe `fp_score` distribution shift on a held-out sample.

---

### Phase 5 — AI Assist (async, HITL) (Weeks 14–15)

**Week 14 — Local LLM serving**
- Build llama.cpp with Vulkan backend on the Ryzen 7 / RX 590 PC:
  ```
  cmake -B build -DGGML_VULKAN=ON
  cmake --build build --config Release
  ```
- Pull `Foundation-Sec-8B-Instruct-Q4_K_M.gguf` (~5 GB) — store in `~/.cache/llama` outside the repo
- Run `llama-server --model foundation-sec-8b-q4_k_m.gguf --n-gpu-layers 32 --port 8081`
- Benchmark: target ≥15 tok/s on Vulkan. Fall back to CPU if Vulkan path fails (Polaris is unofficial in ROCm but Vulkan should work)
- `services/ai-assist/main.py`: FastAPI service that proxies to llama-server, queue-backed (Redis or in-process asyncio.Queue)

**Week 15 — RAG + drafting endpoints**
- Build ChromaDB store, in-process: ingest MITRE ATT&CK descriptions + 5 years of NVD CVE summaries + SigmaHQ rule descriptions + your runbooks
- Endpoints (all async, HITL):
  - `POST /draft/incident-report` — input: incident_id → draft post-mortem markdown
  - `POST /draft/runbook` — input: ATT&CK technique → draft new runbook
  - `POST /explain/cve` — input: CVE ID → plain-English explanation grounded in NVD
  - `POST /explain/alert` — input: alert_id → optional plain-English summary (collapsed by default in UI)
- UI: every draft endpoint result lands in a "Drafts" review queue. Analyst edits → saves → audit trail records both LLM output and analyst edit (for future training)
- `MOCK_LLM=true` env var: returns deterministic templated responses, no GPU/CPU LLM needed
- Tag `v0.6.0-ai`

**End of Phase 5 demo command:** `make demo-ai` — closes a sample case, AI drafts the post-mortem, user reviews and accepts.

---

### Phase 6 — Knowledge, reporting, polish, launch (Week 16)

- **Compliance reports**: WeasyPrint templates for PCI-DSS, ISO 27001, NIST CSF
- **Weekly metrics report**: alert volume, FP rate, MTTR, top-firing rules, top-tuned rules, ATT&CK coverage delta — auto-generated Monday 06:00 UTC
- **Backup/restore**: `make backup` tarballs feedback DB + cases + runbooks + ML models + SIGMA edits + suppressions
- **README polish**: GIF showing demo-attack → incident → analyst investigation → case closure in 90 seconds. Architecture diagram. Hardware profiles table. Quickstart "5 minutes from clone to running."
- **`docker compose up` from clean checkout must work without errors on a fresh Ubuntu 22.04 VM with 16 GB RAM.** Test this on a clean VM before tagging.
- **Demo video on YouTube** (5–7 min)
- **Launch posts**: r/cybersecurity, r/blueteamsec, r/sysadmin, Hacker News (Show HN), dev.to, LinkedIn
- **Tag `v1.0.0`**

---

## SECTION 4 — The first command you should run today

If you want to start immediately, this is the literal first command:

```bash
mkdir -p ~/projects && cd ~/projects
gh repo create tr1nity --public --license MIT \
  --description "Open-source unified SIEM correlation platform for Wazuh, firewall, and WAF logs"
cd tr1nity
git init
echo "# TR1NITY" > README.md
echo "Open-source unified SIEM correlation platform." >> README.md
git add . && git commit -m "init"
git remote add origin git@github.com:<your-username>/tr1nity.git
git push -u origin main
```

Then start Day 2 of Phase 0.

---

## SECTION 5 — The motivation rule

Every Phase ends with a **demo command**. If a phase drags past its planned weeks, you ship a partial demo command anyway and move on — you can come back. **The worst outcome is a perfect Phase 2 with no Phase 3, 4, 5, 6.** Cadence beats perfection. Tag a release at the end of every phase, no matter how rough.

You're building a tool real analysts will install on a Friday and still be using on Monday. That requires shipping. Build the brain (correlation + FP), build the cockpit (UI), and you have something real before week 12 even ends. Everything else is multiplication on top.

This is the complete pathway.
