"""Tests for the Phase-4 runbook router."""

from __future__ import annotations


def test_list_runbooks_returns_bundled_library(client) -> None:
    response = client.get("/api/runbooks")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 15
    technique_ids = {item["technique_id"] for item in data["items"]}
    # Spot-check the must-have techniques the ROADMAP names.
    assert {"T1110.001", "T1190", "T1078"}.issubset(technique_ids)


def test_get_runbook_returns_markdown_body(client) -> None:
    response = client.get("/api/runbooks/T1110.001")
    assert response.status_code == 200
    data = response.json()
    assert data["technique_id"] == "T1110.001"
    assert data["severity"] == "high"
    assert "Password guessing" in data["title"]
    assert data["body"].startswith("#")


def test_get_runbook_falls_back_to_parent_technique(client) -> None:
    # We don't ship a T1110.999 runbook, but we ship T1110.
    response = client.get("/api/runbooks/T1110.999")
    assert response.status_code == 200
    assert response.json()["technique_id"] == "T1110"


def test_get_runbook_404_for_unknown_technique(client) -> None:
    response = client.get("/api/runbooks/T9999")
    assert response.status_code == 404
