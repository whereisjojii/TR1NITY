"""Liveness, readiness, and service-banner endpoints.

Carry-over from Phase 0; readiness now actually probes the configured sink.
"""

from __future__ import annotations

import os
import platform
import socket
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from .. import __version__
from ..dependencies import get_sink
from ..sinks import EventSink

router = APIRouter()
START_TIME = time.monotonic()
SERVICE_NAME = "ingestor"


@router.get("/", summary="Service banner", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "phase": "1 — Multi-source Ingestion",
        "docs": "/docs",
        "healthz": "/healthz",
        "readyz": "/readyz",
    }


@router.get("/healthz", summary="Liveness probe", tags=["health"])
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": __version__,
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "uptime_seconds": round(time.monotonic() - START_TIME, 3),
        "now": datetime.now(UTC).isoformat(),
        "env": os.environ.get("TR1NITY_ENV", "dev"),
    }


@router.get("/readyz", summary="Readiness probe", tags=["health"])
async def readyz(sink: EventSink = Depends(get_sink)) -> dict[str, object]:
    sink_ok = await sink.healthy()
    return {
        "status": "ready" if sink_ok else "degraded",
        "service": SERVICE_NAME,
        "sink": sink.name,
        "sink_healthy": sink_ok,
    }
