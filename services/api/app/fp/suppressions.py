"""Layer 3 — analyst-authored suppression rules with TTL.

Where Layer 1 is operator territory (security engineers committing YAML
to git), Layer 3 is the analyst's own escape hatch: the Cockpit's
"Suppress this for 30 days" button writes a row here. The rules are
loaded on every incident-listing request, so changes take effect
immediately without a deploy.

Each rule has the same matching semantics as Layer 1
(:func:`app.fp.whitelist.match_incident`); the rules are stored in the
SQLite feedback DB (:mod:`app.fp.db`) rather than YAML so they can be
written from the UI and audited per-author.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .whitelist import WhitelistRule, evaluate_whitelist

log = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SuppressionRule:
    """Persisted analyst-authored suppression."""

    suppression_id: str
    name: str
    match: dict[str, Any]
    fp_score: float
    ttl_days: int | None
    author: str
    reason: str | None
    created_at: datetime
    expires_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> SuppressionRule:
        return cls(
            suppression_id=row["suppression_id"],
            name=row["name"],
            match=dict(row.get("match") or {}),
            fp_score=float(row.get("fp_score", 0.0)),
            ttl_days=int(row["ttl_days"]) if row.get("ttl_days") is not None else None,
            author=row.get("author") or "anonymous",
            reason=row.get("reason"),
            created_at=_parse_iso(row["created_at"]),
            expires_at=_parse_iso(row["expires_at"]) if row.get("expires_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suppression_id": self.suppression_id,
            "name": self.name,
            "match": dict(self.match),
            "fp_score": self.fp_score,
            "ttl_days": self.ttl_days,
            "author": self.author,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def to_whitelist_rule(self) -> WhitelistRule:
        """Reuse Layer-1's matcher by adapting the suppression."""
        return WhitelistRule(
            name=self.name,
            match=dict(self.match),
            fp_score=self.fp_score,
            rationale=self.reason,
            ttl_days=self.ttl_days,
        )


@dataclass(slots=True)
class SuppressionMatch:
    """One suppression rule that hit a given incident."""

    rule: SuppressionRule
    matched_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suppression_id": self.rule.suppression_id,
            "name": self.rule.name,
            "score": self.rule.fp_score,
            "matched_fields": list(self.matched_fields),
            "author": self.rule.author,
            "expires_at": (self.rule.expires_at.isoformat() if self.rule.expires_at else None),
        }


def evaluate_suppressions(
    incident: dict[str, Any],
    rules: list[SuppressionRule],
    *,
    now: datetime | None = None,
) -> list[SuppressionMatch]:
    """Return every active suppression rule that matches an incident."""
    cutoff = now or datetime.now(UTC)
    hits: list[SuppressionMatch] = []
    for rule in rules:
        if rule.expires_at is not None and rule.expires_at <= cutoff:
            continue
        wl_rule = rule.to_whitelist_rule()
        wl_hits = evaluate_whitelist(incident, [wl_rule])
        if not wl_hits:
            continue
        hits.append(
            SuppressionMatch(
                rule=rule,
                matched_fields=list(wl_hits[0].matched_fields),
            )
        )
    return hits


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
