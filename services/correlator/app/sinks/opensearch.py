"""OpenSearch incident sink.

Writes finalized incidents into ``tr1nity-incidents-YYYY.MM.dd`` using
the OpenSearch ``_bulk`` endpoint. Mirrors the ingestor's
``OpenSearchSink`` shape (auth, TLS, per-item status accounting) so the
two services share the same operational surface — one set of metrics,
one set of failure modes.

We deliberately use raw ``httpx`` instead of the official OpenSearch
client: the official client pulls a heavy dependency tree and the only
endpoint we need is ``_bulk``. ``httpx.Client`` is enough.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from ..incident import Incident
from .base import SinkResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenSearchIncidentSink:
    """POST incidents to OpenSearch ``_bulk``."""

    base_url: str
    username: str = ""
    password: str = ""
    verify_tls: bool = True
    index_prefix: str = "tr1nity-incidents"
    timeout_seconds: float = 10.0
    name: str = "opensearch"
    transport: httpx.BaseTransport | None = None
    _client: httpx.Client | None = field(default=None, init=False, repr=False)

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

    # ------------------------------------------------------------------

    def _index_for(self, ts: datetime) -> str:
        return f"{self.index_prefix}-{ts.astimezone(UTC):%Y.%m.%d}"

    def _build_bulk(self, incidents: list[Incident]) -> str:
        lines: list[str] = []
        for inc in incidents:
            doc = inc.to_index_doc()
            index = self._index_for(inc.created_at)
            lines.append(json.dumps({"index": {"_index": index, "_id": inc.incident_id}}))
            lines.append(json.dumps(doc, default=str))
        return "\n".join(lines) + "\n"

    def write(self, incidents: list[Incident]) -> SinkResult:
        result = SinkResult(sink=self.name)
        if not incidents:
            return result

        body = self._build_bulk(incidents)
        try:
            resp = self._http().post(
                "/_bulk",
                content=body,
                headers={"Content-Type": "application/x-ndjson"},
            )
        except httpx.HTTPError as exc:
            msg = f"network: {type(exc).__name__}: {exc}"
            result.errors.append(msg)
            result.rejected += len(incidents)
            log.warning("OpenSearchIncidentSink: %s", msg)
            return result

        if resp.status_code in (401, 403):
            result.errors.append(f"auth: HTTP {resp.status_code}")
            result.rejected += len(incidents)
            return result
        if resp.status_code >= 500:
            result.errors.append(f"server: HTTP {resp.status_code}")
            result.rejected += len(incidents)
            return result
        if resp.status_code >= 400:
            result.errors.append(f"client: HTTP {resp.status_code}")
            result.rejected += len(incidents)
            return result

        try:
            payload = resp.json()
        except json.JSONDecodeError:
            result.errors.append("server: response not JSON")
            result.rejected += len(incidents)
            return result

        items = payload.get("items") or []
        for item in items:
            op = item.get("index") or {}
            status = op.get("status", 0)
            if 200 <= status < 300:
                result.accepted += 1
            else:
                result.rejected += 1
                err = op.get("error") or {}
                err_type = err.get("type") if isinstance(err, dict) else None
                err_reason = err.get("reason") if isinstance(err, dict) else None
                result.errors.append(f"item {op.get('_id')}: {err_type}: {err_reason}")

        # If OpenSearch returned no items at all (unexpected) treat the
        # whole batch as rejected so we surface the anomaly upstream.
        if not items:
            result.rejected += len(incidents)
            result.errors.append("server: empty items[]")
        return result
