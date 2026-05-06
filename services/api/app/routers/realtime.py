"""Live-update WebSocket router.

The Cockpit subscribes to ``/ws/incidents`` to receive:

* a ``snapshot`` of the current queue on connect,
* ``incident.new`` events whenever ``POST /api/incidents/refresh`` runs
  or new incidents arrive in the api's recent buffer,
* periodic ``ping`` heartbeats so reverse proxies don't reap idle
  connections.

The Phase-0 ``/ws`` echo endpoint stays untouched in
``app/main.py`` for backwards compatibility — this router serves a new
URL under the ``incidents`` channel.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..config import APISettings
from ..dependencies import get_settings_dep, get_store_dep
from ..realtime import ConnectionManager, get_connection_manager
from ..store import CockpitStore

log = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/incidents")
async def incidents_ws(
    websocket: WebSocket,
    *,
    manager: ConnectionManager = Depends(get_connection_manager),
    store: CockpitStore = Depends(get_store_dep),
    settings: APISettings = Depends(get_settings_dep),
) -> None:
    await manager.connect(websocket)
    try:
        await manager.send_snapshot(websocket, store.list_recent_incidents())
        while True:
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.ws_heartbeat_seconds,
                )
            except TimeoutError:
                # Per-socket heartbeat keeps proxies happy while we wait
                # for fan-out from the broadcast manager.
                await websocket.send_json({"type": "ping"})
                continue
    except WebSocketDisconnect:
        return
    finally:
        await manager.disconnect(websocket)
