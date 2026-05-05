"""OpenSearch event consumer tests (HTTP mocked via httpx.MockTransport)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
from app.consumer.opensearch import OpenSearchEventConsumer


def _hits_payload(hits: list[dict]) -> dict:
    return {
        "took": 1,
        "timed_out": False,
        "hits": {
            "total": {"value": len(hits)},
            "hits": hits,
        },
    }


def _hit(doc_id: str, source: dict) -> dict:
    return {"_id": doc_id, "_source": source}


def test_consumer_returns_events_and_advances_high_water() -> None:
    captured: list[httpx.Request] = []
    events = [
        _hit(
            "id-1",
            {
                "@timestamp": "2026-01-01T12:00:00+00:00",
                "tr1nity": {"source": "firewall"},
                "source": {"ip": "203.0.113.45"},
            },
        ),
        _hit(
            "id-2",
            {
                "@timestamp": "2026-01-01T12:00:30+00:00",
                "tr1nity": {"source": "wazuh"},
                "source": {"ip": "203.0.113.45"},
            },
        ),
    ]
    # Second poll re-returns the boundary doc (gte semantics). The
    # consumer must dedupe it via _seen_at_boundary.
    served: list[list[dict]] = [events, [events[1]], []]

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
    assert body["query"]["range"]["@timestamp"]["gte"] == "2026-01-01T12:00:30+00:00"


def test_consumer_does_not_skip_events_sharing_boundary_timestamp() -> None:
    """Regression: gt would silently drop events tied at the boundary timestamp.

    Round 1 fills max_events=2 with two events at the same timestamp.
    Round 2 must still surface a third, previously-truncated event with
    the *same* timestamp — the gte+_id-dedup machinery makes this safe.
    """
    captured: list[httpx.Request] = []

    def evt(doc_id: str, ts: str, src: str) -> dict:
        return _hit(
            doc_id,
            {"@timestamp": ts, "tr1nity": {"source": src}, "source": {"ip": "203.0.113.45"}},
        )

    boundary_ts = "2026-01-01T12:00:30+00:00"
    served: list[list[dict]] = [
        [evt("id-1", boundary_ts, "firewall"), evt("id-2", boundary_ts, "waf")],
        [
            evt("id-1", boundary_ts, "firewall"),  # dupe (must be filtered)
            evt("id-2", boundary_ts, "waf"),  # dupe (must be filtered)
            evt("id-3", boundary_ts, "wazuh"),  # the previously-skipped tail
        ],
        [],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_hits_payload(served.pop(0) if served else []))

    consumer = OpenSearchEventConsumer(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(handler),
    )
    consumer.replay_from(datetime(2026, 1, 1, 11, 59, 0, tzinfo=UTC))

    first = consumer.fetch(max_events=2)
    assert {e["tr1nity"]["source"] for e in first} == {"firewall", "waf"}

    second = consumer.fetch(max_events=10)
    assert [e["tr1nity"]["source"] for e in second] == ["wazuh"]

    third = consumer.fetch(max_events=10)
    assert third == []


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
