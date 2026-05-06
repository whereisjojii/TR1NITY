"""Endpoint tests for /api/incidents."""

from __future__ import annotations

import httpx
from app.clients.correlator import CorrelatorClient
from app.dependencies import get_correlator_client
from app.main import app as fastapi_app

from .fixtures.incidents import incident


def test_list_incidents_returns_correlator_view(client_factory) -> None:
    items = [
        incident(incident_id="a", severity=5),
        incident(incident_id="b", severity=2),
    ]
    client = client_factory(incidents=items)
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = [i["incident_id"] for i in body["items"]]
    assert set(ids) == {"a", "b"}
    for inc in body["items"]:
        assert inc["fp_score"] == 0.5  # neutral until analyst marks


def test_list_incidents_sorted_by_fp_after_marks(client_factory) -> None:
    items = [
        incident(incident_id="not-fp"),
        incident(incident_id="is-fp"),
    ]
    client = client_factory(incidents=items)
    client.post("/api/incidents/not-fp/mark-fp", json={"is_fp": False})
    client.post("/api/incidents/is-fp/mark-fp", json={"is_fp": True})
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    ids = [i["incident_id"] for i in resp.json()["items"]]
    assert ids == ["not-fp", "is-fp"]


def test_list_incidents_sort_by_severity_descending(client_factory) -> None:
    items = [
        incident(incident_id="low", severity=1),
        incident(incident_id="high", severity=7),
        incident(incident_id="mid", severity=4),
    ]
    client = client_factory(incidents=items)
    resp = client.get(
        "/api/incidents",
        params={"sort_by": "severity", "descending": "true"},
    )
    ids = [i["incident_id"] for i in resp.json()["items"]]
    assert ids == ["high", "mid", "low"]


def test_list_incidents_severity_filter(client_factory) -> None:
    items = [
        incident(incident_id="low", severity=1),
        incident(incident_id="hot", severity=7),
    ]
    client = client_factory(incidents=items)
    resp = client.get("/api/incidents", params={"severity_min": 5})
    ids = [i["incident_id"] for i in resp.json()["items"]]
    assert ids == ["hot"]


def test_list_incidents_source_filter(client_factory) -> None:
    items = [
        incident(incident_id="wazuh-only", sources=["wazuh"]),
        incident(incident_id="waf-only", sources=["waf"]),
    ]
    client = client_factory(incidents=items)
    resp = client.get("/api/incidents", params=[("sources", "waf")])
    ids = [i["incident_id"] for i in resp.json()["items"]]
    assert ids == ["waf-only"]


def test_list_incidents_falls_back_to_opensearch(client_factory) -> None:
    items = [incident(incident_id="from-os")]
    client = client_factory(incidents=None, os_hits=items)
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    ids = [i["incident_id"] for i in resp.json()["items"]]
    assert ids == ["from-os"]


def test_list_incidents_handles_correlator_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/incidents":
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    correlator = CorrelatorClient(base_url="http://correlator", transport=transport)
    fastapi_app.dependency_overrides[get_correlator_client] = lambda: correlator
    try:
        from fastapi.testclient import TestClient

        client = TestClient(fastapi_app)
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_get_single_incident(client_factory) -> None:
    items = [
        incident(incident_id="alpha"),
        incident(incident_id="bravo"),
    ]
    client = client_factory(incidents=items)
    resp = client.get("/api/incidents/bravo")
    assert resp.status_code == 200
    assert resp.json()["incident_id"] == "bravo"


def test_get_missing_incident_returns_404(client_factory) -> None:
    client = client_factory(incidents=[incident(incident_id="alpha")])
    resp = client.get("/api/incidents/zzz")
    assert resp.status_code == 404


def test_mark_fp_persists_score(client_factory) -> None:
    client = client_factory(incidents=[incident(incident_id="alpha")])
    resp = client.post(
        "/api/incidents/alpha/mark-fp",
        json={"is_fp": True, "reason": "scanner", "submitted_by": "alice"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fp_score"] == 1.0
    assert body["feedback"]["submitted_by"] == "alice"
    follow = client.get("/api/incidents/alpha")
    assert follow.json()["fp_score"] == 1.0


def test_refresh_incidents_calls_correlator_and_broadcasts(client_factory) -> None:
    items = [incident(incident_id="refresh-me")]
    client = client_factory(
        correlate_response={
            "incidents": [i for i in items],
            "incident_count": 1,
            "sinks": [{"sink": "stdout", "accepted": 1, "rejected": 0, "errors": []}],
        }
    )
    resp = client.post("/api/incidents/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["triggered"] is True
    assert body["incident_count"] == 1
    assert body["sinks"][0]["sink"] == "stdout"
    listing = client.get("/api/incidents").json()
    assert "refresh-me" in [i["incident_id"] for i in listing["items"]]


def test_refresh_incidents_returns_503_when_correlator_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    correlator = CorrelatorClient(base_url="http://correlator", transport=transport)
    fastapi_app.dependency_overrides[get_correlator_client] = lambda: correlator
    try:
        from fastapi.testclient import TestClient

        client = TestClient(fastapi_app)
        resp = client.post("/api/incidents/refresh")
        assert resp.status_code == 503
    finally:
        fastapi_app.dependency_overrides.clear()
