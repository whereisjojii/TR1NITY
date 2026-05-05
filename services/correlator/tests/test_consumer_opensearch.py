"""OpenSearch event consumer tests (HTTP mocked via httpx.MockTransport)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
from app.consumer.opensearch import OpenSearchEventConsumer


def _hits_payload(events: list[dict]) -> dict:
    return {
        "took": 1,
        "timed_out": False,
        "hits": {
            "total": {"value": len(events)},
            "hits": [{"_source": ev} for ev in events],
        },
    }


def test_consumer_returns_events_and_advances_high_water() -> None:
    captured: list[httpx.Request] = []
    events = [
        {
            "@timestamp": "2026-01-01T12:00:00+00:00",
            "tr1nity": {"source": "firewall"},
            "source": {"ip": "203.0.113.45"},
        },
        {
            "@timestamp": "2026-01-01T12:00:30+00:00",
            "tr1nity": {"source": "wazuh"},
            "source": {"ip": "203.0.113.45"},
        },
    ]
    served: list[list[dict]] = [events, []]

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_hits_payload(served.pop(0) if served else []))

    consumer = OpenSearchEventConsumer(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(handler),
    )
    consumer.replay_from(datetime(2026, 1, 1, 11, 59, 0, tzinfo=UTC))

    first = consumer.fetch(max_events=10)
    assert len(first) == 2
    assert consumer._high_water == datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)

    second = consumer.fetch(max_events=10)
    assert second == []

    body = json.loads(captured[1].content.decode("utf-8"))
    assert body["query"]["range"]["@timestamp"]["gt"] == "2026-01-01T12:00:30+00:00"


def test_consumer_handles_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    consumer = OpenSearchEventConsumer(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(handler),
    )
    assert consumer.fetch(max_events=10) == []


def test_consumer_handles_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    consumer = OpenSearchEventConsumer(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(handler),
    )
    assert consumer.fetch(max_events=10) == []
