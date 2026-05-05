"""Firewall syslog -> ECSEvent.

Supports three commonly-deployed open-source / appliance formats:

* **iptables / netfilter** — the classic ``IPT-DROP: IN=eth0 ... SRC=... DST=...``
  kernel log line.
* **pfSense** — the ``filterlog`` CSV format (BSD-style).
* **OPNsense** — same CSV format as pfSense (forked codebase).

Each line yields a single ECSEvent. Unknown formats raise ``ValueError`` —
the ingestor router catches that and returns 422 without crashing the
service.
"""

from __future__ import annotations

import re
from typing import Any

from ..ecs import (
    NORMALIZER_VERSION,
    SEVERITY_MAP,
    ECSEvent,
    EventBlock,
    HostBlock,
    NetworkBlock,
    RuleBlock,
    SourceDestBlock,
    TR1NITYBlock,
    new_event_id,
    truncate_raw,
    utc_now,
)

MODULE = "firewall"

# ---------------------------------------------------------------------------
# iptables kernel-log regex
# ---------------------------------------------------------------------------
# Examples accepted:
#   Jan 15 14:35:22 fw kernel: [12345.6789] IPT-DROP: IN=eth0 OUT= MAC=...
#       SRC=203.0.113.45 DST=10.0.0.10 LEN=60 PROTO=TCP SPT=41234 DPT=22 ...
#   <kern.warn>kernel: [12345.6789] DROP IN=eth0 OUT= SRC=...

IPTABLES_PREFIX_RE = re.compile(
    r"(?P<action>IPT-DROP|IPT-ACCEPT|DROP|ACCEPT|REJECT)\s*[:]?\s+",
    re.IGNORECASE,
)
IPTABLES_KV_RE = re.compile(r"(?P<key>[A-Z][A-Z0-9_]+)=(?P<val>\S*)")


def _summary(
    action: str,
    src_ip: str | None,
    spt: int | None,
    dst_ip: str | None,
    dpt: int | None,
    proto: str | None,
) -> str:
    """Compact ``ACTION src:port -> dst:port (proto)`` string for event.message."""
    src = f"{src_ip}:{spt}" if (src_ip and spt) else (src_ip or "?")
    dst = f"{dst_ip}:{dpt}" if (dst_ip and dpt) else (dst_ip or "?")
    return f"{action} {src} -> {dst} ({proto or '?'})"


def _pfsense_direction(direction: str | None) -> str | None:
    if direction == "in":
        return "ingress"
    if direction == "out":
        return "egress"
    return None


def _iptables_action_outcome(action: str) -> tuple[str, str]:
    a = action.upper()
    if "DROP" in a or "REJECT" in a:
        return "denied", "failure"
    return "allowed", "success"


def parse_iptables(line: str, host_name: str | None = None) -> ECSEvent:
    line = line.strip()
    m = IPTABLES_PREFIX_RE.search(line)
    if not m:
        raise ValueError("not an iptables/netfilter line")
    action = m.group("action").upper()
    fields: dict[str, str] = {
        kv.group("key"): kv.group("val") for kv in IPTABLES_KV_RE.finditer(line)
    }
    src_ip = fields.get("SRC")
    dst_ip = fields.get("DST")
    if not src_ip:
        raise ValueError("iptables line missing SRC=")

    proto = fields.get("PROTO", "").lower() or None
    spt = int(fields["SPT"]) if "SPT" in fields and fields["SPT"].isdigit() else None
    dpt = int(fields["DPT"]) if "DPT" in fields and fields["DPT"].isdigit() else None
    in_iface = fields.get("IN") or None
    direction = "ingress" if in_iface else "egress"

    ev_type, outcome = _iptables_action_outcome(action)
    raw_truncated, raw_hash = truncate_raw(line)

    return ECSEvent(
        **{
            "@timestamp": utc_now(),
            "event": EventBlock(
                kind="event",
                category=["network"],
                type=[ev_type],  # type: ignore[list-item]
                action=action.lower(),
                outcome=outcome,  # type: ignore[arg-type]
                severity=SEVERITY_MAP[1 if outcome == "failure" else 0],
                module=MODULE,
                dataset="firewall.iptables",
                original=line,
                id=new_event_id(),
                ingested=utc_now(),
            ),
            "host": HostBlock(name=host_name) if host_name else None,
            "source": SourceDestBlock(ip=src_ip, port=spt),
            "destination": (SourceDestBlock(ip=dst_ip, port=dpt) if dst_ip else None),
            "network": NetworkBlock(
                transport=proto,
                direction=direction,  # type: ignore[arg-type]
                bytes=int(fields["LEN"]) if "LEN" in fields and fields["LEN"].isdigit() else None,
            ),
            "rule": RuleBlock(name=action, category="firewall"),
            "message": _summary(action, src_ip, spt, dst_ip, dpt, proto),
            "tags": ["firewall", "iptables"],
            "tr1nity": TR1NITYBlock(
                source="firewall",
                normalizer_version=NORMALIZER_VERSION,
                raw=raw_truncated,
                raw_hash_sha256=raw_hash,
            ),
        }
    )


# ---------------------------------------------------------------------------
# pfSense / OPNsense CSV (filterlog)
# ---------------------------------------------------------------------------
# Format reference:
# https://docs.netgate.com/pfsense/en/latest/monitoring/logs/raw-filter-format.html
# Field 7 = "block"|"pass", field 9 = direction ("in"|"out"), 17 = proto name,
# 19 = src IP, 20 = dst IP, 21 = src port, 22 = dst port (for tcp/udp).


def parse_pfsense(line: str, host_name: str | None = None) -> ECSEvent:
    """Parse a pfSense / OPNsense filterlog CSV line."""
    line = line.strip()
    # Strip optional syslog prefix up to the first comma-bearing field.
    csv_idx = line.find("filterlog")
    csv = line if csv_idx == -1 else line[csv_idx:].split(":", 1)[-1].lstrip()
    parts = csv.split(",")
    if len(parts) < 9:
        raise ValueError("not a pfSense filterlog line")

    action = parts[6] or "unknown"  # "block" or "pass"
    direction = parts[7] or None  # "in" or "out"
    ip_version_raw = parts[8] or "4"

    # Different field layouts for IPv4 vs IPv6, and per-protocol.
    src_ip = dst_ip = None
    spt = dpt = None
    proto = None

    try:
        if ip_version_raw == "4" and len(parts) >= 21:
            proto = parts[16] or None
            src_ip = parts[18] or None
            dst_ip = parts[19] or None
            if proto in {"tcp", "udp"} and len(parts) >= 22:
                spt = int(parts[20]) if parts[20].isdigit() else None
                dpt = int(parts[21]) if parts[21].isdigit() else None
        elif ip_version_raw == "6" and len(parts) >= 18:
            proto = parts[12] or None
            src_ip = parts[15] or None
            dst_ip = parts[16] or None
    except (ValueError, IndexError) as exc:
        raise ValueError(f"malformed pfSense filterlog: {exc}") from exc

    if not src_ip:
        raise ValueError("pfSense line missing source IP")

    outcome = "failure" if action == "block" else "success"
    ev_type = "denied" if action == "block" else "allowed"
    raw_truncated, raw_hash = truncate_raw(line)
    iface = parts[4] or None

    return ECSEvent(
        **{
            "@timestamp": utc_now(),
            "event": EventBlock(
                kind="event",
                category=["network"],
                type=[ev_type],  # type: ignore[list-item]
                action=action,
                outcome=outcome,  # type: ignore[arg-type]
                severity=SEVERITY_MAP[1 if outcome == "failure" else 0],
                module=MODULE,
                dataset="firewall.pfsense",
                original=line,
                id=new_event_id(),
                ingested=utc_now(),
            ),
            "host": HostBlock(name=host_name) if host_name else None,
            "source": SourceDestBlock(ip=src_ip, port=spt),
            "destination": (SourceDestBlock(ip=dst_ip, port=dpt) if dst_ip else None),
            "network": NetworkBlock(
                transport=proto,
                direction=_pfsense_direction(direction),
            ),
            "rule": RuleBlock(
                name=action,
                category="firewall",
                description=f"interface={iface}",
            ),
            "message": _summary(f"pfSense {action}", src_ip, spt, dst_ip, dpt, proto),
            "tags": ["firewall", "pfsense"],
            "tr1nity": TR1NITYBlock(
                source="firewall",
                normalizer_version=NORMALIZER_VERSION,
                raw=raw_truncated,
                raw_hash_sha256=raw_hash,
            ),
        }
    )


# ---------------------------------------------------------------------------
# Auto-detect parser
# ---------------------------------------------------------------------------


def parse(line: str, host_name: str | None = None) -> ECSEvent:
    """Auto-detect the firewall format and dispatch."""
    if not isinstance(line, str) or not line.strip():
        raise ValueError("empty firewall line")
    if "filterlog" in line:
        return parse_pfsense(line, host_name=host_name)
    if IPTABLES_PREFIX_RE.search(line):
        return parse_iptables(line, host_name=host_name)
    # Last-resort attempt to parse as pfSense CSV (no syslog prefix).
    if line.count(",") >= 8:
        return parse_pfsense(line, host_name=host_name)
    raise ValueError("unrecognized firewall log format")


def parse_lines(
    lines: list[str], host_name: str | None = None
) -> tuple[list[ECSEvent], list[dict[str, Any]]]:
    """Parse many lines, returning (successes, [{'line':…, 'error':…}, …])."""
    ok: list[ECSEvent] = []
    errs: list[dict[str, Any]] = []
    for ln in lines:
        try:
            ok.append(parse(ln, host_name=host_name))
        except ValueError as e:
            errs.append({"line": ln[:200], "error": str(e)})
    return ok, errs
