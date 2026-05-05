# M2 · Correlation & Enrichment ("The Brain")

**Phase:** 2 · **Tag:** `v0.3.0-correlation` · **Service:** [`services/correlator/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator)

## Goal

Turn the high-volume ECS event stream produced by the ingestor into a much smaller, ordered queue of high-fidelity **incidents** an analyst can actually triage. Every incident carries:

- Its member events (denormalized so the Cockpit doesn't need a second query).
- A canonically-ordered MITRE ATT&CK kill-chain.
- Any SIGMA rule firings.
- Threat-intel hits attached to source IPs.
- A promoted severity that escalates to the worst member event's level.

No AI is used at this layer — the logic is deterministic, file-based, and easy to audit.

## Pipeline

```
loop every poll_interval_seconds:
  1. consumer.fetch(max_events_per_tick)            ← OpenSearch (or in-memory in DRY_RUN)
  2. for each event: SIGMA engine matches rules    ← may add technique tags + promote severity
  3. group_events(events, window_seconds, max_events_per_incident)
                                                    ← sliding window per source IP
  4. for each incident: enrich_attack(), enrich_intel()
  5. for each sink: sink.write(incidents)           ← OpenSearch (default) and/or stdout
```

The pipeline is implemented in [`services/correlator/app/pipeline.py`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/pipeline.py) and is invoked by `POST /correlate` in Phase 2. Phase 4 will replace the manual trigger with an in-process scheduler.

## Grouping

Today, two events end up in the same incident if **all** of:

- they share a grouping key — currently `source.ip` (the most operationally useful single signal);
- their `@timestamp` values fall within `INCIDENT_WINDOW_SECONDS` of each other (default 15 min);
- the bucket has fewer than `INCIDENT_MAX_EVENTS` members (default 500).

Events without a usable grouping key (no source IP) become single-event incidents — we never silently drop them.

The grouping algorithm lives in [`grouping.py`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/grouping.py) and is stateless between calls.

## SIGMA rule engine

We ship a small, in-process SIGMA-style engine in [`app/sigma/engine.py`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/sigma/engine.py). It supports the strict subset of the SIGMA spec we actually use:

- `title`, `id`, `level`, `tags`
- `detection` block with named selections + a `condition` expression
- Modifiers: `contains`, `startswith`, `endswith`, `re` (everything else is rejected at parse time)
- Combinators: `and`, `or`, `not`, parentheses, `1 of <prefix>*`, `1 of them`

Rule-level severities map to ECS:

| SIGMA `level` | ECS severity |
| ------------- | ------------ |
| informational | 0            |
| low           | 2            |
| medium        | 4            |
| high          | 6            |
| critical      | 7            |

The bundled rule pack ([`app/sigma/rules/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/sigma/rules)) covers the four event types the ingestor emits today:

- `wazuh_brute_force_ssh.yml` → tags `attack.t1110`, `attack.t1110.001`
- `waf_sql_injection.yml` → tags `attack.t1190`
- `waf_path_traversal.yml` → tags `attack.t1083`
- `firewall_portscan.yml` → tags `attack.t1595`, `attack.t1046`

When a rule fires, the pipeline:

1. Rewrites `event.severity` to `max(existing, rule severity)`.
2. Adds the rule's `attack.tNNNN` tags to `threat.technique[*]`.
3. Records the rule ID under `tr1nity.sigma_matches[*]` for audit.

## ATT&CK chain promotion

Once events are grouped, [`app/attack.py`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/attack.py) takes over:

- The flat union of member technique IDs is **deduped** and **sorted** by canonical kill-chain order (Reconnaissance → Resource Development → Initial Access → … → Impact).
- Each technique is mapped to its primary tactic so the incident's `tactic_ids` are coherent.
- The summary line gets a human-readable chain like `Active Scanning (T1595) → Exploit Public-Facing Application (T1190) → Brute Force (T1110)`.

The technique table is intentionally trimmed to what TR1NITY's parsers can emit today. Adding a new technique is a one-line tuple — no rebuilds, no full ATT&CK matrix import.

## Threat-intel enrichment

Free feeds only — TR1NITY's contract with users is **no paid APIs ever**. Today we ship:

- A bundled, file-based IOC list at [`app/intel/data/ioc.json`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/intel/data/ioc.json) that operators can hand-edit or replace with a snapshot of any free feed (abuse.ch URLhaus, SANS ISC blocklist, Spamhaus DROP, etc.).
- A pluggable `Provider` protocol ([`app/intel/base.py`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/intel/base.py)) so future phases can add AlienVault OTX, abuse.ch SSL blacklist, SANS ISC, etc.
- A TTL-bounded in-memory `IntelCache` ([`app/intel/cache.py`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/intel/cache.py)) that caches both positive **and** negative results so the correlator stops hammering the same feed for benign IPs across thousands of events.

Hits are denormalized onto the incident under `intel_hits[*]` with `indicator`, `feed`, `tags`, `confidence`, `description`. The Cockpit reads them inline.

## Output

Incidents are written to OpenSearch under `tr1nity-incidents-YYYY.MM.dd` via the `_bulk` endpoint ([`app/sinks/opensearch.py`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/app/sinks/opensearch.py)). The sink mirrors the ingestor's pattern (auth, TLS, per-item status accounting) for one consistent operational surface.

In `DRY_RUN=true` mode (the default for local dev) the correlator skips OpenSearch entirely and writes one JSON line per incident to stdout, so a fresh `docker compose up` works without standing up the indexer.

## Configuration

| Variable                            | Default                     | Meaning                                   |
| ----------------------------------- | --------------------------- | ----------------------------------------- |
| `OPENSEARCH_URL`                    | `http://wazuh-indexer:9200` | OpenSearch base URL                       |
| `OPENSEARCH_USERNAME` / `_PASSWORD` | (empty) / (empty)           | basic auth credentials                    |
| `OPENSEARCH_VERIFY_TLS`             | `true`                      | verify the indexer's TLS certificate      |
| `EVENTS_INDEX_PATTERN`              | `tr1nity-events-*`          | where the consumer reads events from      |
| `INCIDENTS_INDEX_PREFIX`            | `tr1nity-incidents`         | prefix for daily incident indices         |
| `DRY_RUN`                           | `true`                      | skip OpenSearch entirely; write to stdout |
| `INCIDENT_WINDOW_SECONDS`           | `900`                       | sliding-window size                       |
| `INCIDENT_MAX_EVENTS`               | `500`                       | hard cap on members per incident          |
| `POLL_INTERVAL_SECONDS`             | `10`                        | reserved for the Phase-4 scheduler        |
| `INTEL_CACHE_TTL_SECONDS`           | `3600`                      | how long IOC lookups stay cached          |
| `INTEL_ENABLED`                     | `true`                      | turn intel off entirely                   |
| `SIGMA_ENABLED`                     | `true`                      | turn the SIGMA engine off entirely        |

## HTTP API

| Method | Path           | Purpose                                                              |
| ------ | -------------- | -------------------------------------------------------------------- |
| GET    | `/`            | Service banner (name, version, phase, links)                         |
| GET    | `/healthz`     | Liveness probe                                                       |
| GET    | `/readyz`      | Readiness probe                                                      |
| POST   | `/correlate`   | Run one pipeline tick; returns produced incidents and per-sink stats |
| GET    | `/incidents`   | List incidents from the most recent tick                             |
| POST   | `/ingest-test` | Push events into the in-memory consumer (DRY_RUN only)               |

## Tests

The correlator's test suite lives under [`services/correlator/tests/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator/tests). Coverage:

- `test_grouping.py` — sliding window, multi-IP separation, window-break, max-event cap, severity promotion, unsorted input, technique union.
- `test_attack.py` — kill-chain ordering, tactic resolution, render strings, unknown-technique pass-through.
- `test_sigma.py` — parser, all selection modifiers, condition combinators, level→severity mapping, bundled-rule pack loads.
- `test_intel.py` — file-provider load (good / missing / invalid JSON), TTL caching of positive AND negative results, custom-feed loads.
- `test_sinks.py` — stdout NDJSON, OpenSearch `_bulk` happy path, per-item failures, network errors, empty-input no-op.
- `test_consumer_opensearch.py` — high-water-mark advancement, HTTP errors, network errors.
- `test_pipeline.py` — full end-to-end: events → grouping → SIGMA → ATT&CK → intel → sinks.
- `test_api.py` — `/correlate` and `/ingest-test` endpoints.

Run with:

```bash
cd services/correlator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

## What's next

Phase 3 (the Cockpit) reads `tr1nity-incidents-*` and renders incidents as cards with the ATT&CK chain, member events, intel hits, and SIGMA matches. Phase 4 adds the false-positive feedback loop and 15 starter runbooks. Phase 5 layers AI Assist on top via RAG over incidents + member events.
