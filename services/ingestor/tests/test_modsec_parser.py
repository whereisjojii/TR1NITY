"""ModSecurity parser tests."""

from __future__ import annotations

import pytest
from app.sources.modsec import parse

from .conftest import load_json


def test_parse_sqli_audit_blocks_and_tags_attack() -> None:
    payload = load_json("modsec_sqli.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    assert doc["event"]["module"] == "waf"
    assert doc["event"]["dataset"] == "waf.modsecurity"
    assert doc["event"]["kind"] == "alert"
    assert doc["event"]["outcome"] == "failure"  # intercepted=true
    assert "blocked" in doc["tags"]
    assert doc["http"]["response"]["status_code"] == 403
    assert doc["source"]["ip"] == "203.0.113.45"


def test_parse_sqli_tags_with_mitre_initial_access() -> None:
    payload = load_json("modsec_sqli.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    threat = doc.get("threat") or {}
    techs = [t.get("id") for t in threat.get("technique", [])]
    assert "T1190" in techs


def test_parse_rejects_payload_without_client_ip() -> None:
    bad = {"transaction": {"messages": []}}
    with pytest.raises(ValueError):
        parse(bad)


def test_parse_tolerates_flat_payload() -> None:
    flat = {
        "client_ip": "10.0.0.5",
        "host_ip": "10.0.0.10",
        "messages": [
            {
                "message": "XSS attempt",
                "details": {"ruleId": "941100", "severity": "3"},
            }
        ],
    }
    ev = parse(flat)
    doc = ev.to_index_doc()
    assert doc["source"]["ip"] == "10.0.0.5"


def test_parse_extracts_url_and_method() -> None:
    payload = load_json("modsec_sqli.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    assert doc["url"]["full"] == "/login.php?id=1' OR '1'='1"
    assert doc["http"]["request"]["method"] == "POST"
