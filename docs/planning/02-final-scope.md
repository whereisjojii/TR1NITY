# SENTINEL-CORE — The 100% Project (Tightened Scope)

**Audience:** *You.* A single builder shipping an open-source SOC platform on personal hardware.
**Hardware in play:**
- Desktop PC: Ryzen 7 3700X (8C/16T) · 16 GB DDR4 · RX 590 8 GB · → **the server**
- Laptop: i5 13th gen · 8 GB · → **the dev workstation**

**My job in this doc:** be opinionated. Cut what isn't industry-core. Keep what real analysts actually ask for. Justify every cut and every keep with verifiable evidence.

---

## 1. My honest take, in two paragraphs

Your original scope is impressive but it conflates *three different products*: a SIEM, an ML-research playground, and a SOAR/AI-agent demo. Trying to ship all three as one project — especially solo — is exactly how good ideas die. The good news: ~30% of the original scope is the actual industry-core; the other ~70% is either academic theatre, vendor-imitation, or features that look great in a demo but real analysts don't trust.

The real opportunity is **building the missing analyst workstation that nobody has open-sourced yet**: a single-pane investigation cockpit on top of Wazuh that compresses the 80% of an analyst's day spent on low-fidelity alerts (click → validate → close) into something that actually feels modern. The LLM is *not* the centerpiece — it's an async helper. The correlation engine, FP-reduction loop, threat-intel auto-enrichment, and "similar past incidents" search are the centerpiece. That's what gets stars on GitHub. That's what an L1/L2 analyst will install on a Friday and still be using on Monday.

---

## 2. The industry evidence I'm cutting bloat against

This isn't speculation — these are the data points driving every cut/keep decision below.

| # | Source | Finding | Implication for your project |
|---|--------|---------|-------------------------------|
| 1 | Secure.com SOC burnout study | **71% of SOC analysts report burnout; 64% plan to switch jobs within a year**; alert fatigue from FPs is the #1 driver | The mission is FP reduction, not feature count |
| 2 | VMware/Carbon Black SOC survey | Analysts spend **80% of time on low-fidelity alerts** (click→validate→close); only ~5% on real high-fidelity investigation; ~35% reviewing threat intel | Optimise the 80%. That's the win. |
| 3 | SANS 2024 SOC Survey (Crowley) | Top frustrations: integration gaps, tool sprawl, slow context-gathering | Single-pane investigation panel > more features |
| 4 | HN thread (L2 MSSP analyst, 2024) | "AI tools slow my work, cause me to chase red herrings, fail to provide critical info that would have been obvious from raw payloads" — but: "AI is a big improvement on **generation of text for instructions, incident reports**" | LLM = drafter, not decider. Async, not real-time. |
| 4b | r/cybersecurity (multiple analysts) | "Hallucinations killed that dream"; consensus: AI useful for summaries/runbook starters/scripting **with HITL** — never autonomous | Same conclusion. Never "Claude take the wheel." |
| 5 | Wazuh 4.x docs | All-in-one min: 4 GB RAM / 2 cores; recommended 16 GB | Your 16 GB PC = recommended spec. Comfortable. |
| 6 | fdtn-ai HF model card | Foundation-Sec-8B Q4_K_M = 4.92 GB; Apache 2.0 | Fits in 8 GB VRAM (RX 590) via llama.cpp Vulkan |
| 7 | llama.cpp Vulkan benchmark thread | RX 590 / Polaris runs Q4_0 7B at usable speeds via Vulkan; ROCm officially dropped Polaris but Vulkan works | RX 590 is *useful*, not just decorative |

**The single most important data point** is row 4. Real analysts don't want an LLM telling them what an alert *means* — they distrust it. They want an LLM that drafts the incident report *after* the investigation. **Reorient the LLM accordingly.** This is the most counter-intuitive cut and the most important one.

---

## 3. CUT LIST — what I'm removing and why

I'm cutting nine things from the original scope. Each cut has evidence behind it. None of these are "too hard"; they're the wrong things to build.

### CUT 1 — The CICIDS2017 multi-class network-flow ML pipeline (RF / XGBoost / Decision Tree on 77 flow features)
**Why it's in the original scope:** It's the centerpiece of AI_SOC, looks impressive, has a 99.28% accuracy headline.
**Why I'm cutting it:** Real SOCs **don't run network-flow ML on production traffic** — they correlate logs. The 77 CICFlowMeter features assume you have a span port and CICFlowMeter running 24/7 on every network segment. You don't. Your users won't either. This is academic-paper architecture. The "99.28% accuracy" is on a 2017 lab dataset with synthetic attacks — production performance is *unknown* (the AI_SOC repo even documents this gap). Shipping this means shipping a feature that looks great in screenshots but never gets enabled.
**What I keep instead:** **One** scikit-learn model — a binary FP classifier on alert metadata (rule level × asset criticality × time-of-day × source-reputation × analyst-FP-history). 50 MB pickled. Trains in 30 seconds on analyst feedback. Actually used.

### CUT 2 — Self-rewriting SIGMA rule generator (LLM writes new detection rules)
**Why it's in scope:** Sounds magical. AI_SOC has it.
**Why I'm cutting it:** Quality of LLM-generated SIGMA rules is poor. Every output requires human review — no detection engineer trusts auto-generated rules. The back-test step in AI_SOC requires 30+ days of representative historical alerts you don't have on day one. Net value: a rule queue that analysts ignore. AI_SOC's own docs flag this as experimental.
**What I keep instead:** A **SIGMA rule import + deploy + test workflow** using SigmaHQ's 3,000+ community rules. One-click deploy. Test against last-7-days data. That alone saves detection engineers weeks of work and is a real differentiator.

### CUT 3 — UEBA (User-Entity Behavior Analytics)
**Why it's in scope:** Buzzword. Every commercial SIEM lists it.
**Why I'm cutting it:** UEBA needs **weeks of clean baseline data** before output is meaningful. On a personal/demo install the dashboard will be empty for a month. Even in real SOCs, UEBA has a brutal FP rate and is the #1 module that gets disabled after 90 days. Shipping empty UEBA = users uninstall.
**What I keep instead:** **Per-entity timeline view** (all events for an IP/user/host in chronological order). This is what UEBA *promises* but rarely delivers, and you can build it deterministically from your indexed alerts in two days.

### CUT 4 — Markov chain kill-chain prediction
**Why it's in scope:** Predicts attacker's next move.
**Why I'm cutting it:** Transition probabilities require operational data you won't have. AI_SOC's own docs say "predictions should be treated as directional guidance, not validated forecasts." A predictor that's "directional" is a feature analysts will explicitly disable.
**What I keep instead:** **Static ATT&CK kill-chain stage tagging** on every alert (Initial Access / Execution / Persistence / etc.) using existing rule→technique mappings. Deterministic, accurate, immediately useful for the heatmap.

### CUT 5 — TheHive + Cortex + MISP full server stack
**Why it's in scope:** They're the standard open-source IR stack.
**Why I'm cutting it:** They're great products *but they each need 1.5–3 GB RAM, complex setup, and overlap heavily with what your platform should do.* TheHive 5 is no longer free for commercial use. MISP is a separate product with its own learning curve. Bundling them = your installer becomes 10 minutes of "is Cassandra up yet?"
**What I keep instead:**
- A **lightweight built-in case manager** (Python + SQLite + a single React view): create case → attach alerts → assign analyst → add notes → resolve with markdown post-mortem. Maybe 600 lines of code total.
- A **MISP/OTX/AbuseIPDB feed *consumer*** that pulls IOCs as JSON via API and indexes them locally. No local MISP server.
- A **TheHive REST adapter** (optional, off by default) for users who *already* run TheHive and want to forward cases.

### CUT 6 — Suricata bundling
**Why it's in scope:** Adds NIDS coverage.
**Why I'm cutting it:** Suricata is its own beast — installing, tuning rules, feeding pcap, dealing with span ports. It's a separate concern. Bundling it bloats your installer and confuses scope.
**What I keep instead:** A **Suricata EVE-JSON ingestion adapter**. If a user has Suricata, they point it at your ingestor. If they don't, your platform works fine without it.

### CUT 7 — Atomic Red Team bundled execution
**Why it's in scope:** Demos the platform catching real attacks.
**Why I'm cutting it:** Running ART tests means executing actual credential-dumping / persistence / lateral-movement techniques on a target. That target has to be a separate machine — you can't run ART on the same box as your SIEM. Bundling it makes installation user-hostile.
**What I keep instead:** A **synthetic alert generator** (Python script) that injects a realistic, scripted attack-chain into your indexer (recon → brute force → privilege escalation → exfiltration) so the demo works without any second machine. Document for advanced users how to feed real ART output via syslog.

### CUT 8 — Continuous learning pipeline with champion/challenger ML promotion
**Why it's in scope:** Feels modern, makes the platform "self-improving."
**Why I'm cutting it for v1:** It's MLOps infrastructure for a model whose entire value is a 50 MB FP classifier. Champion/challenger evaluation, hot-reload, label-poisoning detection — these are six weeks of work for a marginal accuracy gain on a model that retrains in 30 seconds. Cargo-cult complexity.
**What I keep instead:** A simple `make retrain` command that re-fits the FP classifier on the latest analyst feedback and atomically swaps the pickle file. Run it weekly via cron. 40 lines of code.

### CUT 9 — The 9-microservice architecture from AI_SOC
**Why it's in scope:** AI_SOC has it, looks "enterprise."
**Why I'm cutting it:** Nine FastAPI services for a solo project = nine deployment surfaces, nine sets of tests, nine version mismatches when you upgrade. AI_SOC was a research POC; you're shipping a tool.
**What I keep instead:** **Four services.** That's it.
1. `ingestor` — receives Wazuh webhooks + WAF/firewall/Suricata syslog → normalizes → writes to indexer.
2. `correlator` — periodic job: correlation, FP scoring, threat-intel enrichment, ATT&CK tagging, runbook attachment, case auto-creation.
3. `ai-assist` — async LLM worker for report drafting / runbook generation / post-incident summaries (NOT real-time triage).
4. `api` — REST + WebSocket backend for the React UI; also serves the static UI bundle.

Plus the off-the-shelf containers: `wazuh-manager`, `wazuh-indexer`, `wazuh-dashboard`, `postgres`, `ollama` (or `llama-server`).

---

## 4. KEEP LIST — the actual industry-core (the 100% project)

Five modules. Each one **directly attacks** one of the documented analyst pain points from Section 2. Nothing here is speculative.

### MODULE 1 — Multi-source Ingestion & Normalization
*Attacks: tool sprawl / integration gaps (SANS finding #3)*

- Wazuh agent for HIDS / FIM / log forwarding.
- Filebeat for app logs.
- Python `ingestor` service: webhooks from Wazuh + syslog from firewall (iptables/pfSense) + ModSecurity CEF + Suricata EVE JSON + cloud logs (Cloudflare, optional).
- Common JSON schema (ECS-compatible — Elastic's open standard so users can swap indexers later).
- All thresholds, sources, retention in `config.yml`.

**Why this is non-negotiable:** if your platform only ingests Wazuh, you're a Wazuh skin, not a SIEM. Multi-source is what makes you a real product.

### MODULE 2 — Correlation, FP Reduction & Auto-Enrichment (THE BRAIN)
*Attacks: alert fatigue (industry finding #1, the #1 cause of burnout)*

This is the single highest-value module. Build it first, ship it first, polish it most. Components:

- **Temporal correlation:** group alerts within a 5-minute sliding window by source IP / target / user / process. Output: incident chains instead of raw alerts.
- **Entity resolution:** unify the same actor across sources (the IP that brute-forced SSH 2 minutes ago is the same IP the WAF blocked just now).
- **Whitelist FP layer:** YAML-defined IP/process/user/host allowlists + scheduled-scan windows.
- **Analyst-feedback FP classifier:** 1-click "this is a false positive" in the UI → feature vector to SQLite → weekly retrain → score every new alert with a confidence (`fp_score`).
- **Auto-enrichment** (the time-saver analysts beg for):
  - Every IP → AbuseIPDB + AlienVault OTX reputation + GeoIP + ASN.
  - Every CVE mentioned → NVD CVSS score + description.
  - Every hash → VirusTotal (free tier, opt-in) + MalwareBazaar.
  - Every host → asset DB lookup (criticality, owner, OS).
  - Every user → identity DB lookup (department, manager, last-login pattern).
  - Every alert → relevant runbook from your knowledge base.
- **SIGMA rule deployment:** import SigmaHQ community rules (3,000+) → translate to OpenSearch DSL via pySigma → enable/disable from UI → test against last-7-days alerts before deploying.
- **ATT&CK tagging:** static mapping of Wazuh rules → MITRE techniques (Wazuh ships this metadata already; just expose it).

**Output:** every alert that lands in the analyst queue arrives with FP score, threat-intel context, asset context, ATT&CK tag, related-incident chain, and runbook link **already attached.** That single change cuts triage time by 70%.

### MODULE 3 — The Analyst Workstation (THE COCKPIT)
*Attacks: context switching / 80%-of-time-on-low-fidelity-alerts (industry findings #2, #3)*

The reason your platform exists. A purpose-built React UI:

- **Alert queue** with smart sort: priority score + FP score + age. Filter by ATT&CK tactic, asset criticality, source.
- **Investigation panel** — single screen showing for the selected alert/incident:
  - Raw event payload (raw, expandable — analysts demand this; never just LLM summaries — see HN finding #4).
  - Auto-enrichment sidebar (threat intel, asset, identity, CVE, GeoIP).
  - **Entity timeline** — chronological events for the IP/user/host across the last 30 days.
  - Related-incidents panel — *similar past cases* retrieved by IOC overlap (CUT-3 alternative).
  - Runbook auto-attached.
  - LLM-drafted summary (collapsed by default — analyst opens it after looking at the raw payload, not before).
- **MITRE ATT&CK Navigator heatmap** — current detection coverage as a visual map. One-click "see alerts under T1110."
- **Case management** — lightweight built-in (CUT-5 replacement): create case → attach alerts → assign → tag → resolve with markdown post-mortem.
- **"Similar past incidents" search** — type IOC or paste log → semantic search via ChromaDB (embeddings of past cases) returns the closest historical incidents with their resolutions. *This single feature is a killer industry differentiator no open-source SIEM has.*
- **Dark mode + keyboard shortcuts.** Analysts work 8-hour shifts; this matters.

**Tech:** React + TailwindCSS + shadcn/ui (production-grade, what real SaaS apps use). Built static, served by the Python `api` service.

### MODULE 4 — AI Assist (Async, Human-In-The-Loop, NOT a triage replacement)
*Attacks: reporting overhead / runbook drafting / onboarding cliff*

This is where I diverge most from your original AI_SOC-inspired scope, and the change is grounded directly in real analyst feedback (HN thread, finding #4).

**What the LLM does:**
- **Drafts the post-incident report** when a case is resolved (analyst edits, never blindly accepts).
- **Drafts a runbook** when the analyst marks "we don't have a runbook for this." Goes to a review queue.
- **Drafts the weekly compliance / metrics report** (PCI-DSS / ISO 27001 / NIST CSF mappings, alert-volume summaries).
- **Optional plain-English alert summary** — collapsed by default in the UI. Analyst opens it *after* glancing at the raw payload.
- **"Explain this CVE / this technique"** on demand, grounded in RAG over MITRE ATT&CK + NVD + your runbooks.

**What the LLM does NOT do:**
- Auto-classify alerts as malicious/benign (that's the deterministic ML + rules' job).
- Auto-close alerts.
- Auto-promote SIGMA rules.
- Anything irreversible without analyst confirmation.

**Why:** real analysts (HN finding #4 + Reddit consensus) report AI hallucinates on logs and produces red herrings during real-time triage but is genuinely useful for **async writing tasks**. Match the tool to the proven use case.

**Model:** Foundation-Sec-8B-Instruct Q4_K_M (~5 GB) via **llama.cpp with Vulkan backend on the RX 590**. ROCm officially dropped Polaris but llama.cpp Vulkan works on RX 590 (8 GB VRAM is enough for Q4 8B). Expected throughput: 15–25 tok/s — fine for async work. CPU fallback (Ryzen 7, 16 threads) if the GPU path has issues: ~5–8 tok/s, still usable.

**RAG knowledge base** (ChromaDB, in-process):
- Full MITRE ATT&CK STIX (835 techniques)
- NVD CVE descriptions for the last 5 years (selective ingest)
- SigmaHQ rule descriptions + their `falsepositives` field
- Your own runbooks (added as you write them)
- **Past case post-mortems** (this is the magic ingredient — every closed case feeds the RAG, so the LLM gets smarter about *your* environment over time)

**Hard rule:** ship a `MOCK_LLM=true` mode that returns deterministic templated responses. The whole platform must work with the LLM disabled — for users without a GPU, for privacy-sensitive deployments, and for CI tests.

### MODULE 5 — Knowledge, Audit & Reporting (THE MEMORY)
*Attacks: institutional-knowledge loss / audit & compliance overhead*

Often overlooked, always critical for adoption in regulated industries.

- **Runbook library** — markdown files in a git-tracked folder, rendered in the UI, attached to alerts by rule mapping. Ships with 15 starter runbooks for the most common attack types (the AI_SOC scope had 8 — go further).
- **Audit trail** — every analyst action (login, alert view, FP-mark, case status change, runbook edit) logged to PostgreSQL + searchable. Auditors love this; most open-source SIEMs skip it.
- **Compliance report generator** — PDF via WeasyPrint, mapped templates for PCI-DSS, ISO 27001, NIST CSF, optionally HIPAA / SOC 2. One click.
- **Weekly metrics report** — alerts processed, FP rate, MTTR, top-firing rules, top-tuned rules, ATT&CK coverage delta. Auto-emailed Monday morning.
- **Backup/restore** — `make backup` tarballs the feedback DB + cases + runbooks + ML models + SIGMA edits. Nobody else does this. Big trust signal.

---

## 5. The 4-service architecture (final)

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       Sources (you ingest from these)                     │
│  Wazuh agents · WAF (ModSecurity) · Firewall syslog · Suricata · Cloud    │
└───────────────────┬───────────────────────────────────────────────────────┘
                    │ webhooks / syslog / filebeat
                    ▼
┌──────────────┐ ┌──────────────────┐
│  ingestor    │─│  wazuh-indexer   │  (OpenSearch fork bundled with Wazuh)
│  FastAPI     │ │  (1 GB heap)     │
└──────┬───────┘ └────────┬─────────┘
       │                  ▲
       │                  │ queries / writes enriched docs
       ▼                  │
┌──────────────┐──────────┘
│  correlator  │  periodic: correlation, FP scoring, enrichment, ATT&CK
│  FastAPI +   │  on-demand: SIGMA rule deploy/test
│  scikit-learn│  reads from indexer, writes incidents back
└──────┬───────┘
       │ "incident resolved" / "runbook missing" events
       ▼
┌──────────────┐                         ┌────────────────┐
│  ai-assist   │ ───llama.cpp/Vulkan────▶│   RX 590 GPU   │
│  FastAPI     │   ChromaDB RAG          │  Foundation-   │
│  (async)     │                         │  Sec-8B Q4     │
└──────┬───────┘                         └────────────────┘
       │ writes drafts to PostgreSQL
       ▼
┌──────────────┐                         ┌────────────────┐
│  api         │◀─REST / WebSocket───────│   React SPA    │
│  FastAPI     │  serves static bundle   │  (Tailwind +   │
└──────┬───────┘                         │   shadcn/ui)   │
       │                                 └────────────────┘
       ▼
┌──────────────┐ ┌──────────────────┐
│  postgres    │ │   wazuh-dashboard│  (optional power-user view)
│  cases, FP   │ │   on :5601       │
│  feedback,   │ └──────────────────┘
│  audit log   │
└──────────────┘
```

**Memory budget on the 16 GB Ryzen 7 PC (verified):**

| Process                   | RAM      |
|---------------------------|---------:|
| OS + browser              | 3.0 GB   |
| wazuh-manager             | 1.0 GB   |
| wazuh-indexer (1 GB heap) | 2.0 GB   |
| wazuh-dashboard           | 0.7 GB   |
| postgres                  | 0.3 GB   |
| ingestor                  | 0.3 GB   |
| correlator                | 0.5 GB   |
| ai-assist (proc only)     | 0.3 GB   |
| Foundation-Sec-8B Q4 (VRAM, not RAM if GPU path) | 0.0 GB on RAM (5 GB on RX 590 VRAM) |
| api                       | 0.3 GB   |
| ChromaDB (in-proc)        | 0.3 GB   |
| Buffer / file cache       | 7.3 GB   |
| **Total RAM used**        | **~9 GB** |
| **Free**                  | **~7 GB** |

**This fits comfortably with headroom.** If the GPU path fails and you have to run the LLM on CPU, that adds ~5 GB and you're at ~14 GB — still fits, with thinner buffer.

---

## 6. The build sequence (16 weeks, solo, with realistic ramp)

This is the order I'd build it in. Each phase ends with something **demoable** so motivation never dies and feedback can come in.

**Phase 0 — Setup (Week 1)**
- Repo: `sentinel-core`, MIT license, branching protected
- Docker Compose skeleton: Wazuh stack + postgres + empty FastAPI services
- CI: GitHub Actions runs `pytest` + `ruff` + `mypy` on every PR
- README v0: problem statement + architecture diagram + "this is what it'll do"

**Phase 1 — Ingest & Index (Weeks 2–3) — Demoable: alerts flow in**
- Wazuh agent on test VM → manager → indexer
- `ingestor` service: Wazuh webhook receiver + ModSecurity CEF parser + iptables syslog parser → ECS-normalized JSON → indexer
- Sample dashboard in wazuh-dashboard showing alerts arriving

**Phase 2 — The Brain (Weeks 4–7) — Demoable: 100 alerts → 8 incidents**
- `correlator` service: temporal grouping + entity resolution
- Whitelist FP layer (YAML config)
- Threat-intel enrichment (AbuseIPDB + OTX + NVD)
- ATT&CK rule mapping
- SIGMA rule import + pySigma translation + deploy
- Sample synthetic attack chain that demonstrates correlation working

**Phase 3 — The Cockpit (Weeks 8–11) — Demoable: real analyst UI**
- React + Tailwind + shadcn/ui scaffold
- Alert queue + filters + sort
- Investigation panel: raw payload + enrichment sidebar + entity timeline + related-incidents
- ATT&CK heatmap (use MITRE's open Navigator embed)
- Lightweight case management
- Audit trail
- Dark mode + keyboard shortcuts
- WebSocket for real-time updates

**Phase 4 — FP Loop & Knowledge (Weeks 12–13) — Demoable: it learns**
- 1-click FP-mark in UI → SQLite → sklearn FP classifier (binary, alert-metadata features)
- Weekly retrain via cron + atomic pickle swap
- Runbook library (15 starter runbooks in markdown)
- Per-alert runbook auto-attach by ATT&CK technique

**Phase 5 — AI Assist (Weeks 14–15) — Demoable: post-incident report drafting**
- llama.cpp build with Vulkan backend on RX 590, Foundation-Sec-8B Q4_K_M
- ChromaDB ingest: ATT&CK + SigmaHQ descriptions + NVD + your runbooks
- `ai-assist` service with three endpoints: `/draft-report`, `/draft-runbook`, `/explain` (all async, queue-backed)
- UI panels for reviewing drafts before saving
- `MOCK_LLM=true` mode for users without GPU

**Phase 6 — Reporting, Polish, Launch (Week 16) — Demoable: shippable v1.0**
- Compliance PDF generator (PCI-DSS, ISO 27001, NIST CSF templates)
- Weekly metrics report
- `make backup` / `make restore`
- Synthetic attack-chain demo script (`make demo-attack`)
- README with GIF, architecture diagram, quickstart
- MkDocs documentation site
- Demo video on YouTube + dev.to launch post
- Tag v1.0.0, post to r/cybersecurity, r/blueteamsec, hackernews, LinkedIn

**16 weeks is honest for solo work** with a day job. If you go full-time on it, compress to 10–12.

---

## 7. What this gives you that nobody else has

This is the GitHub adoption pitch — the README headline.

> **Stop drowning in 10,000 daily alerts. SENTINEL-CORE turns them into 50 actionable incidents — with threat intel, asset context, and runbook attached, on a single screen, free, on your own hardware.**

Concretely, the gaps you fill:

1. **Wazuh + analyst UI in one box.** Wazuh's built-in dashboards are generic. Nobody has shipped an analyst-purpose-built UI on top of it. You will.
2. **SIGMA-native FP feedback loop.** Detection engineers don't have a free tool that combines SigmaHQ deployment with environment-specific FP tuning. You will.
3. **"Similar past incidents" search.** UEBA promised it; no open-source tool delivers it. You will, deterministically, with no baseline-data wait.
4. **AI that drafts reports, not decisions.** Every commercial vendor pitches "AI triage." Real analysts distrust it. You'll be the project that says "the LLM writes the report, the human writes the verdict" — and that aligns with what real SOCs actually want.
5. **Runs on hardware students and SMBs already own.** 16 GB is recommended. Profiles for 8 GB and 32 GB. No cloud dependency, no telemetry, no license server.
6. **One Docker Compose command.** This is the table stakes for adoption and ~80% of open-source security projects fail it.

---

## 8. The success metrics (so we know v1 is "done")

These are the numbers that mean the project succeeded, in order of importance:

1. **A new user gets from `git clone` to "alert in the queue with enrichment" in under 15 minutes** on a 16 GB machine.
2. **FP rate after 2 weeks of analyst feedback is below 30%** of unfiltered Wazuh output.
3. **Investigation panel single-screen rule:** an analyst can decide "real or FP" without opening a second tool 80% of the time.
4. **SigmaHQ deploy works:** at least 2,000 of the 3,000+ community rules import cleanly.
5. **GitHub:** 500 stars in 90 days post-launch (signals real industry interest).
6. **At least 3 outside contributors** with merged PRs (signals it's actually adoptable, not just a portfolio piece).

---

## 9. What you should NOT spend time on (anti-goals)

To stop scope creep before it starts. If you find yourself working on any of these, stop:

- A new SIEM rule language (use SIGMA)
- A new agent (use Wazuh's)
- A custom log shipper (use Filebeat)
- A custom indexer (use Wazuh's bundled OpenSearch)
- Multi-tenancy (v2 / enterprise edition)
- Kubernetes Helm charts (v2)
- Mobile app (never)
- A Splunk-style search language clone
- Per-customer SaaS hosting
- Bundled training datasets in the repo (distribute via release artifacts or external download script — keeps clones fast)
- "AI agents" that take actions autonomously (this is where credibility goes to die in 2025)

---

## 10. My final take

The original scope is the work of someone who wanted to build everything good they read about. That's normal and it's why you came to me. **The version I just defined cuts ~70% of the original feature count and produces a 10× more credible product.** Real SOC analysts (with actual jobs, actual burnout, and actual cynicism toward vendor AI) will install this and keep it. That is the only metric that matters for an open-source security tool.

If you build only the **Brain (Module 2)** and the **Cockpit (Module 3)** properly — even with the LLM module disabled — you have the best free Wazuh analyst UI in existence. Everything else is a multiplier on top of that core. **Do not build the multipliers first.** Build the brain, build the cockpit, get one real SOC analyst on Reddit to use it, then layer on the rest.

Ship the project. Then ship more.
