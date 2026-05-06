# M5 · Analyst Workstation ("The Cockpit")

**Phase:** 3 · **Tag:** `v0.4.0-cockpit` · **Service:** [`ui/`](https://github.com/whereisjojii/TR1NITY/tree/main/ui) (proxied by [`services/api/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/api))

## Goal

Let an analyst fully investigate a multi-source incident **without opening a second tool**. Target: triage 5 incidents in under 2 minutes using only the keyboard.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       UI (ui/, React + Vite)                      │
│  Queue · Detail · Heatmap · Cases · Help                          │
└─────────────┬─────────────────────────────────────┬──────────────┘
              │  /api/* (HTTP)                       │  /ws/incidents (WS)
              ▼                                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                    services/api (Cockpit gateway)                 │
│  Routers ─ incidents · cases · attack · similar · realtime        │
│  Composition lib · CockpitStore · ConnectionManager               │
└────┬──────────────────────┬──────────────────────────┬───────────┘
     │ /correlate, /incidents│ optional fallback        │ broadcast
     ▼                       ▼                         ▼
┌─────────────────┐   ┌──────────────┐         ┌──────────────────┐
│ services/correl │   │ OpenSearch   │         │ live ws clients  │
└─────────────────┘   └──────────────┘         └──────────────────┘
```

## Stack

| Layer         | Choice                                                                                                                      |
| ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Framework     | React 18 + Vite 5 + TypeScript                                                                                              |
| Styling       | Tailwind CSS 3 (custom shadcn-style primitives, no runtime dep)                                                             |
| Data layer    | TanStack Query + native `WebSocket` for `/ws/incidents`                                                                     |
| Icons         | `lucide-react`                                                                                                              |
| Routing       | `react-router-dom` (basename `/cockpit`)                                                                                    |
| Vector search | Phase 3 ships a deterministic IP / technique heuristic; Phase 5 swaps in ChromaDB cosine similarity (no API change needed). |

## Pages

| Path             | Component            | Purpose                                                               |
| ---------------- | -------------------- | --------------------------------------------------------------------- |
| `/queue`         | `QueuePage`          | Alert queue, FP-score sort, source / severity filters, vim shortcuts. |
| `/incidents/:id` | `IncidentDetailPage` | Single-pane investigation: Overview / Timeline / Raw / Similar tabs.  |
| `/heatmap`       | `HeatmapPage`        | MITRE ATT&CK Navigator-style heatmap, frequency-graded.               |
| `/cases`         | `CasesPage`          | Lightweight case manager (in-memory in Phase 3, Postgres in Phase 4). |
| `/help`          | `HelpPage`           | Keyboard reference + Phase-3 quirks.                                  |

## API surface (`services/api`)

### HTTP

| Method | Path                                   | Purpose                                                                                                                                                                      |
| ------ | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/api/incidents`                       | Composed queue (correlator + recent buffer + OpenSearch fallback). Filters: `sort_by`, `descending`, `severity_min`, `sources[]`, `technique`, `limit`, `include_persisted`. |
| GET    | `/api/incidents/{incident_id}`         | Single incident, fully decorated (FP score + feedback if present).                                                                                                           |
| POST   | `/api/incidents/{incident_id}/mark-fp` | Record analyst FP / TP feedback (`is_fp`, optional `reason`, `submitted_by`).                                                                                                |
| POST   | `/api/incidents/refresh`               | Trigger a correlator tick + broadcast `incident.new` to WS clients.                                                                                                          |
| GET    | `/api/incidents/{incident_id}/similar` | Phase-3 heuristic: source-IP overlap + technique Jaccard + source Jaccard.                                                                                                   |
| GET    | `/api/cases`                           | List cases (`status`, `assigned_to` filters).                                                                                                                                |
| POST   | `/api/cases`                           | Create case (title required; severity 0..7 clamped).                                                                                                                         |
| GET    | `/api/cases/{case_id}`                 | Read a single case.                                                                                                                                                          |
| PATCH  | `/api/cases/{case_id}`                 | Partial update (title / status / severity / tags / incident_ids).                                                                                                            |
| POST   | `/api/cases/{case_id}/notes`           | Append an analyst note (author defaults to `analyst`).                                                                                                                       |
| DELETE | `/api/cases/{case_id}`                 | Remove a case.                                                                                                                                                               |
| GET    | `/api/attack/heatmap`                  | Technique + tactic frequency aggregation across the composed queue.                                                                                                          |

The Phase-0 routes (`GET /`, `GET /healthz`, `GET /readyz`, `GET /ws` echo) are preserved verbatim for backward compatibility.

### WebSocket

```
ws://<api-host>/ws/incidents
```

The api emits, in order:

```jsonc
{ "type": "hello",     "service": "api", "channel": "incidents", "ts": "..." }
{ "type": "snapshot",  "ts": "...", "incidents": [ /* full queue */ ] }
{ "type": "incident.new", "ts": "...", "incidents": [ /* delta */ ] }   // on every refresh
{ "type": "ping",      "ts": "..." }                                     // heartbeat
```

The UI hook `useIncidentsLive` reconnects automatically on close / error.

## Vim-style keyboard shortcuts

| Key                   | Where           | Action                                            |
| --------------------- | --------------- | ------------------------------------------------- |
| `j` / `k`             | Queue           | Next / previous incident                          |
| `g g`                 | Queue           | Jump to top                                       |
| `G`                   | Queue           | Jump to bottom                                    |
| `o` / Enter           | Queue           | Open the selected incident                        |
| `Esc` / `h`           | Detail          | Back to queue                                     |
| `1` / `2` / `3` / `4` | Detail          | Switch tabs (Overview / Timeline / Raw / Similar) |
| `f`                   | Queue + Detail  | Mark current incident as **false positive**       |
| `t`                   | Queue + Detail  | Mark current incident as **true positive**        |
| `c`                   | Detail          | Create a case from the open incident              |
| `r`                   | Queue + Heatmap | Trigger a correlator tick / refetch               |
| `1` / `2` / `3` / `?` | Sidebar         | Queue / ATT&CK / Cases / Help                     |

Shortcuts auto-suspend whenever an `<input>`, `<textarea>`, `<select>`, or `contenteditable` element is focused.

## ATT&CK heatmap

Per-tactic columns are rendered in the canonical kill-chain order (Reconnaissance → Resource Development → Initial Access → … → Impact). Cells are colored by frequency relative to the busiest technique in the current view:

| Cell color | Meaning                         |
| ---------- | ------------------------------- |
| Muted gray | No incidents observed           |
| Accent     | Light coverage (≥ 1)            |
| Warning    | ≥ 25 % of the busiest technique |
| Danger     | ≥ 50 %                          |
| Critical   | ≥ 75 %                          |

## Configuration

`services/api` reads the following environment variables at boot (defaults are tuned for `make up` with no extra setup):

| Variable                            | Default                          | Purpose                                         |
| ----------------------------------- | -------------------------------- | ----------------------------------------------- |
| `TR1NITY_CORRELATOR_URL`            | `http://correlator:8002`         | Upstream correlator base URL                    |
| `OPENSEARCH_URL`                    | `https://wazuh-indexer:9200`     | Read-only fallback for persisted incidents      |
| `OPENSEARCH_USERNAME` / `_PASSWORD` | `admin` / `ChangeMeAtFirstBoot!` | Basic-auth credentials                          |
| `OPENSEARCH_VERIFY_TLS`             | `false` (dev)                    | Set `true` in prod                              |
| `INCIDENTS_INDEX_PREFIX`            | `tr1nity-incidents`              | Searched as `<prefix>-*`                        |
| `TR1NITY_API_JWT_SECRET`            | placeholder                      | Reserved for Phase 4 auth                       |
| `WS_HEARTBEAT_SECONDS`              | `20`                             | `/ws/incidents` ping cadence                    |
| `COCKPIT_DEV_ORIGIN`                | unset                            | Adds CORS for `pnpm dev` on `:5173` in dev only |
| `COCKPIT_STATIC_DIR`                | unset                            | Mount `ui/dist` to be served by api in prod     |
| `RECENT_INCIDENT_BUFFER`            | `1000`                           | Cap on the in-memory recent-incidents buffer    |

## Local development

```bash
# Backend
make up                       # boot the full stack (correlator, api, OpenSearch …)

# Frontend (separate terminal)
cd ui
pnpm install                  # one-time
pnpm dev                      # http://localhost:5173/cockpit/queue (HMR)
```

Vite proxies `/api/*` → `VITE_API_URL` and `/ws/*` → its WS equivalent, so the dev server still hits the running api container without CORS noise.

## What ships in Phase 3 vs. Phase 4 / 5

| Concern           | Phase 3 (now)                                    | Phase 4                                             | Phase 5                                    |
| ----------------- | ------------------------------------------------ | --------------------------------------------------- | ------------------------------------------ |
| FP feedback       | In-process ledger, neutral 0.5 baseline          | Persisted to Postgres, drives sklearn FP classifier | LLM rationale alongside the score          |
| Cases             | In-process `CockpitStore` (thread-safe)          | Postgres-backed, audit trail                        | Auto-suggested similar cases               |
| Similar incidents | Deterministic heuristic (IP + technique Jaccard) | Same heuristic + Postgres index                     | ChromaDB cosine similarity over embeddings |
| Heatmap           | Live aggregation over composed queue             | + drill-through into incidents per cell             | + suggested SIGMA gaps                     |
| Realtime          | Snapshot + `incident.new` broadcast              | + per-tenant filtering                              | + draft narrative streamed token-by-token  |
