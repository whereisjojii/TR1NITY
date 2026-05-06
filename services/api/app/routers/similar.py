"""\"Similar past incidents\" routes — Phase 3 heuristic implementation.

The roadmap commits Phase 3 to surfacing similar incidents. The Phase-5
target uses ChromaDB cosine similarity over incident embeddings; until
the AI Assist pipeline lands we ship a deterministic heuristic
(:func:`app.incidents.rank_similar`) so the UI panel works end-to-end.
The route shape is identical so swapping the backend is one-file work
in Phase 5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
from ..incidents import compose_incidents, rank_similar
from ..store import CockpitStore

router = APIRouter(prefix="/api/incidents", tags=["similar"])


class SimilarIncidentsResponse(BaseModel):
    target_id: str
    items: list[dict[str, Any]]
    total: int
    method: str = Field(
        default="heuristic-v1",
        description=(
            "ID of the similarity backend ('heuristic-v1' in Phase 3, "
            "'chroma-cosine' in Phase 5)."
        ),
    )
    fetched_at: str


@router.get("/{incident_id}/similar", response_model=SimilarIncidentsResponse)
def similar_incidents(
    incident_id: str,
    *,
    limit: int = Query(default=10, ge=1, le=50),
    correlator: CorrelatorClient = Depends(get_correlator_client),
    opensearch: OpenSearchIncidentReader = Depends(get_opensearch_reader),
    settings: APISettings = Depends(get_settings_dep),
    store: CockpitStore = Depends(get_store_dep),
) -> SimilarIncidentsResponse:
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

    pool = compose_incidents(
        correlator_items=correlator_items,
        cached_items=store.list_recent_incidents(),
        opensearch_items=persisted_items,
        store=store,
    )
    target = next((i for i in pool if i.get("incident_id") == incident_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"incident {incident_id!r} not found",
        )
    items = rank_similar(target, pool, limit=limit)
    return SimilarIncidentsResponse(
        target_id=incident_id,
        items=items,
        total=len(items),
        fetched_at=datetime.now(UTC).isoformat(),
    )
