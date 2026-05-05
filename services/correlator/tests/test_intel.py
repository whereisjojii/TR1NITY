"""Threat-intel cache + file-provider tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.intel.base import IntelHit
from app.intel.cache import IntelCache
from app.intel.file_provider import FileProvider


def test_file_provider_loads_bundled_starter() -> None:
    bundled = Path(__file__).resolve().parents[1] / "app" / "intel" / "data" / "ioc.json"
    provider = FileProvider.from_file(bundled)
    hits = provider.lookup_ip("203.0.113.45")
    assert len(hits) == 1
    assert hits[0].feed == "tr1nity-bundled"


def test_file_provider_returns_empty_for_unknown() -> None:
    bundled = Path(__file__).resolve().parents[1] / "app" / "intel" / "data" / "ioc.json"
    provider = FileProvider.from_file(bundled)
    assert provider.lookup_ip("8.8.8.8") == []
    assert provider.lookup_domain("example.org") == []


def test_file_provider_handles_missing_file(tmp_path: Path) -> None:
    provider = FileProvider.from_file(tmp_path / "nope.json")
    assert provider.ips == {}
    assert provider.domains == {}


def test_file_provider_handles_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    provider = FileProvider.from_file(bad)
    assert provider.ips == {}


def test_cache_returns_hits_within_ttl() -> None:
    fake_clock = SimpleNamespace(_now=0.0)
    fake_clock.time = lambda: fake_clock._now  # type: ignore[attr-defined]

    class CountingProvider:
        name = "count"

        def __init__(self) -> None:
            self.calls = 0

        def lookup_ip(self, ip: str) -> list[IntelHit]:
            self.calls += 1
            return [IntelHit(indicator=ip, indicator_type="ip", feed="count")]

        def lookup_domain(self, domain: str) -> list[IntelHit]:  # pragma: no cover
            return []

    provider = CountingProvider()
    cache = IntelCache(providers=[provider], ttl_seconds=10, time_source=fake_clock)

    cache.lookup_ip("1.1.1.1")
    cache.lookup_ip("1.1.1.1")
    assert provider.calls == 1

    fake_clock._now = 11.0
    cache.lookup_ip("1.1.1.1")
    assert provider.calls == 2


def test_cache_caches_negative_results() -> None:
    fake_clock = SimpleNamespace(_now=0.0)
    fake_clock.time = lambda: fake_clock._now  # type: ignore[attr-defined]

    class EmptyProvider:
        name = "empty"

        def __init__(self) -> None:
            self.calls = 0

        def lookup_ip(self, ip: str) -> list[IntelHit]:
            self.calls += 1
            return []

        def lookup_domain(self, domain: str) -> list[IntelHit]:  # pragma: no cover
            return []

    provider = EmptyProvider()
    cache = IntelCache(providers=[provider], ttl_seconds=60, time_source=fake_clock)
    cache.lookup_ip("1.1.1.1")
    cache.lookup_ip("1.1.1.1")
    assert provider.calls == 1


def test_cache_clear_drops_entries() -> None:
    bundled = Path(__file__).resolve().parents[1] / "app" / "intel" / "data" / "ioc.json"
    provider = FileProvider.from_file(bundled)
    cache = IntelCache(providers=[provider], ttl_seconds=60)
    cache.lookup_ip("203.0.113.45")
    assert cache._store
    cache.clear()
    assert cache._store == {}


def test_file_provider_loads_custom_file(tmp_path: Path) -> None:
    p = tmp_path / "custom.json"
    p.write_text(
        json.dumps(
            {
                "ips": {
                    "10.0.0.1": {
                        "feed": "internal-blocklist",
                        "tags": ["lab"],
                        "description": "lab attacker",
                        "confidence": 50,
                    }
                },
                "domains": {},
            }
        ),
        encoding="utf-8",
    )
    provider = FileProvider.from_file(p, name="custom")
    hits = provider.lookup_ip("10.0.0.1")
    assert hits[0].feed == "internal-blocklist"
    assert hits[0].confidence == 50
    assert "lab" in hits[0].tags
