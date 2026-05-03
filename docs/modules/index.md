# Modules

TR1NITY is a six-module layered architecture. Each module attacks a documented analyst pain point and is built in its own phase so that progress is always visible.

| #      | Module                                                   | Service(s)                | Phase | Tag               |
| ------ | -------------------------------------------------------- | ------------------------- | ----- | ----------------- |
| **M1** | [Ingestion & Normalization](ingestion.md)                | `ingestor`                | 1     | `v0.2.0-ingest`   |
| **M2** | [Correlation & Enrichment ("The Brain")](correlation.md) | `correlator`              | 2     | `v0.3.0-brain`    |
| **M3** | [AI Assist (HITL)](ai-assist.md)                         | `ai-assist`               | 5     | `v0.6.0-ai`       |
| **M4** | [False-Positive Handling](fp-handling.md)                | `correlator` (sub-module) | 4     | `v0.5.0-feedback` |
| **M5** | [Analyst Workstation ("The Cockpit")](cockpit.md)        | `api` + `ui`              | 3     | `v0.4.0-cockpit`  |
| **M6** | [Knowledge, Audit & Reporting](reporting.md)             | `api` (sub-module)        | 6     | `v1.0.0`          |

## Phase 0 status

This page is current as of `v0.1.0-foundation`. All four FastAPI services are scaffolded as hello-worlds and answer `/healthz` with HTTP 200; no actual ingestion / correlation / drafting work has been done yet. That arrives phase by phase per the [Roadmap](../roadmap.md).
