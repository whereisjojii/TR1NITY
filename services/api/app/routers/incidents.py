"""Incident-domain routes — the Cockpit's primary surface.

Endpoints:

* ``GET  /api/incidents``                 — list with FP-score sort
* ``GET  /api/incidents/{id}``            — single-incident detail
* ``POST /api/incidents/{id}/mark-fp``    — analyst FP feedback (Phase 3 store)
* ``POST /api/incidents/refresh``         — force one correlator tick
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..clients.correlator import CorrelatorClient, CorrelatorUnavailableError
from ..clients.opensearch import OpenSearchIncidentReader
from ..config import APISettings
from ..dependencies import (
    get_correlator_client,
    get_opensearch_reader,
    get_settings_dep,
    get_store_dep,
)
from ..incidents import compose_incidents
from ..realtime import ConnectionManager, get_connection_manager
from ..store import CockpitStore, FPFeedback

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


SortKey = Literal["fp_score", "severity", "created_at", "last_event_at"]


class IncidentListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    fetched_at: str


class FPMarkRequest(BaseModel):
    is_fp: bool
    reason: str | None = Field(default=None, max_length=2000)
    submitted_by: str = Field(default="anonymous", max_length=200)


class FPMarkResponse(BaseModel):
    incident_id: str
    fp_score: float
    feedback: dict[str, Any]


class IncidentRefreshResponse(BaseModel):
    triggered: bool
    incident_count: int
    sinks: list[dict[str, Any]] = Field(default_factory=list)


def _gather_sources(
    *,
    correlator: CorrelatorClient,
    opensearch: OpenSearchIncidentReader,
    settings: APISettings,
    store: CockpitStore,
    include_persisted: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Pull incident dicts from every available source.

    Order: correlator (in-memory tick) → api recent buffer → OpenSearch.
    All three are merged + deduped in :func:`compose_incidents`.
    """
    correlator_items: list[dict[str, Any]] = []
    try:
        correlator_items = correlator.list_incidents()
    except CorrelatorUnavailableError as exc:
        log.warning("correlator unavailable: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("unexpected correlator failure: %s", exc)

    if correlator_items:
        store.remember_incidents(correlator_items)

    cached_items = store.list_recent_incidents()

    persisted_items: list[dict[str, Any]] = []
    if include_persisted:
        try:
            persisted_items = opensearch.search_incidents(
                size=settings.incidents_max_page_size,
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("opensearch read failed: %s", exc)

    return correlator_items, cached_items, persisted_items


@router.get("", response_model=IncidentListResponse)
def list_incidents(
    *,
    sort_by: SortKey = Query(default="fp_score"),
    descending: bool = Query(default=False),
    severity_min: int | None = Query(default=None, ge=0, le=7),
    sources: list[str] | None = Query(default=None),
    technique: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=1000),
    include_persisted: bool = Query(default=True),
    correlator: CorrelatorClient = Depends(get_correlator_client),
    opensearch: OpenSearchIncidentReader = Depends(get_opensearch_reader),
    settings: APISettings = Depends(get_settings_dep),
    store: CockpitStore = Depends(get_store_dep),
) -> IncidentListResponse:
    """List incidents available to the Cockpit, sorted for triage.

    Default sort is ``fp_score`` ascending — most likely true positives
    first. The roadmap mandates this ordering for the queue.
    """
    correlator_items, cached_items, persisted_items = _gather_sources(
        correlator=correlator,
        opensearch=opensearch,
        settings=settings,
        store=store,
        include_persisted=include_persisted,
    )
    items = compose_incidents(
        correlator_items=correlator_items,
        cached_items=cached_items,
        opensearch_items=persisted_items,
        store=store,
        sort_by=sort_by,
        descending=descending,
        severity_min=severity_min,
        sources=sources,
        technique=technique,
        limit=limit,
    )
    return IncidentListResponse(
        items=items,
        total=len(items),
        fetched_at=datetime.now(UTC).isoformat(),
    )


@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    *,
    correlator: CorrelatorClient = Depends(get_correlator_client),
    opensearch: OpenSearchIncidentReader = Depends(get_opensearch_reader),
    settings: APISettings = Depends(get_settings_dep),
    store: CockpitStore = Depends(get_store_dep),
) -> dict[str, Any]:
    """Return a single incident, decorated with FP score and feedback."""
    correlator_items, cached_items, persisted_items = _gather_sources(
        correlator=correlator,
        opensearch=opensearch,
        settings=settings,
        store=store,
        include_persisted=True,
    )
    items = compose_incidents(
        correlator_items=correlator_items,
        cached_items=cached_items,
        opensearch_items=persisted_items,
        store=store,
    )
    for inc in items:
        if inc.get("incident_id") == incident_id:
            return inc
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"incident {incident_id!r} not found",
    )


@router.post("/{incident_id}/mark-fp", response_model=FPMarkResponse)
def mark_fp(
    incident_id: str,
    payload: FPMarkRequest,
    store: CockpitStore = Depends(get_store_dep),
) -> FPMarkResponse:
    """Record analyst FP feedback for an incident.

    Phase 3 stores the feedback in process; Phase 4 persists to Postgres
    and feeds the sklearn classifier on weekly retrain.
    """
    feedback = store.record_fp(
        FPFeedback(
            incident_id=incident_id,
            is_fp=payload.is_fp,
            reason=payload.reason,
            source="analyst",
            submitted_by=payload.submitted_by or "anonymous",
        )
    )
    return FPMarkResponse(
        incident_id=incident_id,
        fp_score=store.fp_score(incident_id),
        feedback=feedback.to_dict(),
    )


@router.post("/refresh", response_model=IncidentRefreshResponse)
async def refresh_incidents(
    *,
    correlator: CorrelatorClient = Depends(get_correlator_client),
    store: CockpitStore = Depends(get_store_dep),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> IncidentRefreshResponse:
    """Force the correlator to tick, refresh the recent buffer, broadcast.

    Used by the Cockpit's ``r``-key shortcut and by ``make demo`` so the
    UI shows the synthetic chain immediately rather than waiting for the
    next scheduled tick.
    """
    try:
        result = correlator.trigger_tick()
    except CorrelatorUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"correlator unavailable: {exc}",
        ) from exc
    incidents = result.get("incidents") or []
    if isinstance(incidents, list):
        store.remember_incidents(i for i in incidents if isinstance(i, dict))
        await manager.broadcast_new([i for i in incidents if isinstance(i, dict)])
    return IncidentRefreshResponse(
        triggered=True,
        incident_count=int(result.get("incident_count") or len(incidents)),
        sinks=list(result.get("sinks") or []),
    )
