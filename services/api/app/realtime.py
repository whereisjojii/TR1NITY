"""WebSocket fan-out for live incident updates.

Phase-3 strategy:
- The api owns one ``ConnectionManager`` per process.
- Each ``/ws/incidents`` client subscribes; the server pushes a
  ``snapshot`` on connect followed by ``incident.new`` / ``incident.updated``
  events whenever the api's recent buffer grows.
- A heartbeat keeps idle proxies happy.

Phase 4 swaps this to a Postgres ``LISTEN`` / NATS-style fan-out, but
the JSON message contract stays stable so the React client doesn't have
to change.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ConnectionManager:
    """Track connected ``/ws/incidents`` clients and broadcast events."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        await websocket.send_json(
            {
                "type": "hello",
                "service": "api",
                "channel": "incidents",
                "ts": _now_iso(),
            }
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def send_snapshot(
        self,
        websocket: WebSocket,
        incidents: Iterable[dict[str, Any]],
    ) -> None:
        await websocket.send_json(
            {
                "type": "snapshot",
                "ts": _now_iso(),
                "incidents": list(incidents),
            }
        )

    async def broadcast_new(self, incidents: list[dict[str, Any]]) -> int:
        """Push an ``incident.new`` event to every connected client.

        Returns the number of clients the event was successfully sent to.
        Failed sockets are pruned silently — the client will reconnect.
        """
        if not incidents:
            return 0
        payload = {
            "type": "incident.new",
            "ts": _now_iso(),
            "incidents": incidents,
        }
        encoded = json.dumps(payload, default=str)
        return await self._broadcast_raw(encoded)

    async def heartbeat(self) -> int:
        """Send a heartbeat — used by the keepalive loop."""
        encoded = json.dumps({"type": "ping", "ts": _now_iso()})
        return await self._broadcast_raw(encoded)

    async def _broadcast_raw(self, encoded: str) -> int:
        delivered = 0
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(encoded)
                delivered += 1
            except Exception as exc:  # pragma: no cover - defensive
                log.debug("ws send failed; dropping client: %s", exc)
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)
        return delivered


_default_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = ConnectionManager()
    return _default_manager


def replace_connection_manager(manager: ConnectionManager) -> ConnectionManager:
    global _default_manager
    _default_manager = manager
    return manager


__all__ = [
    "ConnectionManager",
    "get_connection_manager",
    "replace_connection_manager",
]
