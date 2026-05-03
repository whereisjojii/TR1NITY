"""Wazuh parser tests."""

from __future__ import annotations

import pytest
from app.sources.wazuh import parse

from .conftest import load_json


def test_parse_brute_force_alert_yields_high_severity_event() -> None:
    payload = load_json("wazuh_brute_force.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    assert doc["event"]["module"] == "wazuh"
    assert doc["event"]["dataset"] == "wazuh.alert"
    assert doc["event"]["kind"] == "alert"  # level >= 7
    assert doc["event"]["severity"] >= 4
    assert doc["source"]["ip"] == "203.0.113.45"
    assert "authentication" in doc["event"]["category"]


def test_parse_attaches_mitre_attack_metadata() -> None:
    payload = load_json("wazuh_brute_force.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    assert doc["threat"]["framework"] == "MITRE ATT&CK"
    techs = doc["threat"]["technique"]
    assert any(t.get("id") == "T1110" for t in techs)


def test_parse_malware_alert_uses_malware_category() -> None:
    payload = load_json("wazuh_malware.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    assert "malware" in doc["event"]["category"]
    assert doc["event"]["severity"] >= 6  # level 13 -> high/critical


def test_parse_rejects_payload_without_rule() -> None:
    with pytest.raises(ValueError):
        parse({"timestamp": "2024-01-15T14:32:01.123+0000"})


def test_parse_rejects_non_dict_payload() -> None:
    with pytest.raises(ValueError):
        parse("not a dict")  # type: ignore[arg-type]


def test_parse_preserves_full_log_in_event_original() -> None:
    payload = load_json("wazuh_brute_force.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    assert doc["event"]["original"] == payload["full_log"]


def test_parse_records_raw_hash_for_audit_trail() -> None:
    payload = load_json("wazuh_brute_force.json")
    ev = parse(payload)
    doc = ev.to_index_doc()
    assert len(doc["tr1nity"]["raw_hash_sha256"]) == 64
    # Every alert gets a stable id
    assert doc["event"]["id"]
