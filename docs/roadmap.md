# Roadmap

The version-controlled scoreboard is [`ROADMAP.md`](https://github.com/whereisjojii/TR1NITY/blob/main/ROADMAP.md) at the repo root.

## Phase summary

| Phase                         | Weeks  | Tag                 | Deliverable                                  |
| ----------------------------- | ------ | ------------------- | -------------------------------------------- |
| 0 — Foundation                | W1     | `v0.1.0-foundation` | Repo, Docker Compose skeleton, CI, MkDocs    |
| 1 — Multi-source Ingestion    | W2–3   | `v0.2.0-ingest`     | Wazuh + firewall + WAF → unified ECS index   |
| 2 — The Brain                 | W4–7   | `v0.3.0-brain`      | Correlation, ATT&CK, threat intel, SIGMA     |
| 3 — The Cockpit               | W8–11  | `v0.4.0-cockpit`    | React analyst UI, heatmap, similar-incidents |
| 4 — FP Loop & Runbooks        | W12–13 | `v0.5.0-feedback`   | 3-layer FP pipeline, 15 runbooks             |
| 5 — AI Assist                 | W14–15 | `v0.6.0-ai`         | Foundation-Sec-8B + RAG, async drafting      |
| 6 — Polish, Reporting, Launch | W16    | `v1.0.0`            | Compliance PDFs, weekly metrics, demo video  |

## Success metrics (target at v1.0)

| Metric                                      | Target   |
| ------------------------------------------- | -------- |
| Quickstart from `git clone` to first alert  | < 15 min |
| FP rate after 2 weeks of analyst feedback   | < 30 %   |
| Time-to-triage (vs. unfederated baseline)   | −70 %    |
| Outside contributors at 90 days post-launch | ≥ 3      |
| GitHub stars at 90 days post-launch         | ≥ 500    |
