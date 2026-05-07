"""Tests for the L2 classifier trainer (``make retrain``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.fp.db import FeedbackDB
from app.fp.train import MIN_PER_CLASS, MIN_SAMPLES, run_training


def _seed_balanced_dataset(db: FeedbackDB, count_per_class: int = 8) -> None:
    for i in range(count_per_class):
        db.record_feedback(
            incident_id=f"fp-{i}",
            is_fp=True,
            features={"severity": 1.0, "member_count": 1.0, "source_count": 1.0},
        )
        db.record_feedback(
            incident_id=f"tp-{i}",
            is_fp=False,
            features={"severity": 6.0, "member_count": 4.0, "source_count": 3.0},
        )


def test_train_exits_when_below_min_samples(tmp_path: Path) -> None:
    db_path = tmp_path / "feedback.sqlite"
    db = FeedbackDB(path=db_path)
    db.record_feedback(incident_id="i", is_fp=True, features={"severity": 1.0})
    db.close()

    rc = run_training(
        db_path=str(db_path),
        model_path=str(tmp_path / "model.pkl"),
        report_path=str(tmp_path / "report.json"),
    )
    assert rc == 2
    assert not (tmp_path / "model.pkl").exists()


def test_train_exits_when_imbalanced(tmp_path: Path) -> None:
    db_path = tmp_path / "feedback.sqlite"
    db = FeedbackDB(path=db_path)
    for i in range(MIN_SAMPLES + 5):
        db.record_feedback(
            incident_id=f"only-fp-{i}",
            is_fp=True,
            features={"severity": 1.0},
        )
    db.close()
    rc = run_training(
        db_path=str(db_path),
        model_path=str(tmp_path / "model.pkl"),
        report_path=str(tmp_path / "report.json"),
    )
    assert rc == 3


def test_train_writes_model_when_balanced(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")
    db_path = tmp_path / "feedback.sqlite"
    db = FeedbackDB(path=db_path)
    _seed_balanced_dataset(db, count_per_class=MIN_PER_CLASS + 5)
    db.close()

    model_path = tmp_path / "model.pkl"
    report_path = tmp_path / "report.json"
    rc = run_training(
        db_path=str(db_path),
        model_path=str(model_path),
        report_path=str(report_path),
    )
    assert rc == 0
    assert model_path.exists()
    assert report_path.exists()
