"""TTL-bounded in-memory cache wrapping one or more providers.

We keep this dependency-free on purpose. Each entry is keyed by
``(provider_name, indicator_type, indicator)`` and stores both the list
of hits and the wall-clock at which it expires. Lookups outside the
TTL re-call the provider; lookups within the TTL return cached results.

Only positive AND negative results are cached — caching the absence of
a hit is what saves the correlator from hammering a feed for the same
benign IP across thousands of events.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .base import IntelHit, Provider


@runtime_checkable
class TimeSource(Protocol):
    """Anything that exposes a callable ``time()`` returning seconds-since-epoch.

    Lets tests inject a fake clock without ``time.sleep`` and without
    monkeypatching the global ``time`` module. Both the real ``time``
    module and ``types.SimpleNamespace(time=lambda: ...)`` satisfy this.
    """

    def time(self) -> float: ...


@dataclass(slots=True)
class _Entry:
    hits: list[IntelHit]
    expires_at: float


@dataclass(slots=True)
class IntelCache:
    """Wrap a list of providers with TTL caching.

    ``ttl_seconds`` is the cache lifetime; ``time_source`` is any object
    matching the ``TimeSource`` protocol — injectable for tests so we
    don't have to ``time.sleep`` to expire entries.
    """

    providers: list[Provider]
    ttl_seconds: int = 3600
    time_source: TimeSource = field(default_factory=lambda: time)
    _store: dict[tuple[str, str, str], _Entry] = field(default_factory=dict)

    def _now(self) -> float:
        return float(self.time_source.time())

    def _lookup(self, kind: str, indicator: str) -> list[IntelHit]:
        if not self.providers:
            return []
        out: list[IntelHit] = []
        for provider in self.providers:
            key = (provider.name, kind, indicator)
            entry = self._store.get(key)
            now = self._now()
            if entry is not None and entry.expires_at > now:
                out.extend(entry.hits)
                continue

            if kind == "ip":
                hits = list(provider.lookup_ip(indicator))
            elif kind == "domain":
                hits = list(provider.lookup_domain(indicator))
            else:
                hits = []
            self._store[key] = _Entry(hits=hits, expires_at=now + self.ttl_seconds)
            out.extend(hits)
        return out

    def lookup_ip(self, ip: str) -> list[IntelHit]:
        return self._lookup("ip", ip)

    def lookup_domain(self, domain: str) -> list[IntelHit]:
        return self._lookup("domain", domain)

    def clear(self) -> None:
        self._store.clear()
