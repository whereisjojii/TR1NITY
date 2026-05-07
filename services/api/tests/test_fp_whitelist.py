"""Tests for the Layer-1 YAML whitelist."""

from __future__ import annotations

from pathlib import Path

from app.fp.whitelist import (
    WhitelistRule,
    evaluate_whitelist,
    load_whitelist,
    match_incident,
)


def test_load_whitelist_parses_bundled_file() -> None:
    bundled = Path(__file__).resolve().parents[1] / "app" / "fp" / "whitelist.yaml"
    rules = load_whitelist(bundled)
    assert len(rules) >= 1
    names = [r.name for r in rules]
    assert "Authorized vulnerability scanners" in names


def test_load_whitelist_returns_empty_for_missing_file(tmp_path: Path) -> None:
    rules = load_whitelist(tmp_path / "does-not-exist.yaml")
    assert rules == []


def test_load_whitelist_rejects_malformed_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- name: x\n  match: not-a-mapping\n", encoding="utf-8")
    rules = load_whitelist(bad)
    # Match must be a mapping — invalid rule is dropped, file still loads.
    assert rules == []


def test_match_against_denormalised_top_level_fields() -> None:
    rule = WhitelistRule(name="r", match={"sources": ["firewall"]})
    incident = {
        "incident_id": "i-1",
        "sources": ["firewall", "wazuh"],
    }
    hit = match_incident(rule, incident)
    assert hit is not None
    assert hit.matched_fields == ["sources"]


def test_match_against_member_event_dotted_path() -> None:
    rule = WhitelistRule(
        name="r",
        match={"source.ip": ["10.10.99.10"]},
    )
    incident = {
        "incident_id": "i-1",
        "members": [{"source": {"ip": "10.10.99.10"}}],
    }
    hit = match_incident(rule, incident)
    assert hit is not None
    assert hit.matched_fields == ["source.ip"]


def test_match_returns_none_when_any_key_missing() -> None:
    rule = WhitelistRule(
        name="r",
        match={"sources": ["firewall"], "source.ip": "10.10.99.10"},
    )
    incident = {
        "incident_id": "i-1",
        "sources": ["firewall"],
        "members": [{"source": {"ip": "203.0.113.45"}}],
    }
    assert match_incident(rule, incident) is None


def test_evaluate_returns_all_matching_rules() -> None:
    rules = [
        WhitelistRule(name="r1", match={"sources": ["firewall"]}, fp_score=0.9),
        WhitelistRule(name="r2", match={"sources": ["wazuh"]}, fp_score=0.6),
    ]
    incident = {"incident_id": "i", "sources": ["firewall", "wazuh"]}
    hits = evaluate_whitelist(incident, rules)
    assert {h.rule.name for h in hits} == {"r1", "r2"}


def test_wildcard_value_matches_any_non_empty() -> None:
    rule = WhitelistRule(name="r", match={"summary": "*"})
    matched = {"incident_id": "i", "summary": "Foo"}
    not_matched = {"incident_id": "i"}
    assert match_incident(rule, matched) is not None
    assert match_incident(rule, not_matched) is None
