"""Smoke tests for the ai-assist Phase-0 hello-world."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_root_returns_service_banner() -> None:
    response = _client().get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ai-assist"
    assert body["mock_llm"] is True


def test_healthz_returns_ok() -> None:
    response = _client().get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_returns_ready() -> None:
    response = _client().get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "ai-assist"}


def test_llm_info_defaults_to_mock_mode() -> None:
    # MOCK_LLM is read at module import time; the default in app.main is "true".
    assert os.environ.get("MOCK_LLM", "true").lower() in {"1", "true", "yes"}
    response = _client().get("/llm/info")
    assert response.status_code == 200
    assert response.json()["mode"] == "mock"
