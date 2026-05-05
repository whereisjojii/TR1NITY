"""Firewall syslog parser tests."""

from __future__ import annotations

import pytest
from app.sources.firewall import parse, parse_iptables, parse_lines, parse_pfsense

from .conftest import load_text


def test_parse_iptables_drop_classifies_as_denied_failure() -> None:
    line = load_text("iptables_drop.txt")
    ev = parse_iptables(line)
    doc = ev.to_index_doc()
    assert doc["event"]["module"] == "firewall"
    assert doc["event"]["dataset"] == "firewall.iptables"
    assert "denied" in doc["event"]["type"]
    assert doc["event"]["outcome"] == "failure"
    assert doc["source"]["ip"] == "203.0.113.45"
    assert doc["destination"]["port"] == 22
    assert doc["network"]["transport"] == "tcp"


def test_parse_iptables_rejects_non_iptables_line() -> None:
    with pytest.raises(ValueError):
        parse_iptables("Jan 15 14:35:22 fw kernel: kernel boot messages")


def test_parse_pfsense_block_extracts_src_dst() -> None:
    line = load_text("pfsense_block.txt")
    ev = parse_pfsense(line)
    doc = ev.to_index_doc()
    assert doc["event"]["dataset"] == "firewall.pfsense"
    assert doc["event"]["outcome"] == "failure"
    assert doc["source"]["ip"] == "203.0.113.45"
    assert doc["source"]["port"] == 41234
    assert doc["destination"]["ip"] == "10.0.0.10"
    assert doc["destination"]["port"] == 22
    assert doc["network"]["transport"] == "tcp"
    assert doc["network"]["direction"] == "ingress"


def test_parse_auto_dispatches_correctly() -> None:
    ev_ipt = parse(load_text("iptables_drop.txt"))
    ev_pf = parse(load_text("pfsense_block.txt"))
    assert ev_ipt.to_index_doc()["event"]["dataset"] == "firewall.iptables"
    assert ev_pf.to_index_doc()["event"]["dataset"] == "firewall.pfsense"


def test_parse_lines_separates_successes_and_errors() -> None:
    good = load_text("iptables_drop.txt")
    bad = "this is not a firewall log line at all"
    parsed, errs = parse_lines([good, bad, good])
    assert len(parsed) == 2
    assert len(errs) == 1
    assert "unrecognized" in errs[0]["error"].lower() or "not" in errs[0]["error"].lower()


def test_parse_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        parse("")
    with pytest.raises(ValueError):
        parse("   \n\t  ")


def test_iptables_records_raw_hash_for_audit() -> None:
    ev = parse_iptables(load_text("iptables_drop.txt"))
    doc = ev.to_index_doc()
    assert len(doc["tr1nity"]["raw_hash_sha256"]) == 64
