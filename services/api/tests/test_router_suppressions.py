"""Tests for the Phase-4 suppression-rule CRUD router."""

from __future__ import annotations


def test_create_then_list_suppression(client) -> None:
    create = client.post(
        "/api/suppressions",
        json={
            "name": "scanner",
            "match": {"sources": ["firewall"]},
            "fp_score": 0.95,
            "ttl_days": 7,
            "author": "alice",
            "reason": "approved scanner",
        },
    )
    assert create.status_code == 201
    body = create.json()
    sid = body["suppression_id"]
    assert body["expires_at"] is not None

    listing = client.get("/api/suppressions")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert any(item["suppression_id"] == sid for item in items)


def test_create_rejects_empty_match(client) -> None:
    response = client.post(
        "/api/suppressions",
        json={
            "name": "no-match",
            "match": {},
            "fp_score": 0.5,
        },
    )
    assert response.status_code == 400


def test_get_suppression_round_trip(client) -> None:
    response = client.post(
        "/api/suppressions",
        json={
            "name": "x",
            "match": {"sources": ["wazuh"]},
            "fp_score": 0.5,
            "ttl_days": 30,
        },
    )
    sid = response.json()["suppression_id"]
    detail = client.get(f"/api/suppressions/{sid}")
    assert detail.status_code == 200
    assert detail.json()["suppression_id"] == sid


def test_delete_suppression(client) -> None:
    response = client.post(
        "/api/suppressions",
        json={
            "name": "x",
            "match": {"sources": ["wazuh"]},
            "fp_score": 0.5,
            "ttl_days": 30,
        },
    )
    sid = response.json()["suppression_id"]
    deleted = client.delete(f"/api/suppressions/{sid}")
    assert deleted.status_code == 204
    detail = client.get(f"/api/suppressions/{sid}")
    assert detail.status_code == 404


def test_delete_unknown_suppression_returns_404(client) -> None:
    deleted = client.delete("/api/suppressions/does-not-exist")
    assert deleted.status_code == 404
