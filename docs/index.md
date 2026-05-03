# TR1NITY

> _Three sources. One brain. One cockpit. Zero license cost._

**TR1NITY** is a fully open-source, AI-assisted SOC platform that unifies **Wazuh**, **firewall logs**, and **WAF logs** into a single Elastic Common Schema (ECS) index, then layers correlation, MITRE ATT&CK tagging, false-positive reduction, and a single-pane analyst cockpit on top.

Built for solo SOC operators, university cybersecurity programs, and small MSSPs that cannot stomach Splunk-class licensing fees.

## Why this exists

Most open-source SOC stacks today force the analyst to manually stitch evidence across tools. A single multi-stage attack typically generates a WAF alert, a firewall log, **and** a HIDS alert — three independent low-fidelity events in three independent dashboards. Industry research links this fragmentation to high analyst burnout and a large share of analyst time spent on low-fidelity alerts.

TR1NITY collapses those three signals into one incident document with full kill-chain reconstruction, threat-intel enrichment, ATT&CK mapping, and an AI-drafted post-incident report — all on commodity hardware, with **zero recurring cost**.

## Where to start

<div class="grid cards" markdown>

- :material-rocket-launch: **[Quickstart](quickstart.md)**

  Boot the full stack in 15 minutes.

- :material-sitemap: **[Architecture](architecture.md)**

  Six modules, four FastAPI services, one Docker Compose file.

- :material-map: **[Roadmap](roadmap.md)**

  16-week phase plan from `v0.1.0-foundation` to `v1.0.0`.

</div>

## Module map

| #      | Module                                                           | Phase | Status  |
| ------ | ---------------------------------------------------------------- | ----- | ------- |
| **M1** | [Ingestion & Normalization](modules/ingestion.md)                | 1     | Pending |
| **M2** | [Correlation & Enrichment ("The Brain")](modules/correlation.md) | 2     | Pending |
| **M3** | [AI Assist (HITL)](modules/ai-assist.md)                         | 5     | Pending |
| **M4** | [False-Positive Handling](modules/fp-handling.md)                | 4     | Pending |
| **M5** | [Analyst Workstation ("The Cockpit")](modules/cockpit.md)        | 3     | Pending |
| **M6** | [Knowledge, Audit & Reporting](modules/reporting.md)             | 6     | Pending |
