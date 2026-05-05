"""Smoke tests for the ingestor."""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root_returns_service_banner() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ingestor"
    assert body["phase"].startswith("1")


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "ingestor"
    assert "version" in body
    assert isinstance(body["uptime_seconds"], int | float)


def test_readyz_includes_sink_status() -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ingestor"
    assert body["status"] in {"ready", "degraded"}
    assert body["sink"] in {"stdout", "opensearch"}
    assert isinstance(body["sink_healthy"], bool)
