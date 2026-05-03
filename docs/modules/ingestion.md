# M1 · Ingestion & Normalization

**Phase:** 1 · **Tag:** `v0.2.0-ingest` · **Service:** [`services/ingestor/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/ingestor)

## Goal

Receive events from the three core defensive log sources — Wazuh, firewalls,
WAFs — and write them all into a single OpenSearch index (`tr1nity-events-*`)
with a uniform Elastic Common Schema (ECS) shape.

## Endpoints (Phase 1)

| Method | Path             | Body                                  | Status              |
| ------ | ---------------- | ------------------------------------- | ------------------- |
| GET    | `/`              | —                                     | service banner      |
| GET    | `/healthz`       | —                                     | liveness probe      |
| GET    | `/readyz`        | —                                     | readiness + sink ok |
| POST   | `/ingest/wazuh`  | one alert OR JSON array of alerts     | `202 Accepted`      |
| POST   | `/ingest/syslog` | `{ "lines": [...], "host": "fw-01" }` | `202 Accepted`      |
| POST   | `/ingest/waf`    | one ModSecurity v3 audit object       | `202 Accepted`      |

All `POST /ingest/*` endpoints respect `ENABLE_AUTH=true` + `INGESTOR_AUTH_TOKEN` and
require `Authorization: Bearer <token>` when enabled. Token comparison is constant-time.

The endpoints return JSON of the shape:

```json
{
  "received": 3,
  "parsed": 3,
  "accepted": 3,
  "rejected": 0,
  "parse_errors": [],
  "sink_errors": [],
  "sink": "stdout"
}
```

`202` is returned as long as at least one event parses; full failure returns `422`.

## Sources

| Source                        | Transport                        | Format            | Parser module          |
| ----------------------------- | -------------------------------- | ----------------- | ---------------------- |
| Wazuh                         | HTTP webhook (Wazuh integration) | Wazuh alert JSON  | `app.sources.wazuh`    |
| Firewall (iptables)           | Filebeat → HTTP / syslog → HTTP  | iptables log line | `app.sources.firewall` |
| Firewall (pfSense / OPNsense) | Filebeat → HTTP                  | filterlog CSV     | `app.sources.firewall` |
| WAF (ModSecurity v3 / CRS)    | Filebeat → HTTP                  | JSON audit        | `app.sources.modsec`   |

The firewall parser auto-detects the format per line — operators do not need to
pick a specific dispatcher; one POST to `/ingest/syslog` handles both iptables
and pfSense lines in the same batch.

## ECS shape

Every parser produces an ECS-8.11 document with at minimum:

```json
{
  "@timestamp": "2026-05-03T12:34:56.789Z",
  "ecs.version": "8.11",
  "event": {
    "module": "wazuh|firewall|modsecurity",
    "dataset": "wazuh.alert",
    "kind": "alert",
    "category": ["authentication"],
    "type": ["start"],
    "action": "ssh.brute_force",
    "outcome": "failure",
    "severity": 7,
    "id": "f1c0…",
    "ingested": "2026-05-03T12:34:57.001Z"
  },
  "source": { "ip": "203.0.113.45", "port": 41234 },
  "destination": { "ip": "10.0.0.10", "port": 22 },
  "host": { "name": "web-server-01" },
  "user": { "name": "root" },
  "rule": { "id": "5710", "level": 10, "name": "Multiple failed SSH" },
  "threat": {
    "tactic": { "name": "Credential Access" },
    "technique": { "id": "T1110", "name": "Brute Force" }
  },
  "tags": ["wazuh"],
  "tr1nity": {
    "source": "wazuh",
    "normalizer_version": "0.2.0",
    "raw": "…truncated to 8 KiB…",
    "raw_hash_sha256": "<sha256 of full payload>"
  }
}
```

The `tr1nity.raw` field is capped at **8 KiB** — anything longer is truncated
with the marker `...[truncated]` and the full SHA-256 hash recorded in
`tr1nity.raw_hash_sha256`. This keeps a tamper-evident audit trail without
blowing index size on noisy sources.

### Severity mapping

| Internal | Wazuh level | ECS severity | Meaning       |
| -------- | ----------- | ------------ | ------------- |
| 0        | 0           | 0            | informational |
| 1        | 1–3         | 2            | low           |
| 2        | 4–7         | 4            | medium        |
| 3        | 8–11        | 6            | high          |
| 4        | 12–15       | 7            | critical      |

## Sinks

| Sink         | Mode                             | Notes                                         |
| ------------ | -------------------------------- | --------------------------------------------- |
| `stdout`     | `DRY_RUN=true` (default for dev) | One ECS doc per line — `docker logs` works    |
| `opensearch` | `DRY_RUN=false`                  | NDJSON `_bulk` to `tr1nity-events-YYYY.MM.dd` |

Daily index pattern is fixed: `{OPENSEARCH_INDEX_PREFIX}-YYYY.MM.dd` (UTC).
Phase 2 will add an ISM policy to roll Hot → Warm → Cold → Delete; until then,
operators can manage rollover with their existing OpenSearch tooling.

## Configuration

| Env var                   | Default                     | Notes                              |
| ------------------------- | --------------------------- | ---------------------------------- |
| `TR1NITY_ENV`             | `dev`                       | one of `dev`, `staging`, `prod`    |
| `DRY_RUN`                 | `true`                      | when `true`, sink = stdout         |
| `ENABLE_AUTH`             | `false`                     | when `true`, requires bearer token |
| `INGESTOR_AUTH_TOKEN`     | (empty)                     | required if `ENABLE_AUTH=true`     |
| `OPENSEARCH_URL`          | `http://wazuh-indexer:9200` | base URL                           |
| `OPENSEARCH_USERNAME`     | (empty)                     |                                    |
| `OPENSEARCH_PASSWORD`     | (empty, SecretStr)          |                                    |
| `OPENSEARCH_INDEX_PREFIX` | `tr1nity-events`            |                                    |
| `OPENSEARCH_VERIFY_TLS`   | `true`                      | `false` for self-signed dev certs  |
| `MAX_BODY_BYTES`          | `1048576` (1 MiB)           | per-request guardrail              |
| `MAX_LINES_PER_REQUEST`   | `1000`                      | for `/ingest/syslog`               |
| `MAX_EVENTS_PER_REQUEST`  | `500`                       | for `/ingest/wazuh` batches        |

Secrets (`*_PASSWORD`, `INGESTOR_AUTH_TOKEN`) are wrapped in
[`pydantic.SecretStr`](https://docs.pydantic.dev/latest/concepts/types/#secret-types)
so they never appear in tracebacks or `repr()` output.

## Demo

```bash
make up              # starts ingestor in DRY_RUN mode
make demo            # fires synthetic 3-event chain (firewall → WAF → Wazuh)
```

`scripts/demo/synth_attack.py` posts one event per source with the **same
attacker IP**, exactly the input shape Phase 2's correlator will collapse
into a single incident.

## Filebeat

A drop-in [`deploy/filebeat/filebeat.yml`](https://github.com/whereisjojii/TR1NITY/blob/main/deploy/filebeat/filebeat.yml)
template ships with the repo for hosts that need to forward iptables /
pfSense / ModSec audit logs over HTTP into the ingestor.

## Tests

`services/ingestor/tests/` ships **42 tests** covering:

- ECS schema rendering, severity mapping, raw-truncation hashing, ID generation
- Wazuh parser (brute force, malware classification, MITRE extraction, rejection of bad payloads)
- Firewall parser (iptables DROP, pfSense block, auto-dispatch, partial failure)
- ModSec parser (SQLi blocking, MITRE tagging, severity extraction)
- HTTP endpoint contracts (single + batch, auth enforcement, partial-failure 202, full-failure 422)
- OpenSearch sink (per-item bulk status, auth/network failure modes, healthcheck)

Run them with `make test` or `cd services/ingestor && pytest`.
