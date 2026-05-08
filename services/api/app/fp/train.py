"""``make retrain`` entrypoint — Layer-2 model trainer.

Reads ``fp_feedback`` rows from the SQLite feedback DB, builds a
feature matrix with :func:`app.fp.features.vectorize`, fits a small
``LogisticRegression`` classifier, and writes the model to disk so the
runtime scorer can pick it up.

If the analyst hasn't recorded enough labelled examples yet, the
trainer logs a friendly message and exits non-zero so the Makefile
target surfaces the gap to the operator.

Run via:

    python -m app.fp.train --db services/api/data/feedback.sqlite \
                            --model services/api/data/fp_classifier.pkl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from .db import FeedbackDB, FeedbackRow
from .features import FEATURE_NAMES, vectorize

log = logging.getLogger("app.fp.train")

DEFAULT_DB = "services/api/data/feedback.sqlite"
DEFAULT_MODEL = "services/api/data/fp_classifier.pkl"
DEFAULT_REPORT = "services/api/data/fp_classifier_report.json"
MIN_SAMPLES = 10
MIN_PER_CLASS = 3


def run_training(
    *,
    db_path: str = DEFAULT_DB,
    model_path: str = DEFAULT_MODEL,
    report_path: str = DEFAULT_REPORT,
) -> int:
    """Fit a model and write it to ``model_path``.

    Returns 0 on success, non-zero on any failure (insufficient data,
    sklearn missing, write error). The non-zero exits feed the
    Makefile target so CI reports them.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    db = FeedbackDB(path=db_path)
    rows = db.list_feedback()
    if len(rows) < MIN_SAMPLES:
        log.warning(
            "Not enough analyst feedback yet — have %d, need %d. "
            "Mark a few more incidents and try again.",
            len(rows),
            MIN_SAMPLES,
        )
        return 2

    features, labels = _build_dataset(rows)
    counts = Counter(labels)
    if any(counts.get(label, 0) < MIN_PER_CLASS for label in (0, 1)):
        log.warning(
            "Imbalanced training set — need ≥%d FP and ≥%d TP examples. " "Got: FP=%d, TP=%d.",
            MIN_PER_CLASS,
            MIN_PER_CLASS,
            counts.get(1, 0),
            counts.get(0, 0),
        )
        return 3

    try:
        from sklearn.linear_model import LogisticRegression  # type: ignore[import-not-found]
        from sklearn.metrics import accuracy_score  # type: ignore[import-not-found]
        from sklearn.model_selection import train_test_split  # type: ignore[import-not-found]
    except ImportError as exc:
        log.error(
            "scikit-learn is not installed — `pip install scikit-learn joblib` "
            "in services/api before running `make retrain`. Underlying: %s",
            exc,
        )
        return 4

    try:
        import joblib  # type: ignore[import-not-found]
    except ImportError as exc:
        log.error("joblib missing: %s", exc)
        return 4

    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=42, stratify=labels
    )
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(x_train, y_train)
    accuracy = float(accuracy_score(y_test, model.predict(x_test)))

    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    report = {
        "samples_total": len(rows),
        "samples_train": len(x_train),
        "samples_test": len(x_test),
        "samples_fp": counts.get(1, 0),
        "samples_tp": counts.get(0, 0),
        "feature_names": list(FEATURE_NAMES),
        "test_accuracy": accuracy,
        "model_path": model_path,
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info(
        "Model trained on %d samples (FP=%d / TP=%d). " "Held-out accuracy %.3f. Wrote model to %s",
        len(rows),
        counts.get(1, 0),
        counts.get(0, 0),
        accuracy,
        model_path,
    )
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_dataset(
    rows: list[FeedbackRow],
) -> tuple[list[list[float]], list[int]]:
    feature_matrix: list[list[float]] = []
    labels: list[int] = []
    for row in rows:
        features = row.features
        if not isinstance(features, dict) or not features:
            # Skip rows that pre-date the Phase-4 feature snapshot.
            continue
        feature_matrix.append(vectorize(features))
        labels.append(1 if row.is_fp else 0)
    return feature_matrix, labels


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the TR1NITY Layer-2 FP classifier.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to feedback SQLite DB")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Output model path")
    parser.add_argument(
        "--report",
        default=DEFAULT_REPORT,
        help="Path for the training report JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    return run_training(
        db_path=args.db,
        model_path=args.model,
        report_path=args.report,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
