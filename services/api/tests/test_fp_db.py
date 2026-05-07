"""Tests for the SQLite-backed feedback DB (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.fp.db import FeedbackDB


def test_record_feedback_round_trip() -> None:
    db = FeedbackDB()
    row = db.record_feedback(
        incident_id="inc-1",
        is_fp=True,
        reason="known scanner",
        submitted_by="alice",
        features={"severity": 4.0, "member_count": 3.0},
    )
    assert row.feedback_id
    assert row.incident_id == "inc-1"
    assert row.is_fp is True
    assert row.features == {"severity": 4.0, "member_count": 3.0}

    listed = db.list_feedback()
    assert [r.feedback_id for r in listed] == [row.feedback_id]
    assert db.feedback_count() == 1


def test_latest_feedback_is_most_recent() -> None:
    db = FeedbackDB()
    db.record_feedback(
        incident_id="inc-1", is_fp=True, submitted_at=datetime(2024, 1, 1, tzinfo=UTC)
    )
    second = db.record_feedback(
        incident_id="inc-1",
        is_fp=False,
        submitted_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    latest = db.latest_feedback("inc-1")
    assert latest is not None
    assert latest.feedback_id == second.feedback_id
    assert latest.is_fp is False


def test_suppression_round_trip_and_expiry() -> None:
    db = FeedbackDB()
    created = db.insert_suppression(
        name="scanner-noise",
        match={"sources": ["firewall"], "source.ip": "10.10.99.10"},
        fp_score=0.95,
        ttl_days=7,
        author="alice",
        reason="approved scanner",
    )
    sid = created["suppression_id"]
    assert db.get_suppression(sid) is not None

    listed_active = db.list_suppressions()
    assert [r["suppression_id"] for r in listed_active] == [sid]

    # Pretend we are well past the expiry window.
    far_future = datetime.now(UTC) + timedelta(days=30)
    listed_after_expiry = db.list_suppressions(now=far_future)
    assert listed_after_expiry == []

    # ``include_expired`` returns expired rows verbatim.
    listed_with_expired = db.list_suppressions(include_expired=True)
    assert len(listed_with_expired) == 1


def test_prune_expired_drops_only_expired_rows() -> None:
    db = FeedbackDB()
    permanent = db.insert_suppression(
        name="permanent",
        match={"sources": ["firewall"]},
        fp_score=0.5,
        ttl_days=None,
    )
    short = db.insert_suppression(
        name="short",
        match={"sources": ["wazuh"]},
        fp_score=0.5,
        ttl_days=1,
    )
    # Force the expiry past today.
    far_future = datetime.now(UTC) + timedelta(days=2)
    pruned = db.prune_expired(now=far_future)
    assert pruned == 1
    remaining = {r["suppression_id"] for r in db.list_suppressions(include_expired=True)}
    assert remaining == {permanent["suppression_id"]}
    assert short["suppression_id"] not in remaining


def test_delete_suppression_returns_false_when_unknown() -> None:
    db = FeedbackDB()
    assert db.delete_suppression("nope") is False
    row = db.insert_suppression(
        name="x",
        match={"sources": ["x"]},
        fp_score=0.5,
        ttl_days=None,
    )
    assert db.delete_suppression(row["suppression_id"]) is True
    assert db.get_suppression(row["suppression_id"]) is None
