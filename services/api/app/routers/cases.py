"""Case-management routes — the Cockpit's lightweight case manager.

The roadmap names this an "alternative to TheHive". In Phase 3 we ship a
narrow CRUD over the in-process :class:`~app.store.CockpitStore` so the
React UI can:

* create a case from a triaged incident,
* list / filter cases,
* attach analyst notes,
* update status as the investigation progresses.

Phase 4 promotes storage to Postgres without breaking this surface.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import get_store_dep
from ..store import CaseStatus, CockpitStore

router = APIRouter(prefix="/api/cases", tags=["cases"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    severity: int = Field(default=0, ge=0, le=7)
    status: CaseStatus = "open"
    incident_ids: list[str] = Field(default_factory=list)
    assigned_to: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    severity: int | None = Field(default=None, ge=0, le=7)
    status: CaseStatus | None = None
    incident_ids: list[str] | None = None
    assigned_to: str | None = None
    tags: list[str] | None = None


class CaseNote(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    author: str = Field(default="anonymous", max_length=200)


class CaseResponse(BaseModel):
    case_id: str
    title: str
    severity: int
    status: CaseStatus
    summary: str | None = None
    incident_ids: list[str] = Field(default_factory=list)
    assigned_to: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    fetched_at: str


def _to_response(case_dict: dict[str, Any]) -> CaseResponse:
    return CaseResponse(**case_dict)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=CaseListResponse)
def list_cases(
    *,
    status: CaseStatus | None = Query(default=None),
    assigned_to: str | None = Query(default=None, max_length=200),
    store: CockpitStore = Depends(get_store_dep),
) -> CaseListResponse:
    cases = store.list_cases(status=status, assigned_to=assigned_to)
    items = [_to_response(c.to_dict()) for c in cases]
    return CaseListResponse(
        items=items,
        total=len(items),
        fetched_at=datetime.now(UTC).isoformat(),
    )


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    store: CockpitStore = Depends(get_store_dep),
) -> CaseResponse:
    try:
        case = store.create_case(
            title=payload.title,
            summary=payload.summary,
            severity=payload.severity,
            status=payload.status,
            incident_ids=payload.incident_ids,
            assigned_to=payload.assigned_to,
            tags=payload.tags,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _to_response(case.to_dict())


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: str,
    store: CockpitStore = Depends(get_store_dep),
) -> CaseResponse:
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case {case_id!r} not found",
        )
    return _to_response(case.to_dict())


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: str,
    payload: CaseUpdate,
    store: CockpitStore = Depends(get_store_dep),
) -> CaseResponse:
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no fields to update",
        )
    try:
        case = store.update_case(case_id, **changes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case {case_id!r} not found",
        )
    return _to_response(case.to_dict())


@router.post("/{case_id}/notes", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def add_note(
    case_id: str,
    payload: CaseNote,
    store: CockpitStore = Depends(get_store_dep),
) -> CaseResponse:
    case = store.add_case_note(case_id, author=payload.author or "anonymous", body=payload.body)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case {case_id!r} not found",
        )
    return _to_response(case.to_dict())


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: str,
    store: CockpitStore = Depends(get_store_dep),
) -> Response:
    if not store.delete_case(case_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case {case_id!r} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
