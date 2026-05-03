"""OpenSearch sink tests — uses httpx MockTransport, no live cluster needed."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from app.ecs import ECSEvent, EventBlock, TR1NITYBlock
from app.sinks.opensearch import OpenSearchSink


def _ev() -> ECSEvent:
    return ECSEvent(
        **{
            "@timestamp": datetime.now(UTC),
            "event": EventBlock(kind="event", module="test", dataset="test.fixture", id="abc-123"),
            "tr1nity": TR1NITYBlock(source="synthetic"),
        }
    )


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_bulk_write_records_per_item_status() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/_bulk"
        # Verify NDJSON shape
        lines = req.content.decode().strip().split("\n")
        assert len(lines) == 4  # 2 events -> 4 lines (action + doc, twice)
        for i in (0, 2):
            assert "index" in json.loads(lines[i])
        return httpx.Response(
            200,
            json={
                "items": [
                    {"index": {"status": 201}},
                    {"index": {"status": 400, "error": {"type": "mapper_parsing_exception"}}},
                ]
            },
        )

    sink = OpenSearchSink("http://os.local:9200", client=_client(handler))
    result = await sink.write([_ev(), _ev()])
    assert result.accepted == 1
    assert result.rejected == 1
    assert result.errors


@pytest.mark.asyncio
async def test_network_failure_marks_all_rejected() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated DNS failure")

    sink = OpenSearchSink("http://os.local:9200", client=_client(handler))
    result = await sink.write([_ev(), _ev()])
    assert result.accepted == 0
    assert result.rejected == 2
    assert any("network" in e for e in result.errors)


@pytest.mark.asyncio
async def test_auth_failure_marks_all_rejected() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    sink = OpenSearchSink("http://os.local:9200", client=_client(handler))
    result = await sink.write([_ev()])
    assert result.accepted == 0
    assert result.rejected == 1
    assert any("401" in e for e in result.errors)


@pytest.mark.asyncio
async def test_healthy_returns_true_for_green_or_yellow() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "yellow"})

    sink = OpenSearchSink("http://os.local:9200", client=_client(handler))
    assert await sink.healthy() is True


@pytest.mark.asyncio
async def test_healthy_returns_false_for_red_cluster() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "red"})

    sink = OpenSearchSink("http://os.local:9200", client=_client(handler))
    assert await sink.healthy() is False


@pytest.mark.asyncio
async def test_empty_batch_is_a_noop() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called for empty batch")

    sink = OpenSearchSink("http://os.local:9200", client=_client(handler))
    result = await sink.write([])
    assert result.accepted == 0
    assert result.rejected == 0
