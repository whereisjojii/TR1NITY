# M4 · False-Positive Handling

**Phase:** 4 · **Tag:** `v0.5.0-feedback` · **Lives in:** [`services/correlator/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/correlator) (FP sub-module)

## Goal

Continuously reduce the analyst's noise floor by learning from their feedback. Target: **FP rate < 30 %** within two weeks of deployment.

## Three-layer pipeline

The `fp_score` of every incident is the maximum of three layers, each independent and explainable:

### Layer 1 — Deterministic YAML whitelist

Authored by the operator, version-controlled. Examples:

```yaml
- name: Vulnerability scanner sweeps from authorized IPs
  match:
    source.ip: [10.10.99.10, 10.10.99.11]
    event.module: [iptables]
  fp_score: 0.95
  ttl_days: never
  rationale: "Tenable Nessus scanners — pre-approved by the SOC."
```

Layer 1 is for the cases where the operator already knows the answer. No machine learning needed.

### Layer 2 — sklearn classifier

A small (< 50 MB) scikit-learn classifier trained on **the analyst's own "Mark FP" clicks**. Features come from incident metadata (rule ID, severity, source-port distribution, time-of-day, ATT&CK tactic, source AS, geographic distance, etc.). Retrained weekly via `make retrain`; held-out eval reports the FP score delta on similar alerts.

Crucially, **the classifier is never the only signal**: it sits between Layer 1 (operator certainty) and Layer 3 (analyst override).

### Layer 3 — Analyst-authored suppression rules

Authored from the Cockpit, with TTL and audit trail. Examples:

```yaml
- name: Suppress noisy ModSecurity rule 949110 from /healthcheck
  match:
    rule.id: "949110"
    url.path: "/healthcheck"
  fp_score: 1.0
  ttl_days: 30
  author: "analyst@example.com"
  reason: "Health probes from internal monitoring; safe to suppress for 30 days."
```

## Surface in the UI

- Every incident shows `fp_score` and which layer set it.
- The queue defaults to "ascending fp_score, descending severity" — i.e., high-confidence true positives float to the top.
- "Mark FP" appends a labelled feature vector to the SQLite feedback DB.
- Layer-2 retraining is a one-button operation in the UI (and a `make retrain` target).

## Phase 0 status

Layers are designed but not implemented. Implementation arrives in Phase 4 alongside the 15+ Markdown runbooks.
