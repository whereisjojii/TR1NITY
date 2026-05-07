"""Phase 4 — False-positive (FP) handling.

Three independent layers feed a single composite ``fp_score`` for every
incident the api serves to the Cockpit:

* **Layer 1** — operator-authored YAML whitelist (deterministic).
* **Layer 2** — sklearn classifier trained on analyst "Mark FP" clicks
  (probabilistic; deterministic fallback when no model is present).
* **Layer 3** — analyst-authored suppression rules with TTL (auditable).

The composite score is ``max(L1, L2, L3, analyst_explicit_feedback)``;
each layer's contribution is exposed verbatim in ``fp_layers`` so the
Cockpit can show *why* a score was assigned. The fp-handling design doc
(``docs/modules/fp-handling.md``) is the source of truth for this
module's contract.
"""

from __future__ import annotations

from .db import FeedbackDB, get_feedback_db, replace_feedback_db
from .scorer import LayerHit, ScoreBreakdown, compose_fp_score
from .suppressions import SuppressionRule

__all__ = [
    "FeedbackDB",
    "LayerHit",
    "ScoreBreakdown",
    "SuppressionRule",
    "compose_fp_score",
    "get_feedback_db",
    "replace_feedback_db",
]
