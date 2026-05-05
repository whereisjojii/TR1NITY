"""OpenSearch EventConsumer.

Polls ``tr1nity-events-*`` for new documents using a simple
``range`` query keyed on ``@timestamp``. We deliberately use the
high-water-mark pattern instead of OpenSearch's PIT/scroll: it is
trivially restartable, works without admin privileges, and never
gets stuck on a stale scroll cursor.

The consumer keeps the high-water-mark in process memory only —
operators get at-least-once delivery with no duplicates within one
process lifetime, and on restart the correlator simply starts from
"now" and replays via ``replay_from`` if needed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenSearchEventConsumer:
    """High-water-mark poller against OpenSearch."""

    base_url: str
    index_pattern: str = "tr1nity-events-*"
    username: str = ""
    password: str = ""
    verify_tls: bool = True
    timeout_seconds: float = 10.0
    transport: httpx.BaseTransport | None = None
    _client: httpx.Client | None = field(default=None, init=False, repr=False)
    _high_water: datetime | None = field(default=None, init=False)

    def _http(self) -> httpx.Client:
        if self._client is None:
            auth: httpx.BasicAuth | None = None
            if self.username:
                auth = httpx.BasicAuth(self.username, self.password)
            self._client = httpx.Client(
                base_url=self.base_url,
                auth=auth,
                verify=self.verify_tls,
                timeout=self.timeout_seconds,
                transport=self.transport,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def replay_from(self, start: datetime) -> None:
        """Reset the high-water-mark; next ``fetch`` returns events newer than ``start``."""
        self._high_water = start

    def fetch(self, *, max_events: int) -> list[dict[str, Any]]:
        # Default high-water on first call: "now" minus a small grace
        # window so we don't lose events that arrived just before startup.
        if self._high_water is None:
            self._high_water = datetime.now(UTC).replace(microsecond=0)

        query = {
            "size": int(max_events),
            "sort": [{"@timestamp": {"order": "asc"}}],
            "query": {"range": {"@timestamp": {"gt": self._high_water.isoformat()}}},
        }

        try:
            resp = self._http().post(
                f"/{self.index_pattern}/_search",
                content=json.dumps(query),
                headers={"Content-Type": "application/json"},
            )
        except httpx.HTTPError as exc:
            log.warning("OpenSearchEventConsumer: network error: %s", exc)
            return []

        if resp.status_code in (401, 403):
            log.warning("OpenSearchEventConsumer: auth error HTTP %s", resp.status_code)
            return []
        if resp.status_code >= 400:
            log.warning("OpenSearchEventConsumer: HTTP %s on search", resp.status_code)
            return []

        try:
            payload = resp.json()
        except json.JSONDecodeError:
            log.warning("OpenSearchEventConsumer: response not JSON")
            return []

        hits = (payload.get("hits") or {}).get("hits") or []
        out: list[dict[str, Any]] = []
        latest = self._high_water
        for hit in hits:
            src = hit.get("_source")
            if not isinstance(src, dict):
                continue
            out.append(src)
            ts = src.get("@timestamp") or src.get("timestamp")
            if isinstance(ts, str):
                try:
                    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if latest is None or parsed > latest:
                    latest = parsed
        if latest is not None:
            self._high_water = latest
        return out
