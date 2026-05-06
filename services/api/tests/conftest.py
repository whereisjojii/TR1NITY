"""Shared pytest fixtures for the api service tests."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from app.clients.correlator import CorrelatorClient
from app.clients.opensearch import OpenSearchIncidentReader
from app.dependencies import (
    get_correlator_client,
    get_opensearch_reader,
    get_store_dep,
    reset_dependency_caches,
)
from app.main import app as fastapi_app
from app.realtime import (
    ConnectionManager,
    get_connection_manager,
    replace_connection_manager,
)
from app.store import CockpitStore, replace_store
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test doubles for the upstream services.
# ---------------------------------------------------------------------------


def _ok(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=payload)


def _empty_search() -> httpx.Response:
    return httpx.Response(404, json={"error": "index_not_found"})


def make_correlator_transport(
    *,
    incidents: list[dict[str, Any]] | None = None,
    healthz_status: int = 200,
    correlate_response: dict[str, Any] | None = None,
) -> httpx.MockTransport:
    """Build an httpx mock transport that fakes the correlator's API."""

    incidents_payload = list(incidents or [])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            if healthz_status == 200:
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(healthz_status, json={"status": "fail"})
        if request.url.path == "/incidents" and request.method == "GET":
            return _ok({"items": list(incidents_payload), "total": len(incidents_payload)})
        if request.url.path == "/correlate" and request.method == "POST":
            payload = correlate_response or {
                "incidents": list(incidents_payload),
                "incident_count": len(incidents_payload),
                "sinks": [],
            }
            return _ok(payload)
        return httpx.Response(404, json={"error": "not_found"})

    return httpx.MockTransport(handler)


def make_opensearch_transport(*, hits: list[dict[str, Any]] | None = None) -> httpx.MockTransport:
    """Mock OpenSearch ``/_search`` and surface ``hits.hits[]._source``."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/_search"):
            sources = list(hits or [])
            return _ok(
                {
                    "hits": {
                        "total": {"value": len(sources)},
                        "hits": [{"_source": s} for s in sources],
                    }
                }
            )
        return _empty_search()

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singletons() -> Iterator[None]:
    """Reset cached singletons + store between tests."""
    reset_dependency_caches()
    replace_store(CockpitStore())
    replace_connection_manager(ConnectionManager())
    yield
    reset_dependency_caches()
    replace_store(CockpitStore())
    replace_connection_manager(ConnectionManager())
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def store() -> CockpitStore:
    return get_store_dep()


@pytest.fixture
def manager() -> ConnectionManager:
    return get_connection_manager()


@pytest.fixture
def fake_correlator() -> CorrelatorClient:
    transport = make_correlator_transport()
    return CorrelatorClient(base_url="http://correlator", transport=transport)


@pytest.fixture
def client_factory():
    """Build a TestClient with overridable correlator/opensearch fakes."""

    def _factory(
        *,
        incidents: list[dict[str, Any]] | None = None,
        os_hits: list[dict[str, Any]] | None = None,
        correlate_response: dict[str, Any] | None = None,
        correlator_healthz_status: int = 200,
    ) -> TestClient:
        correlator = CorrelatorClient(
            base_url="http://correlator",
            transport=make_correlator_transport(
                incidents=incidents,
                healthz_status=correlator_healthz_status,
                correlate_response=correlate_response,
            ),
        )
        opensearch = OpenSearchIncidentReader(
            base_url="http://os",
            transport=make_opensearch_transport(hits=os_hits),
        )
        fastapi_app.dependency_overrides[get_correlator_client] = lambda: correlator
        fastapi_app.dependency_overrides[get_opensearch_reader] = lambda: opensearch
        return TestClient(fastapi_app)

    return _factory


@pytest.fixture
def client(client_factory) -> TestClient:
    return client_factory()
