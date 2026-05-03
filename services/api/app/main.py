"""TR1NITY api service — Phase 0 hello-world.

Public-facing REST + WebSocket gateway. In production it also serves the
static React build (the Cockpit, Module 5). Phase-3 deliverables (UI
shell, alert queue endpoints, WebSocket live updates) land in a later
session under tag ``v0.4.0-cockpit``.
"""

from __future__ import annotations

import asyncio
import os
import platform
import socket
import time
from datetime import UTC, datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import __version__

SERVICE_NAME = "api"
START_TIME = time.monotonic()

app = FastAPI(
    title="TR1NITY · API",
    version=__version__,
    description=(
        "Public REST and WebSocket gateway. Serves the static React "
        "Cockpit build in production. Phase 0 hello-world only."
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
        "ws": "/ws",
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
    """Phase-0 echo WebSocket. Replaced by live-incident push in Phase 3."""
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
