"""Endpoint tests for /api/cases."""

from __future__ import annotations


def test_create_then_get_case(client) -> None:
    create = client.post(
        "/api/cases",
        json={
            "title": "SQLi from 203.0.113.10",
            "summary": "WAF blocks + Wazuh login + firewall scan",
            "severity": 6,
            "incident_ids": ["inc-1", "inc-2"],
            "tags": ["web", "sqli"],
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    case_id = body["case_id"]
    assert body["severity"] == 6
    assert body["incident_ids"] == ["inc-1", "inc-2"]

    fetched = client.get(f"/api/cases/{case_id}")
    assert fetched.status_code == 200
    assert fetched.json()["case_id"] == case_id


def test_create_case_rejects_blank_title(client) -> None:
    resp = client.post("/api/cases", json={"title": "   "})
    assert resp.status_code == 422


def test_list_cases_filters_by_status_and_assignee(client) -> None:
    a = client.post(
        "/api/cases",
        json={"title": "A", "status": "open", "assigned_to": "alice"},
    ).json()
    b = client.post(
        "/api/cases",
        json={"title": "B", "status": "investigating", "assigned_to": "bob"},
    ).json()
    by_status = client.get("/api/cases", params={"status": "investigating"}).json()
    assert [c["case_id"] for c in by_status["items"]] == [b["case_id"]]
    by_assignee = client.get("/api/cases", params={"assigned_to": "alice"}).json()
    assert [c["case_id"] for c in by_assignee["items"]] == [a["case_id"]]


def test_update_case_changes_status_and_severity(client) -> None:
    case = client.post("/api/cases", json={"title": "T"}).json()
    resp = client.patch(
        f"/api/cases/{case['case_id']}",
        json={"status": "resolved", "severity": 4},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["severity"] == 4


def test_update_case_rejects_empty_payload(client) -> None:
    case = client.post("/api/cases", json={"title": "T"}).json()
    resp = client.patch(f"/api/cases/{case['case_id']}", json={})
    assert resp.status_code == 400


def test_update_case_unknown_id_returns_404(client) -> None:
    resp = client.patch(
        "/api/cases/does-not-exist",
        json={"status": "resolved"},
    )
    assert resp.status_code == 404


def test_add_note_to_case(client) -> None:
    case = client.post("/api/cases", json={"title": "T"}).json()
    resp = client.post(
        f"/api/cases/{case['case_id']}/notes",
        json={"author": "alice", "body": "Disabled the rule"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["notes"][-1]["body"] == "Disabled the rule"
    assert body["notes"][-1]["author"] == "alice"


def test_delete_case(client) -> None:
    case = client.post("/api/cases", json={"title": "to delete"}).json()
    resp = client.delete(f"/api/cases/{case['case_id']}")
    assert resp.status_code == 204
    follow = client.get(f"/api/cases/{case['case_id']}")
    assert follow.status_code == 404
