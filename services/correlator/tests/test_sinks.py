"""Tests for the incident sinks."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import httpx
from app.incident import Incident, IncidentMember
from app.sinks import OpenSearchIncidentSink, StdoutIncidentSink


def _sample_incident(*, incident_id: str = "inc-1") -> Incident:
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return Incident(
        incident_id=incident_id,
        created_at=ts,
        first_event_at=ts,
        last_event_at=ts,
        grouping_key="src_ip:203.0.113.45",
        title="test incident",
        members=[
            IncidentMember(
                event_id="evt-1",
                timestamp=ts,
                source="wazuh",
                severity=4,
                source_ip="203.0.113.45",
            )
        ],
        member_count=1,
        sources=["wazuh"],
    )


def test_stdout_sink_writes_one_json_line_per_incident() -> None:
    buf = io.StringIO()
    sink = StdoutIncidentSink(stream=buf)
    result = sink.write([_sample_incident(), _sample_incident(incident_id="inc-2")])
    assert result.accepted == 2
    assert result.rejected == 0
    lines = [line for line in buf.getvalue().splitlines() if line]
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert {p["incident_id"] for p in parsed} == {"inc-1", "inc-2"}


def test_opensearch_sink_records_per_item_status() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        body = {
            "took": 4,
            "errors": False,
            "items": [
                {"index": {"_id": "inc-1", "status": 201}},
            ],
        }
        return httpx.Response(200, json=body)

    sink = OpenSearchIncidentSink(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(handler),
    )
    result = sink.write([_sample_incident()])
    assert result.accepted == 1
    assert result.rejected == 0
    assert len(captured) == 1
    assert captured[0].url.path == "/_bulk"
    body_text = captured[0].content.decode("utf-8")
    # NDJSON: action line, doc line.
    assert body_text.count("\n") == 2
    assert "tr1nity-incidents-2026.01.01" in body_text


def test_opensearch_sink_rejects_on_per_item_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "took": 4,
            "errors": True,
            "items": [
                {
                    "index": {
                        "_id": "inc-1",
                        "status": 400,
                        "error": {"type": "mapper_parsing_exception", "reason": "bad"},
                    }
                }
            ],
        }
        return httpx.Response(200, json=body)

    sink = OpenSearchIncidentSink(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(handler),
    )
    result = sink.write([_sample_incident()])
    assert result.accepted == 0
    assert result.rejected == 1
    assert any("mapper_parsing_exception" in e for e in result.errors)


def test_opensearch_sink_handles_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    sink = OpenSearchIncidentSink(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(handler),
    )
    result = sink.write([_sample_incident()])
    assert result.rejected == 1
    assert result.errors
    assert "network" in result.errors[0]


def test_opensearch_sink_no_op_on_empty_input() -> None:
    sink = OpenSearchIncidentSink(
        base_url="http://os.example.com:9200",
        transport=httpx.MockTransport(lambda _: httpx.Response(200)),
    )
    result = sink.write([])
    assert result.accepted == 0
    assert result.rejected == 0
    assert result.errors == []
