"""ATT&CK heatmap routes.

The Cockpit's ATT&CK Navigator-style heatmap consumes a small JSON
payload of technique frequencies derived from the incidents the api can
see. Phase 4 will layer rule coverage on top (which techniques have a
deployed SIGMA rule, when it last fired, etc.).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
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
from ..incidents import compose_incidents, compute_attack_heatmap
from ..store import CockpitStore

router = APIRouter(prefix="/api/attack", tags=["attack"])


CoverageStatus = Literal["covered", "partial", "uncovered"]


class HeatmapTechnique(BaseModel):
    id: str
    count: int
    tactics: list[str] = Field(default_factory=list)


class HeatmapTactic(BaseModel):
    id: str
    count: int


class HeatmapResponse(BaseModel):
    techniques: list[HeatmapTechnique]
    tactics: list[HeatmapTactic]
    total_incidents: int
    covered_incidents: int
    fetched_at: str


@router.get("/heatmap", response_model=HeatmapResponse)
def heatmap(
    *,
    severity_min: int | None = Query(default=None, ge=0, le=7),
    correlator: CorrelatorClient = Depends(get_correlator_client),
    opensearch: OpenSearchIncidentReader = Depends(get_opensearch_reader),
    settings: APISettings = Depends(get_settings_dep),
    store: CockpitStore = Depends(get_store_dep),
) -> HeatmapResponse:
    correlator_items: list[dict[str, Any]] = []
    try:
        correlator_items = correlator.list_incidents()
    except CorrelatorUnavailableError:
        correlator_items = []

    if correlator_items:
        store.remember_incidents(correlator_items)

    persisted_items: list[dict[str, Any]] = []
    try:
        persisted_items = opensearch.search_incidents(
            size=settings.incidents_max_page_size,
        )
    except Exception:
        persisted_items = []

    incidents = compose_incidents(
        correlator_items=correlator_items,
        cached_items=store.list_recent_incidents(),
        opensearch_items=persisted_items,
        store=store,
        severity_min=severity_min,
    )
    summary = compute_attack_heatmap(incidents)
    return HeatmapResponse(
        techniques=[HeatmapTechnique(**t) for t in summary["techniques"]],
        tactics=[HeatmapTactic(**t) for t in summary["tactics"]],
        total_incidents=summary["total_incidents"],
        covered_incidents=summary["covered_incidents"],
        fetched_at=datetime.now(UTC).isoformat(),
    )
