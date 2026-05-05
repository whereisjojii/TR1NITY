"""SIGMA engine tests — parsing and matching."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.sigma.engine import (
    SigmaEngine,
    _eval_condition,
    _parse_yaml_text,
    load_rules_from_dir,
)

from tests.conftest import make_event


def _engine_from_yaml(yaml_text: str) -> SigmaEngine:
    return SigmaEngine(rules=_parse_yaml_text(yaml_text))


def test_simple_eq_selection_matches() -> None:
    yaml_text = """
title: Match Wazuh source
detection:
  selection:
    tr1nity.source: wazuh
  condition: selection
"""
    engine = _engine_from_yaml(yaml_text)
    matches = engine.match(make_event(source="wazuh"))
    assert len(matches) == 1
    matches = engine.match(make_event(source="firewall"))
    assert matches == []


def test_contains_modifier_matches_substring() -> None:
    yaml_text = """
title: SQLi
detection:
  selection:
    message|contains: "UNION SELECT"
  condition: selection
"""
    engine = _engine_from_yaml(yaml_text)
    assert engine.match(make_event(message="bad ' OR 1=1 UNION SELECT * FROM users"))
    assert not engine.match(make_event(message="harmless"))


def test_re_modifier_matches_regex() -> None:
    yaml_text = """
title: Path traversal
detection:
  selection:
    url.path|re: "(\\\\.\\\\./|\\\\.\\\\.\\\\\\\\)"
  condition: selection
"""
    engine = _engine_from_yaml(yaml_text)
    assert engine.match(make_event(url_path="/static/../etc/passwd"))
    assert not engine.match(make_event(url_path="/normal/path"))


def test_or_combinator_in_condition() -> None:
    yaml_text = """
title: A or B
detection:
  sel_a:
    tr1nity.source: wazuh
  sel_b:
    tr1nity.source: firewall
  condition: sel_a or sel_b
"""
    engine = _engine_from_yaml(yaml_text)
    assert engine.match(make_event(source="wazuh"))
    assert engine.match(make_event(source="firewall"))
    assert not engine.match(make_event(source="waf"))


def test_and_combinator_in_condition() -> None:
    yaml_text = """
title: Wazuh + level
detection:
  sel_src:
    tr1nity.source: wazuh
  sel_sev:
    event.severity: 6
  condition: sel_src and sel_sev
"""
    engine = _engine_from_yaml(yaml_text)
    assert engine.match(make_event(source="wazuh", severity=6))
    assert not engine.match(make_event(source="wazuh", severity=2))
    assert not engine.match(make_event(source="firewall", severity=6))


def test_one_of_with_glob_prefix() -> None:
    yaml_text = """
title: 1 of star
detection:
  sel_a:
    tr1nity.source: wazuh
  sel_b:
    tr1nity.source: firewall
  unrelated:
    tr1nity.source: waf
  condition: 1 of sel_*
"""
    engine = _engine_from_yaml(yaml_text)
    assert engine.match(make_event(source="wazuh"))
    assert engine.match(make_event(source="firewall"))
    assert not engine.match(make_event(source="waf"))


def test_list_value_is_or_within_a_field() -> None:
    yaml_text = """
title: List values
detection:
  selection:
    event.severity:
      - 4
      - 6
      - 7
  condition: selection
"""
    engine = _engine_from_yaml(yaml_text)
    assert engine.match(make_event(severity=4))
    assert engine.match(make_event(severity=6))
    assert not engine.match(make_event(severity=2))


def test_unknown_modifier_raises_at_parse_time() -> None:
    yaml_text = """
title: Bad
detection:
  selection:
    message|wat: "x"
  condition: selection
"""
    with pytest.raises(ValueError, match="unsupported modifier"):
        _engine_from_yaml(yaml_text)


def test_eval_condition_rejects_unknown_selection() -> None:
    with pytest.raises(ValueError, match="unknown selection"):
        _eval_condition("missing", {}, {})


def test_severity_mapping_from_level() -> None:
    yaml_text = """
title: High sev
level: high
detection:
  selection:
    tr1nity.source: wazuh
  condition: selection
"""
    engine = _engine_from_yaml(yaml_text)
    matches = engine.match(make_event(source="wazuh"))
    assert matches[0].severity == 6


def test_load_rules_from_bundled_pack(tmp_path: Path) -> None:
    bundled = Path(__file__).resolve().parents[1] / "app" / "sigma" / "rules"
    rules = load_rules_from_dir(bundled)
    assert len(rules) >= 3
    titles = {r.title for r in rules}
    assert "SSH brute-force burst (Wazuh)" in titles


def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    rules = load_rules_from_dir(tmp_path / "does_not_exist")
    assert rules == []


def test_bundled_brute_force_rule_matches_wazuh_event() -> None:
    bundled = Path(__file__).resolve().parents[1] / "app" / "sigma" / "rules"
    engine = SigmaEngine(rules=load_rules_from_dir(bundled))
    event = make_event(
        source="wazuh",
        rule_id="5503",
        rule_category="authentication_failures",
    )
    matches = engine.match(event)
    titles = [m.rule_title for m in matches]
    assert "SSH brute-force burst (Wazuh)" in titles
