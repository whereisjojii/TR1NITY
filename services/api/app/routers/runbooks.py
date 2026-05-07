"""Runbook routes — Phase 4.

Endpoints:

* ``GET /api/runbooks``                     — index by technique id
* ``GET /api/runbooks/{technique_id}``      — single runbook (markdown body included)

The Cockpit's incident-detail page calls the second endpoint when the
analyst opens the "Runbook" tab; the queue page reads the index to
badge incidents whose primary technique has a runbook attached.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_runbook_library_dep
from ..runbooks import RunbookLibrary

router = APIRouter(prefix="/api/runbooks", tags=["runbooks"])


@router.get("")
def list_runbooks(
    *,
    library: RunbookLibrary = Depends(get_runbook_library_dep),
) -> dict[str, Any]:
    summaries = library.list_summaries()
    return {"items": summaries, "total": len(summaries)}


@router.get("/{technique_id}")
def get_runbook(
    technique_id: str,
    *,
    library: RunbookLibrary = Depends(get_runbook_library_dep),
) -> dict[str, Any]:
    runbook = library.get(technique_id)
    if runbook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"runbook for {technique_id!r} not found",
        )
    return runbook.to_dict()
