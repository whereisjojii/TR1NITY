#!/usr/bin/env python3
"""Fire a synthetic 3-event attack chain against a running ingestor.

Generates one event per source (firewall, WAF, Wazuh) with the **same source
IP** and timestamps within a short window — exactly the shape Phase-2's
correlator should later collapse into a single incident.

Usage::

    python scripts/demo/synth_attack.py
    python scripts/demo/synth_attack.py --base-url http://localhost:8001
    python scripts/demo/synth_attack.py --token s3cret  # if auth enabled

Exit code is 0 if every endpoint returned 2xx, non-zero otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

ATTACKER_IP = "203.0.113.45"
VICTIM_IP = "10.0.0.10"
USER_AGENT = "TR1NITY-demo/0.2"


def post_json(url: str, body: Any, token: str | None) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - controlled URL
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return 0, f"network error: {e.reason}"


def step_firewall(base: str, token: str | None) -> tuple[int, str]:
    """Step 1: attacker probes SSH and the firewall blocks it."""
    line = (
        "Jan 15 14:35:22 fw kernel: [12345.6789] IPT-DROP: IN=eth0 OUT= "
        "MAC=aa:bb:cc:dd:ee:ff:11:22:33:44:55:66:08:00 "
        f"SRC={ATTACKER_IP} DST={VICTIM_IP} LEN=60 TOS=0x00 PREC=0x00 "
        "TTL=54 ID=12345 DF PROTO=TCP SPT=41234 DPT=22 WINDOW=29200 "
        "RES=0x00 SYN URGP=0"
    )
    return post_json(
        f"{base}/ingest/syslog", {"lines": [line], "host": "fw-edge"}, token
    )


def step_waf(base: str, token: str | None) -> tuple[int, str]:
    """Step 2: attacker pivots to web app and tries SQLi."""
    payload = {
        "transaction": {
            "client_ip": ATTACKER_IP,
            "client_port": 41235,
            "host_ip": VICTIM_IP,
            "host_port": 443,
            "time_stamp": datetime.now(UTC).strftime("%a %b %d %H:%M:%S %Y"),
            "transaction_id": f"demo-{int(time.time())}",
            "request": {
                "method": "POST",
                "uri": "/login.php?id=1' OR '1'='1",
                "http_version": "1.1",
                "headers": {"User-Agent": "sqlmap/1.7"},
            },
            "response": {"http_code": 403, "intercepted": True},
            "messages": [
                {
                    "message": "SQL Injection Attack: Common Injection Testing Detected",
                    "details": {"ruleId": "942100", "severity": "2"},
                }
            ],
        }
    }
    return post_json(f"{base}/ingest/waf", payload, token)


def step_wazuh(base: str, token: str | None) -> tuple[int, str]:
    """Step 3: Wazuh sees brute-force on SSH from same IP."""
    payload = {
        "timestamp": datetime.now(UTC)
        .strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        .replace("+0000", "+00:00"),
        "rule": {
            "level": 10,
            "description": "sshd: Multiple authentication failures.",
            "id": "5710",
            "groups": ["authentication_failures", "syslog", "sshd"],
            "mitre": {
                "id": ["T1110"],
                "tactic": ["Credential Access"],
                "technique": ["Brute Force"],
            },
        },
        "agent": {"id": "001", "name": "web-server-01", "ip": VICTIM_IP},
        "id": f"{int(time.time())}.{int(time.time() % 1000)}",
        "data": {"srcip": ATTACKER_IP, "srcuser": "admin", "dstuser": "root"},
        "full_log": (
            f"Jan 15 14:36:00 web-server-01 sshd[12345]: Failed password "
            f"for invalid user admin from {ATTACKER_IP} port 41236"
        ),
    }
    return post_json(f"{base}/ingest/wazuh", payload, token)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="Ingestor base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token (only required if ingestor has ENABLE_AUTH=true)",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    print(f"[demo] firing synthetic attack chain at {base}")
    print(f"[demo] attacker={ATTACKER_IP} victim={VICTIM_IP}")
    print()

    steps = [
        ("step 1: firewall  (T1595 - Active Scanning)", step_firewall),
        ("step 2: WAF       (T1190 - Exploit Public-Facing Application)", step_waf),
        ("step 3: Wazuh     (T1110 - Brute Force)", step_wazuh),
    ]
    failed = 0
    for label, fn in steps:
        status, body = fn(base, args.token)
        ok = 200 <= status < 300
        marker = "OK " if ok else "ERR"
        print(f"  [{marker}] {label}  ({status})")
        if not ok:
            print(f"        body: {body[:200]}")
            failed += 1
        time.sleep(0.5)

    print()
    if failed:
        print(f"[demo] {failed}/3 steps failed")
        return 1
    print("[demo] all 3 events accepted by ingestor.")
    print("[demo] In Phase 2, the correlator will collapse these into one incident.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
