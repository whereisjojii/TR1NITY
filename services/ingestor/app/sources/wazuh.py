"""Wazuh integrator/webhook payload -> ECSEvent.

Accepts the JSON shape Wazuh sends via its ``integratord`` /
``ossec.conf <integration>`` webhook (and what shows up on
``ossec-archives.json``). Reference:
https://documentation.wazuh.com/current/user-manual/manager/integration-with-external-apis.html

Wazuh rule levels (0-15) are mapped to TR1NITY's 0-4 internal scale, then
to ECS ``event.severity`` 0-7 via :data:`SEVERITY_MAP`.

This parser is intentionally tolerant: missing fields produce ``None`` rather
than exceptions. The only hard requirement is a ``rule`` object — without one
we cannot meaningfully classify the event and we raise ``ValueError``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..ecs import (
    NORMALIZER_VERSION,
    SEVERITY_MAP,
    ECSEvent,
    EventBlock,
    HostBlock,
    RuleBlock,
    SourceDestBlock,
    ThreatBlock,
    ThreatTactic,
    ThreatTechnique,
    TR1NITYBlock,
    UserBlock,
    new_event_id,
    truncate_raw,
    utc_now,
)

MODULE = "wazuh"
DATASET = "wazuh.alert"


def _wazuh_level_to_severity(level: int) -> int:
    """Map Wazuh rule.level (0-15) -> TR1NITY severity (0-4)."""
    if level <= 3:
        return 0  # informational
    if level <= 6:
        return 1  # low
    if level <= 9:
        return 2  # medium
    if level <= 12:
        return 3  # high
    return 4  # critical


def _categories_from_groups(groups: list[str]) -> list[str]:
    """Best-effort Wazuh-group -> ECS event.category mapping."""
    g = {x.lower() for x in groups or []}
    out: list[str] = []
    if g & {"authentication_failures", "authentication_success", "ssh"}:
        out.append("authentication")
    if g & {"intrusion_detection", "ids", "rootkit"}:
        out.append("intrusion_detection")
    if g & {"malware", "virus", "trojan"}:
        out.append("malware")
    if g & {"firewall", "iptables"}:
        out.append("network")
    if g & {"web", "apache", "nginx"}:
        out.append("web")
    if g & {"vulnerability"}:
        out.append("vulnerability")
    if not out:
        out.append("host")
    return out


def _parse_timestamp(value: Any) -> datetime:
    """Wazuh timestamps look like ``2024-01-15T14:32:01.123+0000``."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return utc_now()
    try:
        # ``+0000`` is non-ISO; insert the colon if needed.
        if len(value) >= 5 and value[-5] in "+-" and value[-3] != ":":
            value = value[:-2] + ":" + value[-2:]
        return datetime.fromisoformat(value)
    except ValueError:
        return utc_now()


def _build_threat(mitre: dict[str, Any] | None) -> ThreatBlock | None:
    if not mitre or not isinstance(mitre, dict):
        return None
    tech_ids = mitre.get("id") or []
    tech_names = mitre.get("technique") or []
    tactic_names = mitre.get("tactic") or []
    techniques = [
        ThreatTechnique(id=tid, name=tname)
        for tid, tname in zip(tech_ids, tech_names + [None] * len(tech_ids), strict=False)
    ]
    tactics = [ThreatTactic(name=tn) for tn in tactic_names]
    if not techniques and not tactics:
        return None
    return ThreatBlock(
        framework="MITRE ATT&CK",
        technique=techniques,
        tactic=tactics,
    )


def parse(payload: dict[str, Any]) -> ECSEvent:
    """Convert one Wazuh alert JSON object to an :class:`ECSEvent`.

    Raises:
        ValueError: when ``payload`` lacks a ``rule`` object — Wazuh always
            emits one, so its absence indicates a malformed feed.
    """
    if not isinstance(payload, dict):
        raise ValueError("wazuh payload must be a JSON object")
    rule = payload.get("rule") or {}
    if not isinstance(rule, dict) or "id" not in rule:
        raise ValueError("wazuh payload missing rule.id — refusing to ingest")

    level = int(rule.get("level", 0))
    sev = _wazuh_level_to_severity(level)
    groups = rule.get("groups") or []
    categories = _categories_from_groups(groups)

    agent = payload.get("agent") or {}
    data = payload.get("data") or {}
    src_ip = data.get("srcip") or data.get("src_ip") or data.get("source_ip")
    src_user = data.get("srcuser") or data.get("user")
    dst_user = data.get("dstuser")

    raw_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    raw_truncated, raw_hash = truncate_raw(raw_str)

    event = EventBlock(
        kind="alert" if level >= 7 else "event",
        category=categories,  # type: ignore[arg-type]
        type=["info"],
        outcome="success" if "success" in groups else None,
        severity=SEVERITY_MAP[sev],
        module=MODULE,
        dataset=DATASET,
        original=payload.get("full_log"),
        id=str(payload.get("id") or new_event_id()),
        ingested=utc_now(),
    )

    host = (
        HostBlock(
            name=agent.get("name"),
            hostname=agent.get("name"),
            ip=[agent["ip"]] if agent.get("ip") else [],
        )
        if agent
        else None
    )

    src = SourceDestBlock(ip=src_ip) if src_ip else None
    user = UserBlock(name=src_user or dst_user) if (src_user or dst_user) else None

    rule_block = RuleBlock(
        id=str(rule.get("id")),
        name=rule.get("description"),
        description=rule.get("description"),
        category=",".join(groups) if groups else None,
    )

    threat = _build_threat(rule.get("mitre"))

    tags = ["wazuh"]
    if level >= 12:
        tags.append("high-severity")
    if "authentication_failures" in groups:
        tags.append("auth-failure")

    return ECSEvent(
        **{
            "@timestamp": _parse_timestamp(payload.get("timestamp")),
            "event": event,
            "host": host,
            "source": src,
            "user": user,
            "rule": rule_block,
            "threat": threat,
            "message": rule.get("description"),
            "tags": tags,
            "tr1nity": TR1NITYBlock(
                source="wazuh",
                normalizer_version=NORMALIZER_VERSION,
                raw=raw_truncated,
                raw_hash_sha256=raw_hash,
            ),
        }
    )
