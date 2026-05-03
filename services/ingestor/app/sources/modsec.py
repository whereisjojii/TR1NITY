"""ModSecurity / WAF audit -> ECSEvent.

Accepts the v3 JSON audit-log format (the ``transaction`` envelope) emitted by
ModSecurity 3.x running under nginx or Apache. Suricata EVE JSON is also
accepted as a near-equivalent ``alert`` document and routed through the same
parser when the caller passes ``source_hint='suricata'``.

Reference:
https://github.com/SpiderLabs/ModSecurity/wiki/ModSecurity-3:-JSON-output
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
    HTTPBlock,
    RuleBlock,
    SourceDestBlock,
    ThreatBlock,
    ThreatTactic,
    ThreatTechnique,
    TR1NITYBlock,
    URLBlock,
    new_event_id,
    truncate_raw,
    utc_now,
)

MODULE = "waf"

# ModSecurity severity scale (CRM114-like): 0 EMERGENCY .. 7 DEBUG.
# We map to TR1NITY 0..4: 0/1=critical, 2=high, 3=medium, 4=low, 5+=info.
_MODSEC_SEV_TO_INTERNAL = {
    "0": 4,  # emergency
    "1": 4,  # alert
    "2": 3,  # critical
    "3": 3,  # error
    "4": 2,  # warning
    "5": 1,  # notice
    "6": 0,  # info
    "7": 0,  # debug
}


def _classify_attack(messages: list[dict[str, Any]]) -> tuple[list[str], ThreatBlock | None]:
    """Best-effort attack-class extraction from message text.

    Maps OWASP CRS rule names to MITRE ATT&CK technique IDs. Coarse but
    deterministic; production deployments override via the analyst suppression
    layer in Phase 4.
    """
    text = " ".join(str(m.get("message", "")).lower() for m in messages or [])
    cats: list[str] = ["intrusion_detection", "web"]
    techs: list[ThreatTechnique] = []
    tactics: list[ThreatTactic] = []
    if "sql injection" in text or "sqli" in text:
        techs.append(ThreatTechnique(id="T1190", name="Exploit Public-Facing Application"))
        tactics.append(ThreatTactic(id="TA0001", name="Initial Access"))
    if "xss" in text or "cross-site scripting" in text:
        techs.append(ThreatTechnique(id="T1059.007", name="JavaScript"))
    if "command injection" in text or "rce" in text or "remote code execution" in text:
        techs.append(ThreatTechnique(id="T1059", name="Command and Scripting Interpreter"))
    if "path traversal" in text or "lfi" in text or "directory traversal" in text:
        techs.append(ThreatTechnique(id="T1083", name="File and Directory Discovery"))
    if "scanner" in text or "recon" in text:
        techs.append(ThreatTechnique(id="T1595", name="Active Scanning"))
        tactics.append(ThreatTactic(id="TA0043", name="Reconnaissance"))
    threat = (
        ThreatBlock(framework="MITRE ATT&CK", technique=techs, tactic=tactics)
        if (techs or tactics)
        else None
    )
    return cats, threat


def _coerce_port(value: Any) -> int | None:
    """Best-effort cast to a TCP/UDP port number; returns ``None`` on junk."""
    if isinstance(value, int):
        return value if 0 < value < 65536 else None
    if isinstance(value, str) and value.isdigit():
        port = int(value)
        return port if 0 < port < 65536 else None
    return None


def _max_severity(messages: list[dict[str, Any]]) -> int:
    """Highest TR1NITY severity (0-4) found among messages, default 1."""
    worst = 1
    for m in messages or []:
        details = m.get("details") or {}
        sev = str(details.get("severity") or "")
        worst = max(worst, _MODSEC_SEV_TO_INTERNAL.get(sev, 1))
    return worst


def _parse_timestamp(value: Any) -> datetime:
    """ModSec uses ``Mon Jan 15 14:36:45 2024`` — try a few formats."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return utc_now()
    for fmt in ("%a %b %d %H:%M:%S %Y", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return utc_now()


def parse(payload: dict[str, Any]) -> ECSEvent:
    """Convert one ModSecurity v3 JSON audit doc to ECS."""
    if not isinstance(payload, dict):
        raise ValueError("modsec payload must be a JSON object")
    txn = payload.get("transaction") or payload  # tolerate flat shape too
    if not isinstance(txn, dict):
        raise ValueError("modsec payload missing 'transaction' object")

    src_ip = txn.get("client_ip")
    if not src_ip:
        raise ValueError("modsec payload missing transaction.client_ip")

    src_port = _coerce_port(txn.get("client_port"))
    dst_ip = txn.get("host_ip")
    dst_port = _coerce_port(txn.get("host_port"))

    request = txn.get("request") or {}
    response = txn.get("response") or {}
    messages = txn.get("messages") or []

    sev_internal = _max_severity(messages)
    cats, threat = _classify_attack(messages)
    method = (request.get("method") or "").upper() or None
    uri = request.get("uri") or request.get("request_uri") or ""
    status = response.get("http_code") or response.get("status")
    blocked = bool(response.get("intercepted"))

    # First message is most-specific rule; concatenate descriptions.
    rule_id = None
    rule_name = None
    if messages:
        first = messages[0]
        details = first.get("details") or {}
        rule_id = details.get("ruleId") or details.get("ruleid")
        rule_name = first.get("message")

    raw_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    raw_truncated, raw_hash = truncate_raw(raw_str)

    return ECSEvent(
        **{
            "@timestamp": _parse_timestamp(txn.get("time_stamp")),
            "event": EventBlock(
                kind="alert",
                category=cats,  # type: ignore[arg-type]
                type=["denied" if blocked else "info"],
                action="blocked" if blocked else "logged",
                outcome="failure" if blocked else "unknown",
                severity=SEVERITY_MAP[sev_internal],
                module=MODULE,
                dataset="waf.modsecurity",
                original=rule_name,
                id=str(txn.get("transaction_id") or new_event_id()),
                ingested=utc_now(),
            ),
            "source": SourceDestBlock(ip=src_ip, port=src_port),
            "destination": SourceDestBlock(ip=dst_ip, port=dst_port) if dst_ip else None,
            "http": HTTPBlock(
                request={"method": method} if method else None,
                response={"status_code": int(status)} if status and str(status).isdigit() else None,
            ),
            "url": URLBlock(full=uri, path=uri.split("?", 1)[0] if uri else None) if uri else None,
            "rule": RuleBlock(
                id=str(rule_id) if rule_id else None,
                name=rule_name,
                description=" | ".join(str(m.get("message", "")) for m in messages[:3]),
                category="modsecurity",
            ),
            "threat": threat,
            "message": rule_name or f"WAF event from {src_ip}",
            "tags": ["waf", "modsecurity"] + (["blocked"] if blocked else []),
            "tr1nity": TR1NITYBlock(
                source="waf",
                normalizer_version=NORMALIZER_VERSION,
                raw=raw_truncated,
                raw_hash_sha256=raw_hash,
            ),
        }
    )
