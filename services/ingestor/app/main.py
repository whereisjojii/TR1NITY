"""TR1NITY ingestor service — Phase 0 hello-world.

Module 1 (Ingestion & Normalization). Phase-1 deliverables (Wazuh webhook,
firewall syslog, ModSecurity tail, ECS schema, OpenSearch writer) land in the
next session under tag ``v0.2.0-ingest``.

This Phase-0 entrypoint exists so that:

* ``docker compose up`` boots a runnable service tree on day one,
* CI exercises a real FastAPI app (not a placeholder),
* downstream services can already point at ``http://ingestor:8001`` for
  end-to-end smoke tests.
"""

from __future__ import annotations

import os
import platform
import socket
import time
from datetime import UTC, datetime

from fastapi import FastAPI

from . import __version__

SERVICE_NAME = "ingestor"
START_TIME = time.monotonic()

app = FastAPI(
    title="TR1NITY · Ingestor",
    version=__version__,
    description=(
        "Receives Wazuh webhooks, firewall syslog, and ModSecurity audit "
        "logs; normalizes everything to ECS; writes to OpenSearch index "
        "tr1nity-events-*. Phase 0 hello-world only — full implementation "
        "in Phase 1."
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
