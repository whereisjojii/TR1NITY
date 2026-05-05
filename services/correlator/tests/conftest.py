"""Shared test helpers for the correlator suite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def make_event(
    *,
    source: str = "wazuh",
    timestamp: datetime | None = None,
    source_ip: str | None = "203.0.113.45",
    severity: int = 4,
    technique_ids: list[str] | None = None,
    tactic_ids: list[str] | None = None,
    rule_id: str | None = None,
    rule_category: str | None = None,
    message: str | None = None,
    url_path: str | None = None,
    event_action: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal-but-realistic ECS event dict for tests."""
    ts = timestamp or datetime.now(UTC)
    ev: dict[str, Any] = {
        "@timestamp": ts.isoformat(),
        "ecs.version": "8.11.0",
        "event": {
            "id": f"evt-{ts.isoformat()}-{source}",
            "kind": "alert",
            "category": ["intrusion_detection"],
            "severity": severity,
        },
        "tr1nity": {"source": source, "schema_version": "1"},
        "message": message or f"{source} test event",
    }
    if source_ip:
        ev["source"] = {"ip": source_ip}
    if technique_ids or tactic_ids:
        threat: dict[str, Any] = {"framework": "MITRE ATT&CK"}
        if technique_ids:
            threat["technique"] = [{"id": tid} for tid in technique_ids]
        if tactic_ids:
            threat["tactic"] = [{"id": tid} for tid in tactic_ids]
        ev["threat"] = threat
    if rule_id is not None or rule_category is not None:
        rule: dict[str, Any] = {}
        if rule_id is not None:
            rule["id"] = rule_id
        if rule_category is not None:
            rule["category"] = rule_category
        ev["rule"] = rule
    if url_path is not None:
        ev["url"] = {"path": url_path}
    if event_action is not None:
        ev["event"]["action"] = event_action
    if extra:
        ev.update(extra)
    return ev


def event_burst(
    *,
    count: int,
    source_ip: str = "203.0.113.45",
    spacing_seconds: int = 30,
    start: datetime | None = None,
    source: str = "wazuh",
    technique_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build ``count`` events from one source IP, ``spacing_seconds`` apart."""
    base = start or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return [
        make_event(
            source=source,
            timestamp=base + timedelta(seconds=i * spacing_seconds),
            source_ip=source_ip,
            technique_ids=technique_ids,
        )
        for i in range(count)
    ]
