<!--
████████ ██████   ██  ███   ██ ██ ████████ ██    ██
   ██    ██   ██ ███  ████  ██ ██    ██     ██  ██
   ██    ██████   ██  ██ ██ ██ ██    ██      ████
   ██    ██   ██  ██  ██  ████ ██    ██       ██
   ██    ██   ██ ████ ██   ███ ██    ██       ██
-->

<div align="center">

# TR1NITY

### Unified SIEM Correlation Platform for Wazuh, Firewall, and WAF Logs

_Three sources. One brain. One cockpit. Zero license cost._

[![License: MIT](https://img.shields.io/badge/License-MIT-1976D2.svg)](LICENSE)
[![Status: Phase 0](https://img.shields.io/badge/Status-Phase%200%20%E2%80%94%20Foundation-0D47A1)](ROADMAP.md)
[![Open Source](https://img.shields.io/badge/100%25-Open%20Source-1565C0)](#license)
[![No Paid APIs](https://img.shields.io/badge/Paid%20APIs-0-0D47A1)](docs/planning/03-build-pathway.md)
[![Built for SOC Analysts](https://img.shields.io/badge/Built%20for-SOC%20Analysts-1976D2)](#-the-problem)

</div>

---

## What is TR1NITY?

**TR1NITY** is a fully open-source, AI-assisted security correlation platform that fuses three of the most widely-deployed defensive log sources — **Wazuh** (HIDS / FIM), **firewalls** (iptables / pfSense / OPNsense), and **WAFs** (ModSecurity + OWASP CRS) — into a single ECS-normalized index, then layers correlation, false-positive reduction, MITRE ATT&CK tagging, and a single-pane analyst cockpit on top.

It is designed for the security analyst who is tired of pivoting between five dashboards to triage one alert.

---

## The Problem

Most open-source SOC stacks today force the analyst to manually stitch evidence across tools. A single multi-stage attack typically generates:

- A **WAF alert** (ModSecurity blocks an SQL injection),
- A **firewall log** (iptables records the offending IP),
- A **HIDS alert** (Wazuh detects the post-exploit file integrity change).

Without unified correlation, those three signals appear as **three independent low-fidelity alerts** in three independent dashboards. Industry research links this fragmentation to **71% analyst burnout** and **~80% of analyst time spent on low-fidelity alerts** ([sources](docs/report/tr1nity_report.pdf)).

TR1NITY collapses those three signals into **one incident document** with full kill-chain reconstruction, threat-intel enrichment, ATT&CK mapping, and an AI-drafted post-incident report — all on commodity hardware, with zero recurring cost.

---

## The Six Modules

| #      | Module                                 | Responsibility                                                                                              | Status  |
| ------ | -------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------- |
| **M1** | Ingestion & Normalization              | Wazuh + firewall syslog + ModSecurity → unified ECS schema → `tr1nity-events-*` index                       | Phase 1 |
| **M2** | Correlation & Enrichment ("The Brain") | Temporal grouping, entity resolution, ATT&CK tagging, threat-intel auto-enrichment, SIGMA rule import       | Phase 2 |
| **M3** | AI Assist (HITL)                       | Foundation-Sec-8B Q4 via `llama.cpp`+Vulkan; drafts post-incident reports, runbooks, compliance summaries   | Phase 5 |
| **M4** | False-Positive Handling                | 3-layer pipeline: deterministic whitelist + sklearn classifier + analyst suppression rules                  | Phase 4 |
| **M5** | Analyst Workstation ("The Cockpit")    | React + Tailwind + shadcn/ui single-pane investigation UI with ATT&CK heatmap and similar-incidents search  | Phase 3 |
| **M6** | Knowledge, Audit & Reporting           | 15+ runbooks, audit trail, compliance PDFs (PCI-DSS / ISO 27001 / NIST CSF), weekly metrics, backup/restore | Phase 6 |

Detailed module specs: [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`ROADMAP.md`](ROADMAP.md) · [Phase-1 Report (PDF)](docs/report/tr1nity_report.pdf)

---

## Quickstart (target — available from Phase 0 onward)

```bash
git clone https://github.com/whereisjojii/TR1NITY.git
cd TR1NITY
make up        # boot the full Docker Compose stack
make demo      # generate a synthetic Wazuh + firewall + WAF attack chain
open http://localhost:8080   # the Cockpit
```

> **Note:** TR1NITY is in **Phase 0 — Foundation** as of this commit. The above command is the v1.0 target. See [ROADMAP.md](ROADMAP.md) for the per-phase deliverable list.

---

## Hardware

| Profile                      | CPU                         | RAM        | GPU                             | Storage    | What runs                                            |
| ---------------------------- | --------------------------- | ---------- | ------------------------------- | ---------- | ---------------------------------------------------- |
| **Demo**                     | 4-core                      | 8 GB       | —                               | 100 GB     | Mock LLM mode (`MOCK_LLM=true`); full SIEM core      |
| **Standard** _(recommended)_ | 8-core (e.g. Ryzen 7 3700X) | 16 GB DDR4 | RX 590 8 GB / NVIDIA equivalent | 500 GB SSD | Everything including Foundation-Sec-8B Q4 via Vulkan |
| **Full AI**                  | 8-core+                     | 32 GB      | 8+ GB VRAM                      | 1 TB       | Heavier index retention + always-on LLM              |

LLM acceleration: AMD RX 590 → `llama.cpp` with Vulkan backend (ROCm dropped Polaris; Vulkan works fine).

---

## Zero Paid APIs

Every external dependency is verified free-tier or fully open-source. Including (not exhaustive):

| Service                                        | Tier                            | What it gives us                 |
| ---------------------------------------------- | ------------------------------- | -------------------------------- |
| Wazuh / Wazuh Indexer (OpenSearch fork)        | GPLv2 / Apache 2.0              | HIDS + storage                   |
| Foundation-Sec-8B                              | Apache 2.0                      | Local security-specialized LLM   |
| AbuseIPDB                                      | Free forever (1,000 checks/day) | IP reputation                    |
| AlienVault OTX                                 | Free                            | Pulse-based threat intel         |
| NVD CVE API v2                                 | Free                            | Vulnerability descriptions       |
| abuse.ch (MalwareBazaar / URLhaus / ThreatFox) | Free                            | Malware / URL / botnet IOCs      |
| MaxMind GeoLite2                               | Free (monthly)                  | GeoIP enrichment                 |
| MITRE ATT&CK STIX 2.1                          | Free                            | Technique catalog                |
| SigmaHQ rules                                  | Free (MIT/DRL)                  | ~3,000 community detection rules |
| GitHub Actions CI / Container Registry         | Free for public repos           | CI + image hosting               |

Net recurring cost to run TR1NITY: **$0**.

---

## Documentation

- **[`docs/report/tr1nity_report.pdf`](docs/report/tr1nity_report.pdf)** — Phase-1 academic-style project report (architecture, lit review, use cases, test cases, market value, Gantt chart, IEEE references).
- **[`docs/planning/01-feasibility-report.md`](docs/planning/01-feasibility-report.md)** — Hardware feasibility analysis.
- **[`docs/planning/02-final-scope.md`](docs/planning/02-final-scope.md)** — Opinionated scope cuts (what was removed and why).
- **[`docs/planning/03-build-pathway.md`](docs/planning/03-build-pathway.md)** — 16-week step-by-step build plan.
- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — High-level architecture and component design.
- **[`ROADMAP.md`](ROADMAP.md)** — Phase-by-phase delivery plan with milestone tags.
- **[`CONTRIBUTING.md`](CONTRIBUTING.md)** — How to set up the dev env and contribute.

---

## Build Status by Phase

| Phase                      | Weeks  | Tag                 | What's in it                                 | Status      |
| -------------------------- | ------ | ------------------- | -------------------------------------------- | ----------- |
| 0 — Foundation             | W1     | `v0.1.0-foundation` | Repo, Docker Compose skeleton, CI, MkDocs    | In progress |
| 1 — Multi-source Ingestion | W2–3   | `v0.2.0-ingest`     | Wazuh + firewall + WAF → unified ECS index   | Pending     |
| 2 — The Brain              | W4–7   | `v0.3.0-brain`      | Correlation, ATT&CK, threat-intel, SIGMA     | Pending     |
| 3 — The Cockpit            | W8–11  | `v0.4.0-cockpit`    | React analyst UI, heatmap, similar-incidents | Pending     |
| 4 — FP Loop & Runbooks     | W12–13 | `v0.5.0-feedback`   | 3-layer FP pipeline, 15 runbooks             | Pending     |
| 5 — AI Assist              | W14–15 | `v0.6.0-ai`         | Foundation-Sec-8B + RAG, async drafting      | Pending     |
| 6 — Polish & Launch        | W16    | `v1.0.0`            | Compliance PDFs, metrics, demo video         | Pending     |

---

## Authors

- **Hamza**
- **Irtaza**
- **Hammad**

Department of Cyber Security · Air University, Islamabad · Network Security · Spring 2026.

---

## License

TR1NITY is released under the [MIT License](LICENSE). It depends on third-party components under their own permissive licenses (Apache 2.0, GPLv2, MIT, DRL); see individual submodules and `docs/planning/03-build-pathway.md` for the full attribution table.

---

> _This project is designed for defensive security purposes only. All tools and integrations are used strictly within authorized and controlled environments._
