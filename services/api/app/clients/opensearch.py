"""Read-only OpenSearch client for the persisted ``tr1nity-incidents-*`` index.

The correlator writes correlated incidents to ``tr1nity-incidents-YYYY.MM.dd``
when ``DRY_RUN=false`` (Phase 2). The api service uses this client as a
*fallback* read source so the Cockpit still has incidents to render after
a correlator restart wipes ``last_incidents``.

We deliberately use raw ``httpx`` (no ``opensearch-py``) to keep the
dependency tree small — same justification as the ingestor and correlator
sinks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenSearchIncidentReader:
    """Read recent incidents from the persisted index pattern."""

    base_url: str
    username: str = ""
    password: str = ""
    verify_tls: bool = True
    index_pattern: str = "tr1nity-incidents-*"
    timeout_seconds: float = 5.0
    transport: httpx.BaseTransport | None = None
    name: str = "opensearch"
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

    def search_incidents(
        self,
        *,
        size: int = 100,
        sort_desc: bool = True,
    ) -> list[dict[str, Any]]:
        """Return the most recent incidents from the persisted index.

        Returns an empty list if OpenSearch is unreachable or the index
        does not yet exist — the api routers are responsible for
        composing this with the correlator's in-memory view.
        """
        body = {
            "size": min(max(int(size), 1), 1000),
            "sort": [{"created_at": {"order": "desc" if sort_desc else "asc"}}],
            "query": {"match_all": {}},
        }
        try:
            resp = self._http().post(f"/{self.index_pattern}/_search", json=body)
        except httpx.HTTPError as exc:
            log.warning("OpenSearchIncidentReader: network failure: %s", exc)
            return []
        if resp.status_code == 404:
            # Index doesn't exist yet — totally fine for a fresh stack.
            return []
        if resp.status_code >= 400:
            log.warning("OpenSearchIncidentReader: HTTP %s", resp.status_code)
            return []
        try:
            payload = resp.json()
        except ValueError:
            return []
        hits = payload.get("hits", {}).get("hits", []) if isinstance(payload, dict) else []
        out: list[dict[str, Any]] = []
        for hit in hits:
            if isinstance(hit, dict) and isinstance(hit.get("_source"), dict):
                out.append(hit["_source"])
        return out
