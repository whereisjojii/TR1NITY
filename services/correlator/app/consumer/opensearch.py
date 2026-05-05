"""OpenSearch EventConsumer.

Polls ``tr1nity-events-*`` for new documents using a ``range`` query
keyed on ``@timestamp``. We deliberately use the high-water-mark
pattern instead of OpenSearch's PIT/scroll: it is trivially restartable,
works without admin privileges, and never gets stuck on a stale scroll
cursor.

Delivery semantics: at-least-once during a single process lifetime,
with **no skipped events at boundary timestamps**. The query uses
``gte`` (so events sharing the high-water timestamp are not lost when a
batch boundary lands mid-millisecond), and a per-boundary set of seen
``_id`` values is carried across calls so those re-fetched documents
are filtered out before they reach the pipeline. On restart the
correlator starts from "now" and operators can rewind with
``replay_from`` if needed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

log = logging.getLogger(__name__)

# How far back the first poll reaches when no high-water-mark has been
# set yet. Without this, events written between process start and the
# very first poll would fall on the wrong side of "now" and be missed.
_STARTUP_GRACE = timedelta(seconds=60)


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
    # ``_id``s seen at exactly ``_high_water``. We re-query inclusively
    # (``gte``) and filter these out so events sharing the boundary
    # timestamp are never permanently skipped.
    _seen_at_boundary: set[str] = field(default_factory=set, init=False)

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
        """Reset the high-water-mark; next ``fetch`` returns events at or after ``start``."""
        self._high_water = start
        self._seen_at_boundary = set()

    def fetch(self, *, max_events: int) -> list[dict[str, Any]]:
        # Default high-water on first call: "now" minus a small grace
        # window so we don't lose events that arrived just before startup.
        if self._high_water is None:
            self._high_water = datetime.now(UTC).replace(microsecond=0) - _STARTUP_GRACE

        query = {
            "size": int(max_events),
            # Sort by timestamp then document id so two events sharing a
            # timestamp have a deterministic ordering inside the batch.
            "sort": [{"@timestamp": {"order": "asc"}}, {"_id": {"order": "asc"}}],
            "query": {"range": {"@timestamp": {"gte": self._high_water.isoformat()}}},
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
        new_boundary_ids: set[str] = set()
        for hit in hits:
            src = hit.get("_source")
            if not isinstance(src, dict):
                continue
            doc_id = str(hit.get("_id") or "")

            # Drop documents we already returned at the previous boundary.
            if doc_id and doc_id in self._seen_at_boundary:
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
                    new_boundary_ids = {doc_id} if doc_id else set()
                elif parsed == latest and doc_id:
                    new_boundary_ids.add(doc_id)

        if latest is not None:
            if latest != self._high_water:
                self._high_water = latest
                self._seen_at_boundary = new_boundary_ids
            else:
                # No timestamp progress this batch — extend the boundary set.
                self._seen_at_boundary |= new_boundary_ids
        return out
