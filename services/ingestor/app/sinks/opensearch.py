"""OpenSearch / Wazuh-indexer sink.

Talks to OpenSearch's ``_bulk`` endpoint over HTTPS. We do **not** use the
official ``opensearch-py`` client — adding a heavy dependency for two HTTP
calls is unjustified, and our schema is small enough that hand-rolling the
bulk format is faster and easier to audit.

Failure handling:

* Network/timeout errors are caught and reported as a single ``rejected``
  batch with a short error message — events are NOT dropped silently.
* Non-2xx responses are parsed for per-item failures so that one bad doc
  cannot poison the whole batch.
* On startup-time auth issues (401/403), :py:meth:`healthy` returns False
  so that the readiness probe correctly reports the sink as unavailable.

The sink defaults to writing to a daily index ``{prefix}-YYYY.MM.dd``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from ..ecs import ECSEvent
from .base import EventSink, SinkResult

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=15.0, pool=5.0)
DEFAULT_INDEX_PREFIX = "tr1nity-events"


class OpenSearchSink(EventSink):
    name = "opensearch"

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        index_prefix: str = DEFAULT_INDEX_PREFIX,
        verify_tls: bool = True,
        timeout: httpx.Timeout | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._auth = (username, password) if username and password else None
        self._index_prefix = index_prefix
        self._verify = verify_tls
        # Allow tests to inject a mock transport
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout or DEFAULT_TIMEOUT,
            verify=verify_tls,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _index_for(self, ts: datetime) -> str:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return f"{self._index_prefix}-{ts.astimezone(UTC).strftime('%Y.%m.%d')}"

    def _bulk_body(self, events: Iterable[ECSEvent]) -> tuple[str, int]:
        """Render the NDJSON body for ``_bulk``.

        Returns ``(body, count)``. Each event becomes two NDJSON lines:
        an action header and the document itself.
        """
        buf: list[str] = []
        n = 0
        for ev in events:
            doc = ev.to_index_doc()
            ts = ev.timestamp if isinstance(ev.timestamp, datetime) else datetime.now(UTC)
            action = {
                "index": {
                    "_index": self._index_for(ts),
                    "_id": ev.event.id,
                }
            }
            buf.append(json.dumps(action, separators=(",", ":")))
            buf.append(json.dumps(doc, separators=(",", ":"), default=str))
            n += 1
        return "\n".join(buf) + "\n", n

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def write(self, events: Iterable[ECSEvent]) -> SinkResult:
        evs = list(events)
        if not evs:
            return SinkResult()
        body, count = self._bulk_body(evs)
        try:
            resp = await self._client.post(
                f"{self._base}/_bulk",
                content=body,
                headers={"Content-Type": "application/x-ndjson"},
                auth=self._auth,
            )
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.TransportError,
        ) as e:
            msg = f"opensearch-network: {type(e).__name__}: {e}"
            return SinkResult(rejected=count, errors=[msg])

        if resp.status_code >= 500:
            msg = f"opensearch-{resp.status_code}: server error"
            return SinkResult(rejected=count, errors=[msg])
        if resp.status_code in (401, 403):
            msg = f"opensearch-{resp.status_code}: auth failure"
            return SinkResult(rejected=count, errors=[msg])
        if resp.status_code >= 400:
            msg = f"opensearch-{resp.status_code}: {resp.text[:200]}"
            return SinkResult(rejected=count, errors=[msg])

        try:
            data = resp.json()
        except json.JSONDecodeError:
            return SinkResult(rejected=count, errors=["opensearch: non-JSON response"])

        accepted = 0
        rejected = 0
        errors: list[str] = []
        for item in data.get("items", []):
            op = next(iter(item.values())) if item else {}
            status = op.get("status", 0)
            if 200 <= status < 300:
                accepted += 1
            else:
                rejected += 1
                err = op.get("error", {})
                # Truncate to keep logs tight
                errors.append(f"{status}: {str(err)[:200]}")
        # Cap error list so a flood of failures cannot blow up the response.
        return SinkResult(accepted=accepted, rejected=rejected, errors=errors[:10])

    async def healthy(self) -> bool:
        try:
            resp = await self._client.get(f"{self._base}/_cluster/health", auth=self._auth)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError):
            return False
        if resp.status_code != 200:
            return False
        try:
            status = resp.json().get("status", "red")
        except json.JSONDecodeError:
            return False
        return status in {"green", "yellow"}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
