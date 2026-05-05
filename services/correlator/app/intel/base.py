"""Threat-intel provider protocol + the ``IntelHit`` value object.

Providers are stateless from the correlator's point of view. The cache
layer wraps each provider with TTL + memoization, so providers
themselves never need to think about retention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class IntelHit:
    """One enrichment result for one indicator.

    Stored on Incidents under ``intel_hits``. Conservative shape — we keep
    it small so OpenSearch indices stay light and Cockpit can render
    without follow-up queries.
    """

    indicator: str
    indicator_type: str  # "ip" / "domain" / "url" / "hash"
    feed: str
    description: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    confidence: int = 0  # 0-100; provider-specific


@runtime_checkable
class Provider(Protocol):
    """One threat-intel feed.

    Implementations must be deterministic for a given input — the cache
    layer assumes the same indicator returns the same set of hits within
    the TTL window.
    """

    name: str

    def lookup_ip(self, ip: str) -> list[IntelHit]:
        """Return zero or more hits for an IP address."""
        ...

    def lookup_domain(self, domain: str) -> list[IntelHit]:
        """Return zero or more hits for a domain."""
        ...
