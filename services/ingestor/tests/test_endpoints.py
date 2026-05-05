"""End-to-end tests for the ingest endpoints."""

from __future__ import annotations

import os

import pytest
from app.config import reset_settings_cache
from app.dependencies import reset_sink_cache
from app.main import app
from fastapi.testclient import TestClient

from .conftest import load_json, load_text


@pytest.fixture(autouse=True)
def _reset_caches():
    reset_settings_cache()
    reset_sink_cache()
    yield
    reset_settings_cache()
    reset_sink_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_post_wazuh_accepts_single_alert(client: TestClient) -> None:
    payload = load_json("wazuh_brute_force.json")
    r = client.post("/ingest/wazuh", json=payload)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["received"] == 1
    assert body["accepted"] == 1
    assert body["rejected"] == 0


def test_post_wazuh_accepts_batch(client: TestClient) -> None:
    payloads = [load_json("wazuh_brute_force.json"), load_json("wazuh_malware.json")]
    r = client.post("/ingest/wazuh", json=payloads)
    assert r.status_code == 202
    body = r.json()
    assert body["received"] == 2
    assert body["accepted"] == 2


def test_post_wazuh_rejects_payload_with_no_rule(client: TestClient) -> None:
    r = client.post("/ingest/wazuh", json={"timestamp": "2024-01-15T14:32:01Z"})
    assert r.status_code == 422


def test_post_syslog_parses_iptables_and_pfsense(client: TestClient) -> None:
    lines = [load_text("iptables_drop.txt"), load_text("pfsense_block.txt")]
    r = client.post("/ingest/syslog", json={"lines": lines, "host": "fw-01"})
    assert r.status_code == 202
    body = r.json()
    assert body["received"] == 2
    assert body["accepted"] == 2


def test_post_syslog_partial_failure_still_returns_202(client: TestClient) -> None:
    lines = [load_text("iptables_drop.txt"), "garbage line"]
    r = client.post("/ingest/syslog", json={"lines": lines})
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 1
    assert len(body["parse_errors"]) == 1


def test_post_syslog_full_failure_returns_422(client: TestClient) -> None:
    r = client.post("/ingest/syslog", json={"lines": ["nope", "still nope"]})
    assert r.status_code == 422


def test_post_waf_normalizes_modsec_audit(client: TestClient) -> None:
    payload = load_json("modsec_sqli.json")
    r = client.post("/ingest/waf", json=payload)
    assert r.status_code == 202


def test_auth_enforced_when_enabled(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("ENABLE_AUTH", "true")
    monkeypatch.setenv("INGESTOR_AUTH_TOKEN", "s3cret")
    reset_settings_cache()
    reset_sink_cache()

    payload = load_json("wazuh_brute_force.json")
    # No auth header -> 401
    r = client.post("/ingest/wazuh", json=payload)
    assert r.status_code == 401

    # Wrong token -> 401
    r = client.post("/ingest/wazuh", json=payload, headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    # Correct token -> 202
    r = client.post("/ingest/wazuh", json=payload, headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 202

    # Cleanup happens via _reset_caches fixture
    monkeypatch.delenv("ENABLE_AUTH", raising=False)
    monkeypatch.delenv("INGESTOR_AUTH_TOKEN", raising=False)
    # Avoid the env leaking — explicitly reset here.
    os.environ.pop("ENABLE_AUTH", None)
    os.environ.pop("INGESTOR_AUTH_TOKEN", None)
    reset_settings_cache()
