"""Endpoint tests for /api/incidents/{id}/similar."""

from __future__ import annotations

from .fixtures.incidents import incident


def test_similar_endpoint_returns_pool_minus_self(client_factory) -> None:
    items = [
        incident(
            incident_id="t",
            source_ip="203.0.113.10",
            technique_ids=["T1190"],
            sources=["waf"],
        ),
        incident(
            incident_id="match",
            source_ip="203.0.113.10",
            technique_ids=["T1190"],
            sources=["waf"],
        ),
        incident(
            incident_id="unrelated",
            source_ip="198.51.100.99",
            technique_ids=["T1486"],
            sources=["wazuh"],
        ),
    ]
    client = client_factory(incidents=items)
    resp = client.get("/api/incidents/t/similar")
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_id"] == "t"
    ids = [i["incident_id"] for i in body["items"]]
    assert "t" not in ids
    assert "match" in ids
    assert "unrelated" not in ids
    assert body["method"] == "heuristic-v1"


def test_similar_endpoint_returns_404_for_missing_target(client_factory) -> None:
    client = client_factory(incidents=[incident(incident_id="other")])
    resp = client.get("/api/incidents/missing/similar")
    assert resp.status_code == 404
