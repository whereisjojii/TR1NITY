# TR1NITY Runbooks

Phase 4 ships 15 actionable ATT&CK-keyed runbooks. Each markdown file
under this directory has a YAML frontmatter block — the api service
loads it at startup (`services/api/app/runbooks.py`) and serves it to
the Cockpit's incident-detail page when the analyst opens the
**Runbook** tab.

## Frontmatter contract

```yaml
---
technique: T1110.001 # required — full or sub-technique id
tactic: TA0006 # optional — primary tactic id
title: Password Guessing # short title shown in the UI badge
severity: high # info | low | medium | high | critical
references:
  - https://attack.mitre.org/techniques/T1110/001/
---
```

After the frontmatter, write standard markdown (headings, lists, code
blocks). A consistent four-section structure makes pages skimmable
under pressure: **Triage → Investigation → Containment →
Eradication & lessons**.

## Index

| Technique | Title                                  | Severity |
| --------- | -------------------------------------- | -------- |
| T1110     | Brute force                            | high     |
| T1110.001 | Password guessing                      | high     |
| T1110.003 | Password spraying                      | high     |
| T1078     | Valid accounts                         | high     |
| T1190     | Exploit public-facing application      | critical |
| T1595     | Active scanning                        | medium   |
| T1046     | Network service scanning               | medium   |
| T1083     | File and directory discovery           | medium   |
| T1059     | Command and scripting interpreter      | high     |
| T1059.001 | PowerShell                             | high     |
| T1003     | OS credential dumping                  | critical |
| T1486     | Data encrypted for impact (ransomware) | critical |
| T1566     | Phishing                               | high     |
| T1071     | Application-layer protocol (C2)        | high     |
| T1027     | Obfuscated files or information        | medium   |
| T1018     | Remote system discovery                | low      |

## Adding a runbook

1. Create `docs/runbooks/T<id>.md` with the YAML frontmatter block.
2. Restart the api service (or call `library.reload()` from a future
   admin endpoint) to pick it up.
3. Reference the URL `/api/runbooks/T<id>` from the Cockpit (auto-
   attached for incidents whose primary technique matches).
