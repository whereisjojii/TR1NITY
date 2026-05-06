"""Builder helpers for synthetic incident dicts (api tests)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def incident(
    *,
    incident_id: str,
    severity: int = 5,
    sources: list[str] | None = None,
    technique_ids: list[str] | None = None,
    tactic_ids: list[str] | None = None,
    source_ip: str | None = "203.0.113.10",
    title: str | None = None,
    created_at: datetime | None = None,
    last_event_at: datetime | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    now = created_at or datetime.now(UTC)
    last = last_event_at or now + timedelta(minutes=1)
    return {
        "incident_id": incident_id,
        "title": title or f"Incident {incident_id}",
        "summary": summary,
        "severity": severity,
        "status": "open",
        "grouping_key": f"src_ip:{source_ip}" if source_ip else "unknown",
        "sources": list(sources or ["wazuh"]),
        "technique_ids": list(technique_ids or []),
        "tactic_ids": list(tactic_ids or []),
        "members": [
            {
                "event_id": f"evt-{incident_id}-1",
                "timestamp": now.isoformat(),
                "source": (sources or ["wazuh"])[0],
                "severity": severity,
                "source_ip": source_ip,
                "destination_ip": None,
                "user": None,
                "message": "synthetic",
                "technique_ids": list(technique_ids or []),
                "sigma_matches": [],
            }
        ],
        "created_at": now.isoformat(),
        "first_event_at": now.isoformat(),
        "last_event_at": last.isoformat(),
        "member_count": 1,
        "intel_hits": [],
        "sigma_matches": [],
    }
