"""Composite FP scoring — max-of-layers with full provenance.

The Cockpit shows ``fp_score`` and ``fp_layers`` for every incident.
``fp_score`` is the maximum of every layer that fired; ``fp_layers`` is
the explainable list of every contributor so the analyst can see *why*
an incident was scored the way it was. The fp-handling design doc
mandates this max-of-layers semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .classifier import FPClassifier
from .suppressions import SuppressionRule, evaluate_suppressions
from .whitelist import WhitelistRule, evaluate_whitelist

LayerName = Literal["L1", "L2", "L3", "analyst"]


@dataclass(slots=True)
class LayerHit:
    """One layer's contribution to the composite score."""

    layer: LayerName
    score: float
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "score": self.score,
            "detail": dict(self.detail),
        }


@dataclass(slots=True)
class ScoreBreakdown:
    """The decoration the api attaches to every served incident."""

    fp_score: float
    layers: list[LayerHit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fp_score": self.fp_score,
            "fp_layers": [layer.to_dict() for layer in self.layers],
        }


def compose_fp_score(
    incident: dict[str, Any],
    *,
    whitelist_rules: list[WhitelistRule] | None = None,
    suppression_rules: list[SuppressionRule] | None = None,
    classifier: FPClassifier | None = None,
    analyst_score: float | None = None,
) -> ScoreBreakdown:
    """Compute the composite ``fp_score`` for one incident.

    All four inputs are optional:

    * ``whitelist_rules`` — Layer 1 (YAML).
    * ``suppression_rules`` — Layer 3 (analyst-authored).
    * ``classifier`` — Layer 2 (lazy-loading sklearn wrapper).
    * ``analyst_score`` — explicit "Mark FP / Mark TP" override.

    Layers that don't fire contribute nothing to ``fp_layers`` so the
    UI surface stays compact. Each fired layer is rendered with its own
    explanation block.
    """
    layers: list[LayerHit] = []
    best = 0.0

    if whitelist_rules:
        for hit in evaluate_whitelist(incident, whitelist_rules):
            layers.append(LayerHit(layer="L1", score=hit.rule.fp_score, detail=hit.to_dict()))
            best = max(best, hit.rule.fp_score)

    if suppression_rules:
        for hit in evaluate_suppressions(incident, suppression_rules):
            layers.append(LayerHit(layer="L3", score=hit.rule.fp_score, detail=hit.to_dict()))
            best = max(best, hit.rule.fp_score)

    if classifier is not None and classifier.available:
        ml_score = classifier.predict_fp_probability(incident)
        if ml_score > 0:
            layers.append(
                LayerHit(
                    layer="L2",
                    score=ml_score,
                    detail={"model": "sklearn"},
                )
            )
            best = max(best, ml_score)

    if analyst_score is not None:
        layers.append(
            LayerHit(
                layer="analyst",
                score=float(analyst_score),
                detail={"source": "Mark FP/TP"},
            )
        )
        best = max(best, float(analyst_score))

    if not layers:
        # Neutral score when no signals exist — keeps sort-by-fp_score
        # stable and matches Phase-3 behaviour.
        return ScoreBreakdown(fp_score=0.5, layers=[])

    return ScoreBreakdown(fp_score=best, layers=layers)
