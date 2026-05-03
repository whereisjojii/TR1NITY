"""Smoke tests for the api Phase-0 hello-world."""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root_returns_service_banner() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "api"


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_returns_ready() -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "api"}


def test_websocket_echo() -> None:
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello == {"type": "hello", "service": "api"}
        ws.send_text("ping")
        echo = ws.receive_json()
        assert echo == {"type": "echo", "received": "ping"}
