"""Layer 2 — sklearn-trained FP classifier (with deterministic fallback).

Loads ``services/api/data/fp_classifier.pkl`` (or whatever path is set
in ``TR1NITY_API_FP_MODEL_PATH``) at first use; if either the file or
the ``scikit-learn`` package itself is missing the layer politely
returns 0.0 so the composite scorer ignores it. ``make retrain`` calls
:func:`app.fp.train.run_training` to produce the model.

The classifier is **never** the only signal — it sits between Layer 1
(operator certainty) and Layer 3 (analyst override). Its output is the
predicted probability that an incident is a false positive.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .features import FEATURE_NAMES, extract_features, vectorize

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ClassifierStatus:
    """Diagnostics surfaced via ``GET /api/fp/status`` (Phase 4)."""

    available: bool
    reason: str
    model_path: str | None = None
    feature_names: tuple[str, ...] = FEATURE_NAMES
    sklearn_version: str | None = None


class FPClassifier:
    """Lazy-loading wrapper around the optional sklearn model."""

    def __init__(self, *, model_path: str | Path | None) -> None:
        self._model_path = Path(model_path) if model_path else None
        self._model: Any = None
        self._loaded = False
        self._load_error: str | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        with self._lock:
            self._ensure_loaded()
            return self._model is not None

    def status(self) -> ClassifierStatus:
        with self._lock:
            self._ensure_loaded()
            sklearn_version: str | None
            try:
                import sklearn  # type: ignore[import-not-found]

                sklearn_version = getattr(sklearn, "__version__", None)
            except ImportError:
                sklearn_version = None
            reason = (
                "ok" if self._model is not None else (self._load_error or "no model trained yet")
            )
            return ClassifierStatus(
                available=self._model is not None,
                reason=reason,
                model_path=str(self._model_path) if self._model_path else None,
                sklearn_version=sklearn_version,
            )

    def predict_fp_probability(self, incident: dict[str, Any]) -> float:
        """Return the predicted FP probability in [0, 1].

        Falls back to 0.0 (no contribution) when the model isn't
        available — the composite scorer always has Layers 1, 3 and the
        analyst's explicit feedback to fall back on.
        """
        with self._lock:
            self._ensure_loaded()
            if self._model is None:
                return 0.0
            features = vectorize(extract_features(incident))
            try:
                proba = self._model.predict_proba([features])[0]
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("FPClassifier.predict_fp_probability failed: %s", exc)
                return 0.0
            # The classifier is trained with class label 1 == FP, 0 == TP.
            try:
                idx_fp = list(self._model.classes_).index(1)
            except ValueError:
                return float(proba[-1])
            return float(proba[idx_fp])

    def reload(self) -> None:
        with self._lock:
            self._loaded = False
            self._model = None
            self._load_error = None
            self._ensure_loaded()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self._model_path is None or not self._model_path.exists():
            self._load_error = "no model file found — run `make retrain` after collecting feedback."
            return
        try:
            import joblib  # type: ignore[import-not-found]
        except ImportError as exc:
            self._load_error = f"joblib not installed: {exc}"
            log.info(
                "FPClassifier: joblib not installed — Layer 2 disabled. "
                "Install scikit-learn or skip ML scoring."
            )
            return
        try:
            self._model = joblib.load(self._model_path)
        except Exception as exc:
            self._load_error = f"failed to load model {self._model_path}: {exc}"
            log.warning("FPClassifier: %s", self._load_error)
            self._model = None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


_singleton: FPClassifier | None = None
_singleton_lock = threading.Lock()


def get_classifier(model_path: str | Path | None = None) -> FPClassifier:
    """Return the process-wide classifier singleton."""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = FPClassifier(model_path=model_path)
        return _singleton


def replace_classifier(classifier: FPClassifier) -> None:
    """Test hook — swap the singleton."""
    global _singleton
    with _singleton_lock:
        _singleton = classifier
