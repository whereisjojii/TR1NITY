# M2 · Correlation & Enrichment ("The Brain")

**Phase:** 2 · **Tag:** `v0.3.0-brain` · **Service:** [`services/correlator/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator)

## Goal

Turn raw events into a small, ordered queue of high-fidelity _incidents_ with full kill-chain context, ATT&CK technique mapping, and threat-intel enrichment baked in — so the analyst never opens a second tool to make a verdict.

## Pipeline

```
Every 30 seconds:
  1. Query last 5 minutes of tr1nity-events-*
  2. Group by (source.ip, target_ip OR user.name, host.name)
  3. Resolve entities across sources (Wazuh + firewall + WAF)
  4. Tag MITRE ATT&CK techniques
  5. Enrich with threat intel (cached, 24h TTL)
  6. Score FP (Module 4)
  7. Write incident document to tr1nity-incidents-*
```

## ATT&CK mapping

| Source             | Mapping strategy                                                |
| ------------------ | --------------------------------------------------------------- |
| Wazuh              | Wazuh's native `rule.mitre` field                               |
| iptables / pfSense | Static rule-to-technique map (e.g., dropped TCP 22 → T1110.001) |
| ModSecurity        | OWASP CRS rule ID → technique map                               |
| Suricata           | Suricata classtype → technique map                              |

For the long tail, we lean on **SIGMA** rules translated via `pySigma` to the OpenSearch DSL.

## Threat intelligence (free tier only)

| Source                                         | Limit                   | Cache TTL      |
| ---------------------------------------------- | ----------------------- | -------------- |
| AbuseIPDB                                      | 1,000 IP checks/day     | 24 h           |
| AlienVault OTX                                 | rate-limited per minute | 24 h           |
| NVD CVE API v2                                 | 50 req/30 s with key    | 7 d            |
| abuse.ch (MalwareBazaar / URLhaus / ThreatFox) | reasonable use          | 24 h           |
| MaxMind GeoLite2                               | monthly DB pull         | n/a (local DB) |

## SIGMA rule manager

- **Import:** `pySigma` reads the `SigmaHQ/sigma` git submodule (~3,000 community rules).
- **Translate:** rules compile to OpenSearch DSL on-demand.
- **Test:** before activation, the rule runs against the last 7 days and reports an estimated FP rate. Analyst chooses whether to deploy.
- **Deploy:** activated rules are persisted in the correlator's rule registry.

## Phase 0 status

The `correlator` service is currently a hello-world that exposes `/healthz`, `/readyz`, and `/incidents` (returns an empty list with a "not built yet" note). Real implementation arrives in Phase 2.
