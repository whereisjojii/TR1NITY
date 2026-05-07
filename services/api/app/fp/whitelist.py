"""Layer 1 — deterministic YAML whitelist.

Operator-authored, version-controlled list of "we already know this is
benign" rules. A rule fires when **every** key in its ``match`` block is
satisfied by the incident; the rule's ``fp_score`` then becomes one of
the inputs to :func:`app.fp.scorer.compose_fp_score`.

Rule shape (one entry per item in the YAML list):

    - name: Vulnerability scanner sweeps from authorized IPs
      match:
        source.ip: [10.10.99.10, 10.10.99.11]
        event.module: [iptables]
      fp_score: 0.95
      ttl_days: never
      rationale: "Tenable Nessus scanners — pre-approved by the SOC."

Match values may be scalar (``"foo"``), a list (``["foo", "bar"]``), or
the string ``"*"`` (matches anything truthy). The match keys traverse
ECS-style nested paths (``source.ip``, ``user.name``); the rule also
matches against the denormalised member-event fields the correlator
attaches to incidents (``sources``, ``technique_ids``, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class WhitelistRule:
    """One Layer-1 rule loaded from YAML."""

    name: str
    match: dict[str, Any]
    fp_score: float = 0.95
    rationale: str | None = None
    ttl_days: int | None = None  # ``"never"`` in YAML → None.

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "match": dict(self.match),
            "fp_score": self.fp_score,
            "rationale": self.rationale,
            "ttl_days": self.ttl_days,
        }


@dataclass(slots=True)
class WhitelistMatch:
    """One whitelist hit on a single incident."""

    rule: WhitelistRule
    matched_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule.name,
            "score": self.rule.fp_score,
            "matched_fields": list(self.matched_fields),
            "rationale": self.rule.rationale,
        }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_whitelist(path: str | Path) -> list[WhitelistRule]:
    """Read a whitelist YAML file and return parsed rules.

    Missing files yield an empty list (no whitelist == no Layer-1 hits),
    making the cockpit still bootable on a fresh deploy. Malformed YAML
    raises ``ValueError`` — operators should fix their file rather than
    silently lose protection.
    """
    p = Path(path)
    if not p.exists():
        log.info("Whitelist file %s not found — Layer 1 disabled.", p)
        return []
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as exc:
        raise ValueError(f"failed to parse whitelist {p}: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError(f"whitelist {p} must be a YAML list of rules")

    rules: list[WhitelistRule] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            log.warning("Whitelist entry %d is not a mapping — skipped.", idx)
            continue
        name = str(entry.get("name") or f"rule-{idx}").strip()
        match = entry.get("match") or {}
        if not isinstance(match, dict) or not match:
            log.warning("Whitelist rule %r has no match block — skipped.", name)
            continue
        score_raw = entry.get("fp_score", 0.95)
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            log.warning("Whitelist rule %r has non-numeric fp_score — skipped.", name)
            continue
        score = max(0.0, min(1.0, score))
        ttl_days_raw = entry.get("ttl_days")
        ttl_days: int | None
        if ttl_days_raw in (None, "never", "infinite"):
            ttl_days = None
        else:
            try:
                ttl_days = int(ttl_days_raw)
            except (TypeError, ValueError):
                ttl_days = None
        rationale = entry.get("rationale") or entry.get("reason")
        rules.append(
            WhitelistRule(
                name=name,
                match=dict(match),
                fp_score=score,
                rationale=str(rationale) if rationale is not None else None,
                ttl_days=ttl_days,
            )
        )
    return rules


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def match_incident(rule: WhitelistRule, incident: dict[str, Any]) -> WhitelistMatch | None:
    """Return a :class:`WhitelistMatch` if every key in ``rule.match`` matches.

    Match value semantics:

    * scalar (str/int/bool) — equality after string-coercion
    * list — incident value must be (or contain) at least one element
    * ``"*"`` — any non-empty incident value matches
    * mapping — recursive (descends into nested incident fields)

    Match keys may be dotted (``source.ip``) and resolve in two places:

    * ``incident[<dotted key>]`` (for denormalised fields like
      ``technique_ids`` or ``sources``).
    * a flattened view of every member event in ``incident["members"]``.
    """
    matched_fields: list[str] = []
    for key, expected in rule.match.items():
        actual = _gather_values(incident, key)
        if not _value_matches(expected, actual):
            return None
        matched_fields.append(key)
    if not matched_fields:
        return None
    return WhitelistMatch(rule=rule, matched_fields=matched_fields)


def evaluate_whitelist(
    incident: dict[str, Any],
    rules: list[WhitelistRule],
) -> list[WhitelistMatch]:
    """Apply every rule to an incident and return all hits in order."""
    hits: list[WhitelistMatch] = []
    for rule in rules:
        hit = match_incident(rule, incident)
        if hit is not None:
            hits.append(hit)
    return hits


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _gather_values(incident: dict[str, Any], dotted_key: str) -> list[Any]:
    """Collect every value under ``dotted_key`` from the incident.

    Looks at:
    * the incident dict's denormalised top-level fields (``sources``,
      ``technique_ids``, ``severity``, ``summary``, etc.);
    * each member event under ``incident["members"]`` (treated as an
      ECS document and traversed by dotted path).
    """
    parts = dotted_key.split(".")
    out: list[Any] = []

    # 1) Direct lookup on the incident itself (top-level only).
    direct = incident.get(parts[0])
    if direct is not None and len(parts) == 1:
        if isinstance(direct, list):
            out.extend(direct)
        else:
            out.append(direct)

    # 2) Walk into members[*] following the dotted path.
    members = incident.get("members") or []
    if isinstance(members, list):
        for ev in members:
            if not isinstance(ev, dict):
                continue
            value = _walk(ev, parts)
            if value is None:
                continue
            if isinstance(value, list):
                out.extend(value)
            else:
                out.append(value)

    return out


def _walk(node: Any, parts: list[str]) -> Any:
    cur = node
    for key in parts:
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list):
            collected = []
            for item in cur:
                walked = _walk(item, [key])
                if walked is not None:
                    collected.append(walked)
            cur = collected or None
        else:
            return None
        if cur is None:
            return None
    return cur


def _value_matches(expected: Any, actual: list[Any]) -> bool:
    if expected == "*":
        return any(v not in (None, "", [], {}) for v in actual)
    if isinstance(expected, dict):
        # Nested matcher — flatten and AND.
        return all(
            _value_matches(sub_expected, _flatten_under(actual, sub_key))
            for sub_key, sub_expected in expected.items()
        )
    if isinstance(expected, list):
        wanted = {str(v) for v in expected}
        seen = {str(v) for v in actual}
        return bool(wanted.intersection(seen))
    wanted = str(expected)
    return any(str(v) == wanted for v in actual)


def _flatten_under(values: list[Any], key: str) -> list[Any]:
    out: list[Any] = []
    for v in values:
        if isinstance(v, dict):
            descended = v.get(key)
            if descended is None:
                continue
            if isinstance(descended, list):
                out.extend(descended)
            else:
                out.append(descended)
    return out
