"""Sliding-window event grouping.

The first cut of "correlation" in TR1NITY is intentionally simple and
deterministic: events that share the same *grouping key* and whose
timestamps fall within a sliding time window are merged into one
incident. Today the grouping key is the source IP — operationally the
most useful single signal — but the function is split out so future
phases can swap in entity-resolved keys (e.g. "user@host" or
"asset_id") without rewriting the pipeline.

This module is **stateless** between calls: callers feed it a batch of
events and get back a list of incidents. Persistence and incremental
updates are the sink layer's job.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from .incident import Incident, IncidentMember, promote_severity

log = logging.getLogger(__name__)


def derive_grouping_key(event: dict[str, Any]) -> str | None:
    """Pick the grouping key for one ECS event.

    Today: source.ip. Returns ``None`` for events that have no source IP
    and therefore cannot be grouped (the pipeline ships them as their
    own single-event incidents).
    """
    src = event.get("source") or {}
    ip = src.get("ip") if isinstance(src, dict) else None
    if isinstance(ip, str) and ip:
        return f"src_ip:{ip}"
    return None


def event_timestamp(event: dict[str, Any]) -> datetime | None:
    """Extract ``@timestamp`` from an ECS event dict.

    Accepts either the canonical ``@timestamp`` key or the Pydantic
    field name ``timestamp`` (when the dict came straight from
    ``model_dump`` without ``by_alias``).
    """
    raw = event.get("@timestamp") or event.get("timestamp")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _event_severity(event: dict[str, Any]) -> int:
    ev = event.get("event") or {}
    sev = ev.get("severity") if isinstance(ev, dict) else 0
    try:
        return int(sev or 0)
    except (TypeError, ValueError):
        return 0


def _event_techniques(event: dict[str, Any]) -> list[str]:
    threat = event.get("threat") or {}
    if not isinstance(threat, dict):
        return []
    techniques = threat.get("technique") or []
    if not isinstance(techniques, list):
        return []
    out: list[str] = []
    for t in techniques:
        tid = t.get("id") if isinstance(t, dict) else None
        if isinstance(tid, str) and tid:
            out.append(tid)
    return out


def _event_tactics(event: dict[str, Any]) -> list[str]:
    threat = event.get("threat") or {}
    if not isinstance(threat, dict):
        return []
    tactics = threat.get("tactic") or []
    if not isinstance(tactics, list):
        return []
    out: list[str] = []
    for t in tactics:
        tid = t.get("id") if isinstance(t, dict) else None
        if isinstance(tid, str) and tid:
            out.append(tid)
    return out


def _event_sigma_matches(event: dict[str, Any]) -> list[str]:
    tr = event.get("tr1nity") or {}
    if not isinstance(tr, dict):
        return []
    matches = tr.get("sigma_matches") or []
    if not isinstance(matches, list):
        return []
    return [str(m) for m in matches if isinstance(m, str) and m]


def _to_member(event: dict[str, Any]) -> IncidentMember | None:
    """Promote one ECS event dict to an IncidentMember."""
    ts = event_timestamp(event)
    if ts is None:
        return None
    ev = event.get("event") or {}
    src = event.get("source") or {}
    dst = event.get("destination") or {}
    user = event.get("user") or {}
    tr = event.get("tr1nity") or {}
    return IncidentMember(
        event_id=str(ev.get("id") or event.get("id") or "unknown"),
        timestamp=ts,
        source=str(tr.get("source") or "unknown"),
        dataset=str(ev.get("dataset")) if ev.get("dataset") else None,
        severity=_event_severity(event),
        source_ip=src.get("ip") if isinstance(src, dict) else None,
        destination_ip=dst.get("ip") if isinstance(dst, dict) else None,
        user=user.get("name") if isinstance(user, dict) else None,
        message=event.get("message"),
        technique_ids=_event_techniques(event),
        sigma_matches=_event_sigma_matches(event),
    )


def group_events(
    events: Iterable[dict[str, Any]],
    *,
    window_seconds: int = 900,
    max_events_per_incident: int = 500,
) -> list[Incident]:
    """Partition ``events`` into a list of Incidents.

    Algorithm:
      1. Sort events by timestamp ascending.
      2. Walk events in order. For each, compute its grouping key.
      3. If there is an open bucket for that key whose ``last_event_at``
         is within ``window_seconds`` AND its member count is below
         ``max_events_per_incident``, append this event.
      4. Otherwise start a new bucket.
      5. Events without a grouping key become single-event incidents.

    Returns the full list of incidents, in order of ``first_event_at``.
    """
    # Materialize + sort. Events without a parseable timestamp are dropped
    # (they cannot be ordered safely; the ingestor should never produce
    # them, so this is a defense-in-depth check).
    sortable: list[tuple[datetime, dict[str, Any]]] = []
    for ev in events:
        ts = event_timestamp(ev)
        if ts is None:
            log.warning("group_events: event with no timestamp dropped: id=%s", ev.get("id"))
            continue
        sortable.append((ts, ev))
    sortable.sort(key=lambda pair: pair[0])

    open_buckets: dict[str, Incident] = {}  # grouping_key -> open Incident
    closed: list[Incident] = []

    for ts, ev in sortable:
        member = _to_member(ev)
        if member is None:
            continue

        key = derive_grouping_key(ev)
        if key is None:
            # Single-event incident, immediately closed.
            inc = Incident(
                grouping_key="event_id:" + member.event_id,
                first_event_at=ts,
                last_event_at=ts,
                title=_render_title([member], "event_id:" + member.event_id),
                members=[member],
                technique_ids=member.technique_ids[:],
                tactic_ids=_event_tactics(ev),
                severity=member.severity,
                member_count=1,
                sources=[member.source] if member.source else [],
            )
            closed.append(inc)
            continue

        bucket = open_buckets.get(key)
        if bucket is not None:
            elapsed = (ts - bucket.last_event_at).total_seconds()
            if elapsed > window_seconds or len(bucket.members) >= max_events_per_incident:
                # Window closed or capped — flush this bucket and start a fresh one.
                _finalize(bucket)
                closed.append(bucket)
                bucket = None

        if bucket is None:
            bucket = Incident(
                grouping_key=key,
                first_event_at=ts,
                last_event_at=ts,
                title="",  # filled in by _finalize / on append below
                members=[],
            )
            open_buckets[key] = bucket

        bucket.members.append(member)
        bucket.last_event_at = ts
        bucket.member_count = len(bucket.members)
        for tid in member.technique_ids:
            if tid not in bucket.technique_ids:
                bucket.technique_ids.append(tid)
        for tac in _event_tactics(ev):
            if tac not in bucket.tactic_ids:
                bucket.tactic_ids.append(tac)
        if member.source and member.source not in bucket.sources:
            bucket.sources.append(member.source)

    # Flush any remaining open buckets.
    for bucket in open_buckets.values():
        _finalize(bucket)
        closed.append(bucket)

    closed.sort(key=lambda inc: inc.first_event_at)
    return closed


def _finalize(incident: Incident) -> None:
    """Compute roll-up fields once a bucket is closed."""
    incident.severity = promote_severity([m.severity for m in incident.members])
    incident.title = _render_title(incident.members, incident.grouping_key)
    incident.summary = _render_summary(incident)


def _render_title(members: list[IncidentMember], grouping_key: str) -> str:
    if not members:
        return f"Empty incident ({grouping_key})"
    sources = sorted({m.source for m in members if m.source})
    chain = " → ".join(sources) if sources else "events"
    if grouping_key.startswith("src_ip:"):
        ip = grouping_key.split(":", 1)[1]
        return f"{chain} from {ip} ({len(members)} events)"
    return f"{chain} — {len(members)} events"


def _render_summary(incident: Incident) -> str:
    parts: list[str] = []
    if incident.technique_ids:
        parts.append("ATT&CK: " + ", ".join(incident.technique_ids))
    if incident.sources:
        parts.append("sources: " + ", ".join(sorted(incident.sources)))
    parts.append(f"events: {len(incident.members)}")
    parts.append(
        "window: " f"{incident.first_event_at.isoformat()} → {incident.last_event_at.isoformat()}"
    )
    return " | ".join(parts)
