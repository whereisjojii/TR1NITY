"""Suppression-rule CRUD — Phase 4 Layer 3.

Analyst-authored "I know this isn't a real attack" rules. Stored in the
SQLite feedback DB and matched against every incident on every list
call. Each rule has an optional TTL so noisy short-term rules
auto-expire without an analyst having to remember to clean them up.

Endpoints:

* ``GET    /api/suppressions``              — list active rules
* ``POST   /api/suppressions``              — create a new rule
* ``GET    /api/suppressions/{id}``         — fetch a rule
* ``DELETE /api/suppressions/{id}``         — revoke a rule
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_feedback_db_dep
from ..fp.db import FeedbackDB

router = APIRouter(prefix="/api/suppressions", tags=["suppressions"])


class SuppressionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    match: dict[str, Any] = Field(..., description="Layer-1 style matcher")
    fp_score: float = Field(default=1.0, ge=0.0, le=1.0)
    ttl_days: int | None = Field(default=30, ge=1, le=365)
    author: str = Field(default="anonymous", max_length=200)
    reason: str | None = Field(default=None, max_length=2000)


class SuppressionResponse(BaseModel):
    suppression_id: str
    name: str
    match: dict[str, Any]
    fp_score: float
    ttl_days: int | None
    author: str
    reason: str | None
    created_at: str
    expires_at: str | None


class SuppressionListResponse(BaseModel):
    items: list[SuppressionResponse]
    total: int


@router.get("", response_model=SuppressionListResponse)
def list_suppressions(
    *,
    include_expired: bool = False,
    db: FeedbackDB = Depends(get_feedback_db_dep),
) -> SuppressionListResponse:
    if not include_expired:
        db.prune_expired()
    rows = db.list_suppressions(include_expired=include_expired)
    return SuppressionListResponse(items=rows, total=len(rows))


@router.post(
    "",
    response_model=SuppressionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_suppression(
    payload: SuppressionCreate,
    *,
    db: FeedbackDB = Depends(get_feedback_db_dep),
) -> SuppressionResponse:
    if not payload.match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="match block must contain at least one key",
        )
    row = db.insert_suppression(
        name=payload.name,
        match=payload.match,
        fp_score=payload.fp_score,
        ttl_days=payload.ttl_days,
        author=payload.author,
        reason=payload.reason,
    )
    return SuppressionResponse(**row)


@router.get("/{suppression_id}", response_model=SuppressionResponse)
def get_suppression(
    suppression_id: str,
    *,
    db: FeedbackDB = Depends(get_feedback_db_dep),
) -> SuppressionResponse:
    row = db.get_suppression(suppression_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"suppression {suppression_id!r} not found",
        )
    return SuppressionResponse(**row)


@router.delete("/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suppression(
    suppression_id: str,
    *,
    db: FeedbackDB = Depends(get_feedback_db_dep),
) -> None:
    if not db.delete_suppression(suppression_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"suppression {suppression_id!r} not found",
        )
