"""TR1NITY correlator service — Phase 0 hello-world.

"The Brain" (Module 2). Phase-2 deliverables (temporal grouping, entity
resolution, MITRE ATT&CK tagging, threat-intel enrichment, SIGMA rule
import via pySigma, runbook auto-attachment) land in a later session
under tag ``v0.3.0-brain``.
"""

from __future__ import annotations

import os
import platform
import socket
import time
from datetime import UTC, datetime

from fastapi import FastAPI

from . import __version__

SERVICE_NAME = "correlator"
START_TIME = time.monotonic()

app = FastAPI(
    title="TR1NITY · Correlator",
    version=__version__,
    description=(
        "Periodic correlation engine. Reads tr1nity-events-*, performs "
        "temporal grouping, entity resolution, MITRE ATT&CK tagging, and "
        "threat-intel enrichment, writes incidents to "
        "tr1nity-incidents-*. Phase 0 hello-world only."
    ),
)


@app.get("/", summary="Service banner", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "phase": "0 — Foundation",
        "docs": "/docs",
        "healthz": "/healthz",
    }


@app.get("/healthz", summary="Liveness probe", tags=["health"])
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


@app.get("/readyz", summary="Readiness probe", tags=["health"])
def readyz() -> dict[str, str]:
    return {"status": "ready", "service": SERVICE_NAME}


@app.get("/incidents", summary="List incidents", tags=["incidents"])
def list_incidents() -> dict[str, object]:
    """Phase-0 stub. Real implementation in Phase 2."""
    return {
        "items": [],
        "total": 0,
        "phase": "0",
        "note": (
            "Correlation pipeline not built yet. Returns empty list until "
            "Phase 2 (v0.3.0-brain)."
        ),
    }
