"""HTTP API smoke tests for the correlator service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.main import app
from fastapi.testclient import TestClient

from tests.conftest import make_event

client = TestClient(app)


def test_correlate_endpoint_drives_pipeline() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    payload = [
        make_event(source="firewall", timestamp=base, event_action="block"),
        make_event(
            source="wazuh",
            timestamp=base + timedelta(seconds=30),
            rule_id="5503",
            rule_category="authentication_failures",
        ),
    ]
    enqueue = client.post("/ingest-test", json=payload)
    assert enqueue.status_code == 200, enqueue.text
    assert enqueue.json() == {"queued": 2}

    correlate = client.post("/correlate")
    assert correlate.status_code == 200
    body = correlate.json()
    assert body["incident_count"] == 1
    incident = body["incidents"][0]
    assert incident["member_count"] == 2
    assert incident["grouping_key"].startswith("src_ip:")

    # Listing should now reflect the latest tick.
    listing = client.get("/incidents")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_correlate_with_empty_queue_returns_zero() -> None:
    # Drain the consumer first.
    client.post("/correlate")
    body = client.post("/correlate").json()
    assert body["incident_count"] == 0
    assert body["incidents"] == []
