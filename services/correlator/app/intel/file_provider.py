"""File-based intel provider.

Loads a JSON document on construction and answers lookups in-memory.
This is the default provider TR1NITY ships with so the correlator works
out-of-the-box on a fresh checkout — no internet required, no API keys.

The file format is intentionally trivial (and stable), so operators can
edit it by hand or sync it from any external feed they trust:

```json
{
  "ips": {
    "203.0.113.45": {
      "feed": "tr1nity-bundled",
      "tags": ["botnet", "scanner"],
      "description": "Documentation IP — used in tests"
    }
  },
  "domains": {
    "evil.example.com": {
      "feed": "tr1nity-bundled",
      "tags": ["c2"],
      "description": "Documentation domain"
    }
  }
}
```

Operators can swap this file for a snapshot from any free feed (e.g.
abuse.ch SSL blacklist, SANS ISC blocklist, Spamhaus DROP) — the format
is small enough to translate with a few lines of jq or Python.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import IntelHit

log = logging.getLogger(__name__)


@dataclass(slots=True)
class FileProvider:
    """Static, file-backed indicator provider."""

    name: str
    ips: dict[str, dict[str, Any]]
    domains: dict[str, dict[str, Any]]

    @classmethod
    def from_file(cls, path: str | Path, *, name: str = "tr1nity-file") -> FileProvider:
        """Load a JSON file. Missing file → empty provider (warns, doesn't fail).

        The correlator service should boot even if the operator hasn't
        populated an IOC list yet — turning every miss into 0 hits is
        exactly the right default.
        """
        p = Path(path)
        if not p.is_file():
            log.warning("FileProvider: %s does not exist; provider is empty", p)
            return cls(name=name, ips={}, domains={})
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.exception("FileProvider: %s is not valid JSON; provider is empty", p)
            return cls(name=name, ips={}, domains={})
        ips = data.get("ips") or {}
        domains = data.get("domains") or {}
        if not isinstance(ips, dict) or not isinstance(domains, dict):
            log.warning("FileProvider: %s has wrong shape; provider is empty", p)
            return cls(name=name, ips={}, domains={})
        return cls(name=name, ips=ips, domains=domains)

    def _entry_to_hit(self, indicator: str, kind: str, entry: dict[str, Any]) -> IntelHit:
        return IntelHit(
            indicator=indicator,
            indicator_type=kind,
            feed=str(entry.get("feed") or self.name),
            description=entry.get("description"),
            tags=tuple(str(t) for t in (entry.get("tags") or [])),
            confidence=int(entry.get("confidence") or 0),
        )

    def lookup_ip(self, ip: str) -> list[IntelHit]:
        entry = self.ips.get(ip)
        return [self._entry_to_hit(ip, "ip", entry)] if entry else []

    def lookup_domain(self, domain: str) -> list[IntelHit]:
        entry = self.domains.get(domain.lower())
        return [self._entry_to_hit(domain, "domain", entry)] if entry else []
