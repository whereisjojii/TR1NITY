"""WebSocket fan-out tests for /ws/incidents."""

from __future__ import annotations

import pytest
from app.realtime import ConnectionManager

from .fixtures.incidents import incident


def test_ws_incidents_emits_hello_and_snapshot(client_factory) -> None:
    items = [incident(incident_id="a"), incident(incident_id="b")]
    # Listing the queue first populates the recent buffer.
    client = client_factory(incidents=items)
    client.get("/api/incidents")

    with client.websocket_connect("/ws/incidents") as ws:
        hello = ws.receive_json()
        snapshot = ws.receive_json()

    assert hello["type"] == "hello"
    assert hello["channel"] == "incidents"
    assert snapshot["type"] == "snapshot"
    snapshot_ids = [i["incident_id"] for i in snapshot["incidents"]]
    assert set(snapshot_ids) == {"a", "b"}


def test_refresh_pushes_incident_new_event(client_factory) -> None:
    items = [incident(incident_id="boom")]
    client = client_factory(
        correlate_response={
            "incidents": items,
            "incident_count": 1,
            "sinks": [],
        }
    )
    with client.websocket_connect("/ws/incidents") as ws:
        ws.receive_json()  # hello
        ws.receive_json()  # snapshot

        client.post("/api/incidents/refresh")

        event = ws.receive_json()
        assert event["type"] == "incident.new"
        assert [i["incident_id"] for i in event["incidents"]] == ["boom"]


@pytest.mark.asyncio
async def test_connection_manager_drops_dead_clients() -> None:
    manager = ConnectionManager()

    class _DummyWS:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_text(self, text: str) -> None:
            self.sent.append(text)

    class _BadWS(_DummyWS):
        async def send_text(self, text: str) -> None:
            raise RuntimeError("disconnected")

    good = _DummyWS()
    bad = _BadWS()
    async with manager._lock:  # noqa: SLF001 — internal hook
        manager._connections.add(good)  # type: ignore[arg-type]
        manager._connections.add(bad)  # type: ignore[arg-type]

    delivered = await manager.broadcast_new([{"incident_id": "x"}])
    assert delivered == 1
    assert manager.connection_count == 1
