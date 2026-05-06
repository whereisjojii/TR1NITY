"""HTTP client for the Phase-2 correlator service.

The api service exposes incidents to the React Cockpit. The actual
incident store is owned by the correlator (it ticks every ``N`` seconds
and caches the last batch in ``app.state.pipeline.last_incidents``). We
proxy reads against ``GET /incidents`` and trigger ticks via
``POST /correlate`` when a development cockpit needs fresh data on
demand.

Errors are mapped to a small custom hierarchy so the API routers can
surface clean 502/503 responses instead of raw httpx tracebacks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)


class CorrelatorError(RuntimeError):
    """Base class for correlator-client failures."""


class CorrelatorUnavailableError(CorrelatorError):
    """Raised when the correlator is unreachable or returned 5xx."""


@dataclass(slots=True)
class CorrelatorClient:
    """Thin HTTP wrapper around the correlator's read API."""

    base_url: str
    timeout_seconds: float = 5.0
    transport: httpx.BaseTransport | None = None
    name: str = "correlator"
    _client: httpx.Client | None = field(default=None, init=False, repr=False)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------

    def healthy(self) -> bool:
        """Quick liveness probe — used by ``/readyz``."""
        try:
            resp = self._http().get("/healthz")
        except httpx.HTTPError:
            return False
        return resp.status_code == 200

    def list_incidents(self) -> list[dict[str, Any]]:
        """Return the correlator's most recent batch of incidents.

        The correlator's ``GET /incidents`` returns
        ``{"items": [...], "total": N}``. We unwrap to a flat list so
        the api can compose it with other sources (Postgres, OpenSearch).
        """
        try:
            resp = self._http().get("/incidents")
        except httpx.HTTPError as exc:
            raise CorrelatorUnavailableError(f"network: {type(exc).__name__}: {exc}") from exc
        if resp.status_code >= 500:
            raise CorrelatorUnavailableError(f"upstream: HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise CorrelatorError(f"client: HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:  # pragma: no cover - defensive
            raise CorrelatorError(f"decode: {exc}") from exc
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def trigger_tick(self) -> dict[str, Any]:
        """Force the correlator to run one tick and return the result.

        Useful for the dev-flow ``make demo`` and for the Cockpit's
        ``r``-key "reload" shortcut. Production deployments rely on the
        correlator's own scheduler.
        """
        try:
            resp = self._http().post("/correlate")
        except httpx.HTTPError as exc:
            raise CorrelatorUnavailableError(f"network: {type(exc).__name__}: {exc}") from exc
        if resp.status_code >= 500:
            raise CorrelatorUnavailableError(f"upstream: HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise CorrelatorError(f"client: HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:  # pragma: no cover - defensive
            raise CorrelatorError(f"decode: {exc}") from exc
        return payload if isinstance(payload, dict) else {}
