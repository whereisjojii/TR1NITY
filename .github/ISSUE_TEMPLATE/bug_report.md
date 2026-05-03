---
name: Bug report
about: Something is broken or behaving unexpectedly
title: "[bug] "
labels: ["bug", "triage"]
assignees: []
---

## Summary

<!-- One sentence describing the bug. -->

## Steps to reproduce

1.
2.
3.

## Expected behaviour

## Actual behaviour

## Logs

<details>
<summary>Container logs (from <code>make logs</code> or <code>docker compose logs &lt;service&gt;</code>)</summary>

```
paste logs here
```

</details>

## Environment

- **TR1NITY version / commit:**
- **Deployment profile:** Demo / Standard / Full AI
- **OS:** (e.g. Ubuntu 22.04)
- **CPU / RAM:** (e.g. Ryzen 7 3700X / 16 GB)
- **GPU:** (e.g. AMD RX 590 8 GB / NVIDIA RTX 3060 / none)
- **Docker / Compose version:** (`docker --version`, `docker compose version`)

## Relevant config

<!-- Any non-default env vars or config tweaks. Redact secrets. -->

## Severity

- [ ] Blocks ingestion / data loss
- [ ] Blocks correlation / wrong incident output
- [ ] UI broken / unusable
- [ ] Documentation
- [ ] Other
