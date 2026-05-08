"""Tests for the composite FP scorer (max of layers)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.fp.classifier import FPClassifier
from app.fp.scorer import compose_fp_score
from app.fp.suppressions import SuppressionRule
from app.fp.whitelist import WhitelistRule


class _FakeAvailableClassifier(FPClassifier):
    """Classifier double — pretends to have a model and emits a fixed probability."""

    def __init__(self, score: float) -> None:
        super().__init__(model_path=None)
        self._fixed = score

    @property
    def available(self) -> bool:  # type: ignore[override]
        return True

    def predict_fp_probability(self, incident: dict) -> float:  # type: ignore[override]
        return self._fixed


def test_no_layers_gives_neutral_score() -> None:
    breakdown = compose_fp_score({"incident_id": "i"})
    assert breakdown.fp_score == 0.5
    assert breakdown.layers == []


def test_layer1_only() -> None:
    rules = [WhitelistRule(name="rule", match={"sources": ["firewall"]}, fp_score=0.9)]
    incident = {"incident_id": "i", "sources": ["firewall"]}
    breakdown = compose_fp_score(incident, whitelist_rules=rules)
    assert breakdown.fp_score == 0.9
    assert [layer.layer for layer in breakdown.layers] == ["L1"]


def test_layer3_overrides_layer1_when_higher() -> None:
    rules = [WhitelistRule(name="r1", match={"sources": ["firewall"]}, fp_score=0.5)]
    suppression = SuppressionRule(
        suppression_id="s1",
        name="manual",
        match={"sources": ["firewall"]},
        fp_score=0.95,
        ttl_days=30,
        author="alice",
        reason="approved",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    incident = {"incident_id": "i", "sources": ["firewall"]}
    breakdown = compose_fp_score(
        incident,
        whitelist_rules=rules,
        suppression_rules=[suppression],
    )
    assert breakdown.fp_score == 0.95
    layers = {layer.layer for layer in breakdown.layers}
    assert {"L1", "L3"}.issubset(layers)


def test_layer2_classifier_contributes_when_available() -> None:
    incident = {"incident_id": "i", "sources": ["wazuh"]}
    breakdown = compose_fp_score(incident, classifier=_FakeAvailableClassifier(0.7))
    assert breakdown.fp_score == 0.7
    assert [layer.layer for layer in breakdown.layers] == ["L2"]


def test_analyst_score_dominates_when_explicit() -> None:
    rules = [WhitelistRule(name="r", match={"sources": ["firewall"]}, fp_score=0.5)]
    incident = {"incident_id": "i", "sources": ["firewall"]}
    breakdown = compose_fp_score(
        incident,
        whitelist_rules=rules,
        analyst_score=1.0,
    )
    assert breakdown.fp_score == 1.0
    layers = [layer.layer for layer in breakdown.layers]
    assert "analyst" in layers


def test_expired_suppression_is_ignored() -> None:
    suppression = SuppressionRule(
        suppression_id="s1",
        name="manual",
        match={"sources": ["firewall"]},
        fp_score=0.95,
        ttl_days=1,
        author="alice",
        reason=None,
        created_at=datetime.now(UTC) - timedelta(days=10),
        expires_at=datetime.now(UTC) - timedelta(days=5),
    )
    incident = {"incident_id": "i", "sources": ["firewall"]}
    breakdown = compose_fp_score(incident, suppression_rules=[suppression])
    assert breakdown.fp_score == 0.5
    assert breakdown.layers == []
