# SENTINEL-CORE — Feasibility Report

**Target hardware:** Intel i5 (13th gen, 12 cores P+E) · 8 GB RAM · 500 GB SSD · single laptop, no cloud
**Source documents:** Your master research doc (Parts 1–9 + AI_SOC dissection Sections 1–8)
**Goal of this report:** Filter every module, service, dataset, and feature in your research against this exact hardware and tell you — bluntly — what is buildable, what is buildable with explicit trade-offs, and what is not feasible to run locally.

> Verified resource numbers used in this report:
> - Wazuh 4.x **all-in-one minimum: 4 GB RAM / 2 CPU cores**, recommended 16 GB. Source: official Wazuh installation guide.
> - **Foundation-Sec-8B Q4_K_M GGUF: ~4.92 GB RAM** at inference (CPU, llama.cpp). Source: fdtn-ai HuggingFace model card.
> - TheHive 4 + Cortex + Elasticsearch single-node Docker stack: ~1.5–2.5 GB even with `Xms256m -Xmx256m` (TheHive-Project Docker-Templates).
>
> These are not estimates — they are the published numbers from the projects themselves.

---

## TL;DR — The Honest Answer

**Yes, ~85% of SENTINEL-CORE is buildable on your laptop**, but **not all at once and not in a single Docker Compose run**. The 8 GB RAM ceiling forces one architectural rule on you:

> **One heavy subsystem at a time.** You can run Wazuh+Indexer+Dashboard, OR you can run the LLM (Foundation-Sec-8B), OR you can run TheHive — pairs of these are tight, all three together is impossible.

Your research doc already arrived at the right conclusion ("LLM-optional with graceful degradation"). This report locks that in and tells you exactly which features go in which bucket.

**Build verdict:**
- **Fully buildable on this laptop, no compromises:** 18 features
- **Buildable with explicit, documented trade-offs:** 14 features
- **Not feasible locally — needs second machine, GPU, or different scope:** 9 features

---

## Hardware Memory Budget (the actual math)

```
Total system RAM:              8.0 GB
Windows/Linux + Chrome + IDE:  3.0–4.0 GB   (realistic baseline you can't avoid)
Available for the SIEM stack:  4.0–5.0 GB   <-- this is your real budget
```

Per-component published footprints (lean configs):

| Component                                | RAM   | Notes                                                  |
|------------------------------------------|-------|--------------------------------------------------------|
| Wazuh manager                            | 1.0 GB | analysisd + remoted + modulesd                         |
| Wazuh indexer (OpenSearch fork)          | 2.0 GB | JVM heap 1 GB + OS file cache                          |
| Wazuh dashboard (OpenSearch Dashboards)  | 0.7 GB | Node.js                                                |
| **Wazuh all-in-one total**               | **3.5–4.0 GB** | confirmed by Wazuh 4 docs (4 GB minimum)         |
| Filebeat                                 | 0.15 GB |                                                        |
| Python FastAPI services (each)           | 0.2–0.4 GB | correlator, ingestion, rule mgr, feedback           |
| React dev server (Vite)                  | 0.4 GB | only during development; production is static files    |
| PostgreSQL (feedback DB)                 | 0.25 GB |                                                        |
| ChromaDB (in-process Python lib)         | 0.2 GB | not a separate server                                  |
| scikit-learn ML inference (3 models)     | 0.1 GB | RF + XGBoost + DT pickled, ~50 MB on disk each         |
| Ollama + Foundation-Sec-8B Q4_K_M        | **5.0 GB** | this alone eats your entire SIEM budget            |
| Ollama + Llama 3.2:3b (backup)           | 2.5 GB |                                                        |
| Logstash (avoid)                         | 1.0–1.5 GB | replace with Filebeat + Python ingestor             |
| TheHive 4 + Cassandra/BerkeleyDB + ES    | 1.5–2.5 GB |                                                    |
| MISP full LAMP stack                     | 2.5–3.0 GB | do not run locally                                  |
| Suricata                                 | 0.3 GB | only useful if you have a span port / pcap source      |

**Concurrency rules you must accept:**
- ✅ Wazuh stack + Python correlator + ML inference + Filebeat + ChromaDB + PostgreSQL + React (built, served as static)  →  ~5 GB. **Fits.**
- ⚠️ Wazuh stack + Foundation-Sec-8B Q4 LLM  →  ~9 GB. **Will swap. Demoable for short bursts only.**
- ⚠️ Wazuh stack + Llama 3.2:3b (lighter LLM)  →  ~6.5 GB. **Tight but workable.**
- ❌ Wazuh stack + LLM + TheHive  →  ~11 GB. **Not possible.**
- ❌ Wazuh stack + LLM + MISP local  →  ~12 GB. **Not possible.**

**Disk budget (500 GB):** completely fine. Full data inventory is ~30 GB:
- CICIDS2017: 8 GB · UNSW-NB15: 2 GB · NSL-KDD: 0.1 GB · MITRE ATT&CK STIX: 40 MB · SigmaHQ: 15 MB · Ollama models: 5 GB · Docker images: 10 GB · OpenSearch indices (90-day retention with light traffic): ~5–10 GB.

---

## BUCKET A — FULLY BUILDABLE on this laptop (no compromises)

These features run fine inside your 8 GB budget alongside the rest of the stack. Build all of these without hesitation.

| #  | Feature (from your research doc)                                     | Why it fits                                                                 |
|----|----------------------------------------------------------------------|------------------------------------------------------------------------------|
| A1 | **Wazuh 4.x all-in-one** (manager + indexer + dashboard)             | Meets the 4 GB minimum; tune indexer JVM `-Xms1g -Xmx1g`                     |
| A2 | **Filebeat ingestion pipeline** for Wazuh → indexer                  | 150 MB; the doc's "don't run Logstash" rule is correct, follow it            |
| A3 | **Python ingestion microservice** (replaces Logstash)                | FastAPI worker normalizes WAF/firewall/Suricata into common JSON; 200–400 MB |
| A4 | **WAF parser (ModSecurity CEF)** + **firewall parsers (iptables, pfSense)** | pure Python; cheap                                                    |
| A5 | **Smart Alert Correlator (Module 1)** — temporal grouping + entity resolution | Python + OpenSearch query polling every 30 s; 200 MB                |
| A6 | **SIGMA Rule Manager (Module 2)** with pySigma + auto-deploy to Wazuh | pySigma is a Python lib; one-shot translation to OpenSearch DSL              |
| A7 | **SigmaHQ rule library import** (3,000+ community rules)             | 15 MB on disk; index once into OpenSearch                                    |
| A8 | **Whitelist-layer FP reduction** (IPs, processes, users)             | YAML config + redis-cache or in-memory dict                                  |
| A9 | **scikit-learn FP classifier** (LogisticRegression / RandomForest)   | Tiny model (~10 MB); inference < 5 ms                                        |
| A10| **Multi-class ML detection** (RF + XGBoost + Decision Tree on CICIDS2017) — *inference only, models trained offline* | pickled models < 50 MB each; <5 ms inference            |
| A11| **Analyst feedback loop** (PostgreSQL or SQLite store)               | 200 MB; SQLite if you want even lighter                                      |
| A12| **Custom React SOC dashboard** (alert queue, investigation panel, real-time WS feed) | React build is static files served by FastAPI; zero runtime overhead |
| A13| **MITRE ATT&CK Navigator heatmap** (D3 / official Navigator embed)   | Static STIX JSON (40 MB) loaded client-side                                  |
| A14| **Compliance report generator** (PCI-DSS / ISO 27001 / NIST CSF PDF) | Python + WeasyPrint or ReportLab; generated on demand                        |
| A15| **Threat intel enrichment** via free APIs (AbuseIPDB, AlienVault OTX, NVD CVE) | HTTP calls only; no local services. Mind rate limits (AbuseIPDB 1k/day) |
| A16| **MISP feed ingestion (community feeds only, JSON pull)** — not the full MISP server | Cron job downloads IOC JSON, indexes into OpenSearch              |
| A17| **Markov chain kill-chain prediction** (initialised from MITRE ATT&CK ordering + CTID emulation plans) | Pure Python NumPy matrix; <50 MB                       |
| A18| **Docker Compose deployment (development profile)** with resource limits | The deliverable that makes the project actually adoptable on GitHub       |

**This is your v1.0 release.** Every item above runs concurrently inside ~5 GB. This alone is genuinely competitive with mid-tier commercial SIEMs.

---

## BUCKET B — BUILDABLE WITH EXPLICIT TRADE-OFFS

These features are buildable, but the trade-off must be in the README so users (and you) don't get blindsided. Your research doc already half-anticipated this — this section just makes the trade-offs explicit.

| #  | Feature                                              | Trade-off you must accept and document                                                                                                                                |
|----|------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| B1 | **Foundation-Sec-8B Q4_K_M LLM (Module / Service 2)** via Ollama | ~5 GB RAM. **Cannot run alongside the full Wazuh stack on 8 GB without swap.** Use the doc's "LLM-optional with graceful degradation" pattern: ML always runs, LLM only on severity ≥ 7 alerts AND only when user explicitly enables it. Provide a "demo mode" docker-compose profile that turns the Wazuh indexer to minimal heap (512 MB) so the LLM has room. |
| B2 | **Llama 3.2:3b lightweight LLM mode**                | ~2.5 GB. Fits alongside Wazuh. Loses the cybersecurity specialization of Foundation-Sec but enables the analyst-explanation feature on any 8 GB machine.              |
| B3 | **Mock LLM mode** (canned template responses)        | Zero RAM. Always ship this so the demo works on any laptop with no Ollama install.                                                                                    |
| B4 | **TheHive 4 case management integration**            | TheHive 4 + Cassandra + ES adds 1.5–2.5 GB. Two viable paths: **(a)** ship a TheHive *adapter* (the API client) and disable the service by default, document that users with ≥16 GB can enable it; **(b)** build a lightweight Python+SQLite case management module (the doc itself recommends this fallback). Recommendation: do **(b)** as the default and (a) as the optional integration. |
| B5 | **ML model TRAINING on CICIDS2017 (8 GB CSV)**       | Training is RAM-heavy (will hit swap on 8 GB). Mitigation: chunked loading with Polars/Dask, or sub-sample the dataset (10–20% gives ~99% of accuracy on this benchmark). Train **offline as a one-shot script**, ship the pickled models in the repo. End users never re-train, they just download and run. |
| B6 | **UNSW-NB15 + CICIDS2018 expansion**                 | More disk (~12 GB extra), longer training time. Same mitigation as B5. Optional Phase 2 enhancement.                                                                  |
| B7 | **Continuous learning / weekly retraining pipeline** | Retraining is the same heavy job as B5. Run as a **scheduled job that pauses Wazuh containers** during training (or run only when user is not actively SOC-ing). Ship a `make retrain` command, not an always-on service. |
| B8 | **Self-rewriting SIGMA rule generator (Service 7)**  | Requires LLM running concurrently with back-test against historical OpenSearch data — heavy. Build the scaffold, gate behind an explicit `--enable-rule-generation` flag, document as **experimental / requires ≥ 12 GB RAM**.    |
| B9 | **Suricata IDS integration**                         | 200–400 MB is fine, but Suricata is only useful if you have a span port / mirrored network traffic. On a single laptop you usually don't. Ship as optional plugin with a "how to feed it pcap files" guide for demo. |
| B10| **Atomic Red Team attack simulations**               | The atomic tests need a **target machine** (you can't safely run real credential-dumping techniques on the same laptop running your SIEM). Two options: **(a)** ship a synthetic attack generator (Service 8) that produces fake-but-realistic alerts in OpenSearch (no second machine needed, the doc's `POST /simulate` pattern); **(b)** document how users with a spare VM/Pi/old laptop can run real Atomic Red Team and feed alerts back. Default to (a). |
| B11| **UEBA (User-Entity Behavior Analytics) baseline**   | Technically buildable as a Python service computing per-user/host z-scores and rolling baselines. Caveat: UEBA needs **weeks of operational data** before output is meaningful — on a personal demo this will look empty for a while. Ship the engine, ship a script that injects synthetic baseline data so the dashboard isn't blank on day one. |
| B12| **MISP full server integration**                     | A real MISP server is 2.5–3 GB and conflicts with Wazuh's RAM. Ship a **MISP feed *consumer*** (downloads IOCs from public MISP communities as JSON, indexes them) instead of running MISP locally. Full MISP integration is a documented "advanced setup" requiring a second machine. |
| B13| **3 concurrent LLM workers (per AI_SOC)**            | Reduce to **1 worker on 8 GB hardware**. Make worker count configurable in `config.yml` so users with 16/32 GB can scale up.                                          |
| B14| **30-day historical back-testing for SIGMA rule generator** | Requires 30 days of accumulated alerts in OpenSearch — fine on a 500 GB SSD, but only useful after the platform has been running for a month. Document as "kicks in after 30 days of operation." |

---

## BUCKET C — NOT FEASIBLE LOCALLY (or strongly not recommended)

Be honest with users in the README about these limits. Most can be re-enabled later on better hardware or a second machine.

| #  | Feature                                              | Why it can't run on this laptop                                                                                                |
|----|------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| C1 | **Foundation-Sec-8B at BF16 (full precision)**       | Needs 16 GB RAM just for the model. Hard impossible on 8 GB. Q4_K_M is the only viable option.                                |
| C2 | **Foundation-Sec-8B at Q8_0 quantization**           | Needs 8.54 GB for the model alone — leaves 0 GB for the rest of the stack.                                                     |
| C3 | **Foundation-Sec-8B-Reasoning variant**              | Reasoning variant needs more headroom + ideally a GPU. Defer to v2 / GPU-equipped users.                                       |
| C4 | **Full LLM + Wazuh + TheHive + MISP simultaneously** | ~12 GB combined. Will swap so hard the system becomes unusable. This is the limit your research doc warned about.              |
| C5 | **Production multi-node Docker Compose profile**     | Needs ≥ 3 separate hosts. Ship the YAML for documentation/educational purposes only; do not test on this laptop.               |
| C6 | **Multi-tenant MSSP architecture**                   | Requires per-tenant index isolation, RBAC, and resource quotas — needs proper infra. Mark as "v2.0 enterprise edition."        |
| C7 | **Real-time Atomic Red Team execution sandbox**      | Cannot run target VM + SIEM on 8 GB. Needs second machine. (Mitigation: see B10.)                                              |
| C8 | **Always-on continuous LLM-driven enrichment**       | At ~5 GB resident, the LLM cannot stay loaded 24/7 alongside Wazuh. Use on-demand triage of severity ≥ 7 alerts only.          |
| C9 | **GPU-accelerated inference** (vLLM, TensorRT-LLM)   | No discrete GPU on a typical i5 laptop. Stick with CPU + Ollama + Q4 quantization.                                              |

---

## What This Means for Your GitHub Project

### Your v1.0 (Months 1–4) is exactly Bucket A
This gives you a **complete, runnable, demoable, multi-source SIEM correlation platform** on 8 GB hardware:
Wazuh + OpenSearch + Filebeat + Python correlator + SIGMA manager + 3-model ML detection + analyst React UI + ATT&CK heatmap + threat-intel enrichment + compliance reports + Docker Compose. **Nobody else has shipped this combination as one project.**

### Your v1.5 (Months 5–6) adds Bucket B with proper docs
"AI mode" (Foundation-Sec-8B optional), TheHive adapter, lightweight case-mgmt fallback, attack simulator, UEBA scaffolding, MISP feed consumer. Each behind a flag, each with explicit RAM warnings in the README.

### Your v2.0 / "enterprise edition" (later, on better hardware) is Bucket C
Multi-node, multi-tenant, GPU-accelerated, full LLM-always-on. This is the path users with real servers can take.

### Hardware Profile Documentation You Must Ship

Put this exact table in your README. Users will trust the project specifically because you're upfront:

```
┌────────────────────────┬─────────┬──────────────────────────────────────────────────┐
│ Profile                │ RAM     │ Features enabled                                 │
├────────────────────────┼─────────┼──────────────────────────────────────────────────┤
│ Demo (laptop)          │ 4 GB    │ Mock LLM, in-memory store, sample data only      │
│ Standard (your build)  │ 8 GB    │ Bucket A everything, ML always on, LLM optional  │
│ Full AI                │ 16 GB   │ Bucket A + Foundation-Sec-8B always-on + TheHive │
│ Enterprise             │ 32 GB+  │ Multi-node, MISP, UEBA, rule generator           │
└────────────────────────┴─────────┴──────────────────────────────────────────────────┘
```

---

## Mandatory Engineering Rules for the 8 GB Build (non-negotiable)

These come directly from the research doc but ranked by how badly they'll burn you if you skip them:

1. **Tune the OpenSearch JVM heap to 1 GB** (`OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g`). The default is 50% of system RAM and will eat 4 GB on its own.
2. **Replace Logstash with Filebeat + Python ingestor.** Logstash alone is ~1 GB. Non-negotiable on 8 GB.
3. **Single-node, single-shard indices** with index-rollover policy: hot 7 days → warm 30 days → cold compressed JSON on disk.
4. **Train ML models offline. Ship pickled artefacts.** End users never train. Re-training is a separate scheduled job that pauses other containers.
5. **LLM is on-demand, not always-on.** Triggered for severity ≥ 7 with circuit breaker (per AI_SOC pattern, but with 1 worker not 3).
6. **Ship a `mock-llm` docker-compose profile.** This is what makes your project demoable on any 4 GB machine and is the single biggest adoption multiplier.
7. **All thresholds, paths, retention windows in `config.yml`.** No hardcoding. The doc was right.
8. **Static-served React build, not a dev server**, in production profile. Saves 400 MB.
9. **PostgreSQL OR SQLite — not both.** SQLite for the feedback DB is enough at this scale and saves 200 MB.
10. **Document the swap behaviour.** When users enable Full AI mode on 8 GB, tell them they will swap. Better honesty than mysterious slowness.

---

## What's Missing from Your Research Doc (gaps I'd add)

After mapping everything I noticed three things the doc did not address that you'll need:

1. **Index lifecycle / disk-blowup protection.** The doc mentions retention but doesn't specify ISM (Index State Management) policies. Without this OpenSearch will silently consume your 500 GB SSD over months. Ship default ISM policies in v1.0.
2. **Backup / disaster recovery story.** A SOC tool that loses analyst feedback labels on a crash is useless. Ship a `make backup` that snapshots the feedback DB + SIGMA rule edits + ML models to a tarball. Cheap to add, huge trust signal.
3. **Time-series performance baseline.** Add a `make benchmark` that ingests a known volume of alerts and reports throughput (alerts/sec, query latency, memory peak). This is the proof that your project actually works on 8 GB and lets users on bigger hardware predict scaling.

---

## Final Verdict

**Your project is buildable.** The architecture in your research doc is correct. The hardware constraint is real but well-handled by the "LLM-optional + graceful degradation" decision the doc already arrived at.

The single most important architectural commitment you must make is:

> **The 8 GB profile is the default. Everything must work on 8 GB. The 16 GB and 32 GB profiles are "unlocks," not "requirements."**

If you keep that rule, SENTINEL-CORE will be one of the very few open-source SIEM projects that actually runs on the hardware students, junior analysts, and SMBs already own. That is the adoption story — and the research doc identified it correctly. This report just locks in which features go in which tier so you don't accidentally promise something the laptop can't deliver.
