# M1 · Ingestion & Normalization

**Phase:** 1 · **Tag:** `v0.2.0-ingest` · **Service:** [`services/ingestor/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/ingestor)

## Goal

Receive events from the three core defensive log sources — Wazuh, firewalls, WAFs — and write them all into a single OpenSearch index (`tr1nity-events-*`) with a uniform Elastic Common Schema (ECS) shape.

## Sources

| Source | Transport | Format | Parser |
|--------|-----------|--------|--------|
| Wazuh | HTTP webhook (Wazuh integration) | Wazuh JSON | `app.parsers.wazuh` |
| Firewall (iptables) | UDP 514 syslog | iptables log line | `app.parsers.iptables` |
| Firewall (pfSense / OPNsense) | UDP 514 syslog | filterlog | `app.parsers.pfsense` |
| WAF (ModSecurity + OWASP CRS) | Filebeat / syslog | JSON or CEF | `app.parsers.modsecurity` |
| Suricata (optional) | EVE JSON tail | EVE | `app.parsers.suricata` |

## ECS shape

Every parser produces a document with at minimum:

```json
{
  "@timestamp": "2026-05-03T12:34:56.789Z",
  "event": {
    "module": "wazuh|iptables|pfsense|modsecurity|suricata",
    "category": ["intrusion_detection"],
    "type":     ["alert"],
    "severity": 7,
    "action":   "blocked|alerted|denied"
  },
  "source":      { "ip": "203.0.113.5", "port": 51234 },
  "destination": { "ip": "10.0.0.42",   "port": 22 },
  "host":        { "name": "web-prod-1" },
  "user":        { "name": "root" },
  "threat":      { "tactic": "...", "technique": { "id": "T1110.001" } },
  "tr1nity":     { "raw": "...original payload, untouched..." }
}
```

## Index lifecycle

`tr1nity-events-*` follows an ISM (Index State Management) policy:

| State | Default | Purpose |
|-------|---------|---------|
| Hot | 7 d | Active queries, fast disk |
| Warm | 30 d | Older queries, slower disk |
| Cold (closed) | 90 d | Compliance retention |
| Delete | 180 d | Final purge |

All thresholds are operator-overridable via env vars.

## Phase 0 status

The `ingestor` service is currently a hello-world FastAPI app exposing `/healthz`, `/readyz`, and a Swagger UI at `/docs`. No parsers are wired yet; that lands in Phase 1.
