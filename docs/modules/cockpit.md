# M5 · Analyst Workstation ("The Cockpit")

**Phase:** 3 · **Tag:** `v0.4.0-cockpit` · **Service:** [`ui/`](https://github.com/whereisjojii/TR1NITY/tree/main/ui) (built and served by `services/api/`)

## Goal

Let an analyst fully investigate a multi-source incident **without opening a second tool**. Target: triage 5 incidents in under 2 minutes using only the keyboard.

## Stack

| Layer | Choice |
|-------|--------|
| Framework | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS + shadcn/ui |
| Data | TanStack Query + WebSocket live updates |
| Graph rendering | D3 / Visx for the ATT&CK heatmap |
| Vector search | ChromaDB (via `ai-assist`) for "similar past incidents" |

## Single-pane investigation panel

When an incident is opened, the analyst sees one screen with:

| Region | What it shows |
|--------|---------------|
| Top bar | Incident ID · severity · ATT&CK tactic + technique badges · age |
| Left | The raw event payload (collapsed by default per source) |
| Right (sidebar) | Threat-intel enrichment: AbuseIPDB confidence, OTX pulse refs, NVD CVE notes, GeoIP, ASN |
| Center | Entity timeline: last 30 days of activity for `source.ip` / `user.name` / `host.name` |
| Bottom | Similar past incidents (semantic search via ChromaDB) — with verdicts attached |
| Action bar | `f` mark FP · `c` create case · `o` open referenced runbook · `e` escalate |

## Vim-style keyboard shortcuts

| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up the queue |
| `o` | Open the highlighted incident |
| `f` | Mark FP |
| `c` | Create case |
| `r` | Reload queue |
| `g` `g` / `G` | Jump to top / bottom |
| `?` | Show all shortcuts |

## ATT&CK heatmap

A custom Navigator-style heatmap renders detection coverage per technique:

- 🟢 Green: deployed SIGMA rule + recent successful test
- 🟡 Yellow: deployed but stale (no test in 30 days)
- 🔴 Red: uncovered

Clicking a cell drills down to the incidents under that technique.

## Phase 0 status

The `ui/` workspace exists as a placeholder. The static React build will be served by the `api` service in production. Implementation arrives in Phase 3.
