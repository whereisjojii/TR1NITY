"""Smoke tests for the correlator Phase-0 hello-world."""

from __future__ import annotations

import pytest
from app.main import _default_pipeline, app, replace_pipeline
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Fresh pipeline + client per test.

    Without this fixture, ``app.state.pipeline`` would leak across tests
    and across test modules — e.g. ``test_incidents_empty_at_boot`` only
    passes when no earlier test has already populated
    ``pipeline.last_incidents``. Rebuilding from settings on each test
    matches what boot does and keeps each test self-contained.
    """
    replace_pipeline(_default_pipeline())
    return TestClient(app)


def test_root_returns_service_banner(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "correlator"


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_returns_ready(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "correlator"}


def test_incidents_empty_at_boot(client: TestClient) -> None:
    response = client.get("/incidents")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
