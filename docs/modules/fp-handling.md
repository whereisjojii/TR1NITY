# M4 · False-Positive Handling

**Phase:** 4 · **Tag:** `v0.5.0-feedback` · **Lives in:** [`services/api/app/fp/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/api/app/fp) (FP sub-module)
**Status:** Implemented in Phase 4.

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

## Wiring

- **Composite scorer:** `services/api/app/fp/scorer.py` — exposes `compose_fp_score(incident, whitelist_rules, suppression_rules, classifier, analyst_score)`. Returns a `ScoreBreakdown` containing `fp_score` (max of all layers) and `layers[]` (every layer that contributed, with detail).
- **Layer 1 (whitelist):** `services/api/app/fp/whitelist.py` + `whitelist.yaml`. Match supports scalar equality, list any-of, `"*"` wildcard, nested dicts, and dotted-path traversal of incident + member events. Override the path with `TR1NITY_API_FP_WHITELIST` (set to `off` to disable Layer 1 entirely).
- **Layer 2 (classifier):** `services/api/app/fp/classifier.py` + `features.py` + `train.py`. Default features: severity, member count, source count, technique count, sigma matches, intel hits, hour-of-day, internal-source flag, has-user, has-destination. Retrain with `make retrain` (requires `services/api/requirements-ml.txt`); the runtime gracefully degrades to `0.0` if no model is loaded.
- **Layer 3 (suppressions):** `services/api/app/fp/suppressions.py`. Persisted in SQLite alongside feedback. CRUD endpoints under `/api/suppressions` (list / create / get / delete; expired rules auto-pruned).
- **Feedback DB:** `services/api/app/fp/db.py` — SQLite, default path `services/api/data/feedback.sqlite` (override `TR1NITY_API_FP_DB`; empty path runs in-memory). Tables: `fp_feedback` (analyst clicks + feature snapshot for training reproducibility), `suppressions` (Layer-3 rules with TTL + audit trail).
- **Runbooks:** `services/api/app/runbooks.py` loads markdown under `docs/runbooks/` and exposes `GET /api/runbooks` + `GET /api/runbooks/{technique_id}`. Auto-attached to every incident as `runbook_url` based on the primary ATT&CK technique. Override the directory with `TR1NITY_API_RUNBOOKS_DIR`.
- **Operator command:** `make retrain` rebuilds the classifier from the SQLite feedback DB (requires ≥10 total samples and ≥3 per class). Writes the model + a JSON training report next to it.
