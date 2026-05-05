"""TR1NITY correlator service — Phase 2.

"The Brain" (Module 2). Responsible for taking the unified ECS event
stream emitted by the ingestor and turning it into a much smaller,
analyst-friendly stream of ``Incident`` documents.

This file is the FastAPI entrypoint only — every interesting piece of
logic lives in a focused submodule (``grouping``, ``attack``, ``sigma``,
``intel``, ``pipeline``).
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from . import __version__
from .config import get_settings
from .consumer import InMemoryEventConsumer
from .incident import Incident
from .intel import FileProvider
from .pipeline import CorrelatorPipeline
from .sigma import SigmaEngine, load_rules_from_dir
from .sinks import StdoutIncidentSink

log = logging.getLogger(__name__)

SERVICE_NAME = "correlator"
START_TIME = time.monotonic()


def _default_pipeline() -> CorrelatorPipeline:
    """Build the default DRY_RUN pipeline used at boot.

    The bundled SIGMA rule pack ships under ``app/sigma/rules`` and the
    starter IOC list under ``app/intel/data/ioc.json``. Operators can
    override either path via env vars without touching code.
    """
    settings = get_settings()

    rules_dir = Path(__file__).parent / "sigma" / "rules"
    sigma_engine: SigmaEngine | None = None
    if settings.sigma_enabled:
        rules = load_rules_from_dir(rules_dir)
        sigma_engine = SigmaEngine(rules=rules)

    intel_providers = []
    if settings.intel_enabled:
        ioc_path = Path(__file__).parent / "intel" / "data" / "ioc.json"
        intel_providers.append(FileProvider.from_file(ioc_path))

    return CorrelatorPipeline.assemble(
        consumer=InMemoryEventConsumer(),
        sinks=[StdoutIncidentSink()],
        sigma_engine=sigma_engine,
        intel_providers=intel_providers,
        intel_ttl_seconds=settings.intel_cache_ttl_seconds,
        window_seconds=settings.incident_window_seconds,
        max_events_per_incident=settings.incident_max_events,
    )


app = FastAPI(
    title="TR1NITY · Correlator",
    version=__version__,
    description=(
        "Phase 2 — The Brain. Reads tr1nity-events-*, performs sliding-window "
        "grouping by source IP, runs SIGMA-style rules, promotes the MITRE "
        "ATT&CK chain, enriches with threat-intel, and writes incidents to "
        "tr1nity-incidents-*."
    ),
)

# We intentionally hang the pipeline off the FastAPI app instance so
# tests can swap it out without monkeypatching module globals.
app.state.pipeline = _default_pipeline()


@app.get("/", summary="Service banner", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "phase": "2 — Correlation (The Brain)",
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


@app.get("/incidents", summary="List most recently produced incidents", tags=["incidents"])
def list_incidents() -> dict[str, object]:
    """Return the incidents from the most recent pipeline tick.

    In Phase 2 the correlator runs on demand (via ``/correlate``) or via
    a deployment-managed scheduler. Persistent listing across restarts
    lands in Phase 3 alongside the Cockpit's incident store.
    """
    pipeline: CorrelatorPipeline = app.state.pipeline
    items = [inc.to_index_doc() for inc in pipeline.last_incidents]
    return {"items": items, "total": len(items)}


@app.post("/correlate", summary="Trigger one correlation tick", tags=["incidents"])
def trigger_correlation() -> dict[str, object]:
    """Pull whatever the consumer currently has, correlate, and write to all sinks.

    Phase-2 deployments invoke this from a cron / scheduler. Phase 4
    will replace it with an event-driven reactor inside the pipeline.
    """
    pipeline: CorrelatorPipeline = app.state.pipeline
    results = pipeline.tick()
    return {
        "incidents": [inc.to_index_doc() for inc in pipeline.last_incidents],
        "incident_count": len(pipeline.last_incidents),
        "sinks": [
            {
                "sink": r.sink,
                "accepted": r.accepted,
                "rejected": r.rejected,
                "errors": r.errors,
            }
            for r in results
        ],
    }


@app.post(
    "/ingest-test",
    summary="Test helper: push events into the in-memory consumer",
    tags=["incidents"],
)
def ingest_test(events: list[dict]) -> dict[str, object]:
    """Push a list of ECS event dicts into the in-memory consumer.

    Helpful for ``make demo`` and integration tests where we want to drive
    correlation without standing up OpenSearch. In production this
    endpoint is a no-op when the configured consumer is not the in-memory
    one (returns ``409 Conflict``).
    """
    pipeline: CorrelatorPipeline = app.state.pipeline
    consumer = pipeline.consumer
    if not isinstance(consumer, InMemoryEventConsumer):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ingest-test only works against the in-memory consumer",
        )
    consumer.push(events)
    return {"queued": len(events)}


# ---------------------------------------------------------------------------
# Convenience: lazy access for tests
# ---------------------------------------------------------------------------


def get_pipeline() -> CorrelatorPipeline:
    """Return the FastAPI-bound pipeline (handy for unit tests)."""
    return app.state.pipeline


def replace_pipeline(pipeline: CorrelatorPipeline) -> None:
    """Swap in a custom pipeline for testing."""
    app.state.pipeline = pipeline


__all__ = [
    "Incident",
    "app",
    "get_pipeline",
    "replace_pipeline",
]
