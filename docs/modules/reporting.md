# M6 · Knowledge, Audit & Reporting

**Phase:** 6 · **Tag:** `v1.0.0` · **Lives in:** [`services/api/`](https://github.com/whereisjojii/TR1NITY/tree/main/services/api) (reporting sub-module) and [`configs/runbooks/`](https://github.com/whereisjojii/TR1NITY/tree/main/configs)

## Goal

Make TR1NITY presentable to non-analyst stakeholders (auditors, management, university examiners) and recoverable in case of disaster.

## What ships in v1.0

### Runbooks

15+ Markdown runbooks shipped with the platform, auto-attached to incidents by primary ATT&CK technique. Examples:

- T1110.001 — Brute-force password attack
- T1078 — Valid accounts (suspicious login)
- T1190 — Exploit public-facing application (web)
- T1046 — Network service scanning
- T1041 — Exfiltration over C2 channel

Operators can edit, add, or override runbooks; all edits are versioned in PostgreSQL with audit trail.

### Audit trail

Every analyst action is journaled:

| Field | Example |
|-------|---------|
| `actor` | hammad@air.edu.pk |
| `action` | `incident.mark_fp` |
| `target` | `incident-2026-05-03-3829` |
| `before` / `after` | JSON diffs |
| `timestamp` | UTC, monotonic |

The journal is append-only and is included in compliance PDF exports.

### Compliance PDF generator

One-click export from the Cockpit with sections for:

- **PCI-DSS** (12 sections + sub-controls; mapped to TR1NITY-collected evidence)
- **ISO 27001 Annex A** (controls A.5–A.18)
- **NIST Cybersecurity Framework** (Identify / Protect / Detect / Respond / Recover)

Powered by WeasyPrint or ReportLab; output is `compliance-<framework>-<date>.pdf` with valid section numbering and download link.

### Weekly metrics

A cron-driven Markdown + PDF report:

- Alert volume by source
- FP rate trend (Layer 1 / 2 / 3 contributions)
- MTTR (mean time to resolve)
- Top-firing rules + suppressed rules
- ATT&CK coverage delta vs. previous week
- New runbooks authored

### Backup & restore

```bash
make backup    # produces backup-<timestamp>.tar.gz
make restore F=backup-2026-05-03.tar.gz
```

The tarball contains:

- PostgreSQL dump (cases, audit, FP feedback, runbook history)
- ChromaDB collections
- SIGMA rule overrides
- ML model pickle
- ISM index policies
- `.env` (encrypted)

Restoring on a clean install reproduces the original platform state byte-for-byte for the test cases that matter.

## Phase 0 status

Designed but not implemented. Lands at v1.0.0.
