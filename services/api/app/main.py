"""TR1NITY api service — Phase 3 (Cockpit gateway).

Public-facing REST + WebSocket gateway. The api service is the analyst-
facing surface in front of the correlator and (Phase 5) the ai-assist
service. In production it also serves the static React Cockpit build.

Phase 3 deliverables (this version, ``0.4.0``):

* Phase-0 surface kept intact: ``GET /``, ``GET /healthz``,
  ``GET /readyz``, ``WS /ws`` (echo).
* Cockpit API surface added under ``/api/*``:

  * ``GET  /api/incidents``                 — queue, FP-score sorted.
  * ``GET  /api/incidents/{id}``            — single incident detail.
  * ``POST /api/incidents/{id}/mark-fp``    — analyst FP feedback.
  * ``POST /api/incidents/refresh``         — force a correlator tick.
  * ``GET  /api/incidents/{id}/similar``    — similar past incidents.
  * ``GET  /api/cases``  (+ POST/PATCH/DELETE) — lightweight case manager.
  * ``GET  /api/attack/heatmap``            — ATT&CK heatmap payload.

* Live updates: ``WS /ws/incidents`` (snapshot on connect + pushes).
* Static Cockpit mount when ``COCKPIT_STATIC_DIR`` is set.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import socket
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import get_settings
from .routers import attack, cases, incidents, realtime, runbooks, similar, suppressions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

SERVICE_NAME = "api"
START_TIME = time.monotonic()

app = FastAPI(
    title="TR1NITY · API",
    version=__version__,
    description=(
        "Phase 3 — Cockpit gateway. Public REST + WebSocket surface "
        "fronting the correlator's incident store; serves the static "
        "React Cockpit build in production."
    ),
)


# ---------------------------------------------------------------------------
# CORS — only enabled when a dev origin is set (e.g. ``pnpm dev`` on :5173).
# ---------------------------------------------------------------------------

_settings = get_settings()
if _settings.cockpit_dev_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_settings.cockpit_dev_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ---------------------------------------------------------------------------
# Phase-0 surface — kept intact for backwards compatibility.
# ---------------------------------------------------------------------------


@app.get("/", summary="Service banner", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "phase": "3 — Cockpit gateway",
        "docs": "/docs",
        "healthz": "/healthz",
        "ws": "/ws",
        "ws_incidents": "/ws/incidents",
        "cockpit": "/cockpit/",
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Phase-0 echo WebSocket — kept for backwards-compat smoke tests.

    The Cockpit's live-incident channel lives at ``/ws/incidents``.
    """
    await websocket.accept()
    try:
        await websocket.send_json({"type": "hello", "service": SERVICE_NAME})
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except TimeoutError:
                await websocket.send_json({"type": "ping", "ts": datetime.now(UTC).isoformat()})
                continue
            await websocket.send_json({"type": "echo", "received": msg})
    except WebSocketDisconnect:
        return


# ---------------------------------------------------------------------------
# Phase-3 routers
# ---------------------------------------------------------------------------


app.include_router(incidents.router)
app.include_router(similar.router)
app.include_router(cases.router)
app.include_router(attack.router)
app.include_router(realtime.router)
app.include_router(runbooks.router)
app.include_router(suppressions.router)


# ---------------------------------------------------------------------------
# Static Cockpit mount.
# ---------------------------------------------------------------------------


def _mount_static_cockpit(static_dir: str) -> None:
    """Mount the built React app at ``/cockpit/`` if the directory exists."""
    if not static_dir:
        return
    path = Path(static_dir)
    if not path.is_dir():
        log.info("COCKPIT_STATIC_DIR=%s does not exist; skipping static mount.", static_dir)
        return
    app.mount(
        "/cockpit",
        StaticFiles(directory=str(path), html=True),
        name="cockpit",
    )
    log.info("Mounted Cockpit static build at /cockpit/ from %s", static_dir)

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{rest:path}", include_in_schema=False)
    async def _cockpit_alias(rest: str = "") -> RedirectResponse:
        # Convenience alias for older docs that referenced /app.
        target = "/cockpit/" + rest if rest else "/cockpit/"
        return RedirectResponse(url=target, status_code=307)


_mount_static_cockpit(_settings.cockpit_static_dir)
