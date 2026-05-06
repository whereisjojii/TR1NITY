"""Endpoint tests for /api/attack/heatmap."""

from __future__ import annotations

from .fixtures.incidents import incident


def test_heatmap_aggregates(client_factory) -> None:
    items = [
        incident(
            incident_id="a",
            technique_ids=["T1190", "T1110"],
            tactic_ids=["TA0001", "TA0006"],
        ),
        incident(
            incident_id="b",
            technique_ids=["T1190"],
            tactic_ids=["TA0001"],
        ),
        incident(
            incident_id="c",
            technique_ids=[],
            tactic_ids=[],
        ),
    ]
    client = client_factory(incidents=items)
    resp = client.get("/api/attack/heatmap")
    assert resp.status_code == 200
    body = resp.json()
    counts = {t["id"]: t["count"] for t in body["techniques"]}
    assert counts == {"T1190": 2, "T1110": 1}
    tactic_counts = {t["id"]: t["count"] for t in body["tactics"]}
    assert tactic_counts == {"TA0001": 2, "TA0006": 1}
    assert body["total_incidents"] == 3
    assert body["covered_incidents"] == 2


def test_heatmap_severity_filter(client_factory) -> None:
    items = [
        incident(incident_id="low", severity=1, technique_ids=["T1190"]),
        incident(incident_id="hot", severity=7, technique_ids=["T1110"]),
    ]
    client = client_factory(incidents=items)
    resp = client.get("/api/attack/heatmap", params={"severity_min": 5})
    counts = {t["id"]: t["count"] for t in resp.json()["techniques"]}
    assert counts == {"T1110": 1}
