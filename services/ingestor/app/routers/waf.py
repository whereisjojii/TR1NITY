"""POST /ingest/waf — receives ModSecurity / WAF audit JSON."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ..config import get_settings
from ..dependencies import get_sink, require_auth
from ..sinks import EventSink
from ..sources import modsec as modsec_parser

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/waf",
    status_code=status.HTTP_202_ACCEPTED,
    summary="ModSecurity / WAF audit",
    description=(
        "Accepts one ModSecurity v3 JSON audit document or a list of them. "
        "Each is normalized to ECS and forwarded to the configured sink."
    ),
    dependencies=[Depends(require_auth)],
)
async def ingest_waf(
    body: dict | list[dict] = Body(...),  # noqa: B008
    sink: EventSink = Depends(get_sink),  # noqa: B008
) -> dict[str, object]:
    settings = get_settings()
    payloads: list[dict] = body if isinstance(body, list) else [body]
    if len(payloads) > settings.max_events_per_request:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"too many events: {len(payloads)} > {settings.max_events_per_request}",
        )

    parsed = []
    parse_errors: list[dict[str, object]] = []
    for i, p in enumerate(payloads):
        try:
            parsed.append(modsec_parser.parse(p))
        except (ValueError, TypeError) as e:
            parse_errors.append({"index": i, "error": str(e)})

    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"received": len(payloads), "parse_errors": parse_errors},
        )

    sink_result = await sink.write(parsed)
    return {
        "received": len(payloads),
        "parsed": len(parsed),
        "accepted": sink_result.accepted,
        "rejected": sink_result.rejected,
        "parse_errors": parse_errors,
        "sink_errors": sink_result.errors,
    }
