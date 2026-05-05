"""POST /ingest/syslog — receives raw firewall syslog lines."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..dependencies import get_sink, require_auth
from ..sinks import EventSink
from ..sources import firewall as fw_parser

router = APIRouter(prefix="/ingest", tags=["ingest"])


class SyslogBatch(BaseModel):
    lines: list[str] = Field(..., min_length=1)
    host: str | None = None


@router.post(
    "/syslog",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Firewall syslog batch",
    description=(
        "Accepts a JSON object with ``lines`` (list of raw syslog lines from "
        "iptables, pfSense, or OPNsense) and an optional ``host`` field. "
        "Each line is auto-detected and normalized to ECS."
    ),
    dependencies=[Depends(require_auth)],
)
async def ingest_syslog(
    body: SyslogBatch,
    sink: EventSink = Depends(get_sink),  # noqa: B008
) -> dict[str, Any]:
    settings = get_settings()
    if len(body.lines) > settings.max_lines_per_request:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"too many lines: {len(body.lines)} > {settings.max_lines_per_request}",
        )

    parsed, parse_errors = fw_parser.parse_lines(body.lines, host_name=body.host)

    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"received": len(body.lines), "parse_errors": parse_errors[:25]},
        )

    sink_result = await sink.write(parsed)
    return {
        "received": len(body.lines),
        "parsed": len(parsed),
        "accepted": sink_result.accepted,
        "rejected": sink_result.rejected,
        "parse_errors": parse_errors[:25],  # don't echo huge error lists
        "sink_errors": sink_result.errors,
    }
