"""Incident data model.

An *incident* in TR1NITY is the unit of human attention: a small group of
related ECS events that, taken together, describe one attack or one piece
of suspicious activity. The correlator's whole job is to take a stream of
ECS events and emit Incidents.

This file defines:

* ``IncidentSeverity`` — promotion rules from member-event severity to a
  single incident severity (we always escalate; one ``critical`` member
  forces ``critical``).
* ``IncidentMember`` — a thin record pointing back at the source event
  (id, timestamp, source ip, brief summary).
* ``Incident`` — the aggregate that gets shipped to OpenSearch under
  ``tr1nity-incidents-YYYY.MM.dd``.

We deliberately keep the schema small: anything correlator-specific goes
in a dedicated field, never overloads ECS. Downstream consumers (Cockpit
in Phase 3, AI Assist in Phase 5, Reporting in Phase 6) read these docs
without surprise.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ECS uses syslog-style integer severities (0-7). We carry the same scale
# on incidents so OpenSearch dashboards can sort/filter uniformly.
IncidentSeverityCode = int  # 0..7

IncidentStatus = Literal[
    "open",
    "triaging",
    "resolved",
    "false_positive",
    "suppressed",
]


class IncidentMember(BaseModel):
    """One ECS event that belongs to an incident.

    Stored denormalized so that opening the incident doc gives an analyst
    everything they need without a second OpenSearch query (a "Cockpit
    works offline" property we want to preserve).
    """

    model_config = ConfigDict(extra="allow")

    event_id: str
    timestamp: datetime
    source: str  # tr1nity.source: wazuh / firewall / waf / ...
    dataset: str | None = None
    severity: IncidentSeverityCode = 0
    source_ip: str | None = None
    destination_ip: str | None = None
    user: str | None = None
    message: str | None = None
    technique_ids: list[str] = Field(default_factory=list)


class Incident(BaseModel):
    """A correlated incident — what an analyst opens in the Cockpit."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_event_at: datetime
    first_event_at: datetime

    # Grouping key — what made these events "the same thing".
    # Today: source IP + sliding window. Future: entity-resolved tuple.
    grouping_key: str

    title: str
    summary: str | None = None
    severity: IncidentSeverityCode = 0
    status: IncidentStatus = "open"

    # Member events (denormalized — see IncidentMember docstring).
    members: list[IncidentMember] = Field(default_factory=list)

    # MITRE ATT&CK chain — promoted union of all member techniques.
    technique_ids: list[str] = Field(default_factory=list)
    tactic_ids: list[str] = Field(default_factory=list)

    # SIGMA rules that fired for any member event.
    sigma_matches: list[str] = Field(default_factory=list)

    # Threat-intel hits (denormalized so analysts see them on open).
    intel_hits: list[dict[str, Any]] = Field(default_factory=list)

    # Internal accounting.
    member_count: int = 0
    sources: list[str] = Field(default_factory=list)

    def to_index_doc(self) -> dict[str, Any]:
        """Render to the dict shape OpenSearch expects."""
        return self.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# Severity promotion
# ---------------------------------------------------------------------------


def promote_severity(member_severities: list[IncidentSeverityCode]) -> IncidentSeverityCode:
    """Roll up member severities into one incident severity.

    Conservative rule: an incident is at least as severe as its worst
    member. Empty list → 0 (informational).
    """
    if not member_severities:
        return 0
    return max(0, min(7, max(member_severities)))
