"""Sliding-window grouping tests.

These exercise the deterministic core of the correlator without any
SIGMA, ATT&CK promotion, or threat-intel — the pipeline tests cover the
combinations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.grouping import group_events

from tests.conftest import event_burst, make_event


def test_single_ip_within_window_collapses_to_one_incident() -> None:
    events = event_burst(count=5, spacing_seconds=60)  # 5 events, 1 min apart
    incidents = group_events(events, window_seconds=900)
    assert len(incidents) == 1
    assert incidents[0].member_count == 5
    assert incidents[0].grouping_key == "src_ip:203.0.113.45"


def test_separate_ips_become_separate_incidents() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    events = [
        make_event(timestamp=base, source_ip="203.0.113.45"),
        make_event(timestamp=base + timedelta(seconds=1), source_ip="198.51.100.1"),
        make_event(timestamp=base + timedelta(seconds=2), source_ip="203.0.113.45"),
    ]
    incidents = group_events(events, window_seconds=900)
    assert len(incidents) == 2
    members_by_ip = {inc.grouping_key: inc.member_count for inc in incidents}
    assert members_by_ip["src_ip:203.0.113.45"] == 2
    assert members_by_ip["src_ip:198.51.100.1"] == 1


def test_window_break_starts_new_incident() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    events = [
        make_event(timestamp=base, source_ip="203.0.113.45"),
        make_event(timestamp=base + timedelta(seconds=120), source_ip="203.0.113.45"),
        # 30 minutes later — far outside the default 15-min window.
        make_event(timestamp=base + timedelta(minutes=30), source_ip="203.0.113.45"),
        make_event(timestamp=base + timedelta(minutes=30, seconds=30), source_ip="203.0.113.45"),
    ]
    incidents = group_events(events, window_seconds=900)
    assert len(incidents) == 2
    assert [inc.member_count for inc in incidents] == [2, 2]


def test_max_events_caps_one_bucket() -> None:
    events = event_burst(count=10, spacing_seconds=10)
    incidents = group_events(events, window_seconds=900, max_events_per_incident=4)
    # 10 events split by cap of 4 → 4, 4, 2.
    sizes = sorted([inc.member_count for inc in incidents], reverse=True)
    assert sizes == [4, 4, 2]


def test_event_without_source_ip_is_its_own_incident() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    events = [
        make_event(timestamp=base, source_ip="203.0.113.45"),
        make_event(timestamp=base + timedelta(seconds=10), source_ip=None),
        make_event(timestamp=base + timedelta(seconds=20), source_ip="203.0.113.45"),
    ]
    incidents = group_events(events, window_seconds=900)
    # Two for 203.0.113.45 (one bucket) + one orphan = 2 incidents.
    assert len(incidents) == 2
    assert any(inc.grouping_key.startswith("event_id:") for inc in incidents)


def test_severity_promotion_takes_max() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    events = [
        make_event(timestamp=base, severity=2),
        make_event(timestamp=base + timedelta(seconds=10), severity=6),
        make_event(timestamp=base + timedelta(seconds=20), severity=3),
    ]
    incidents = group_events(events, window_seconds=900)
    assert len(incidents) == 1
    assert incidents[0].severity == 6


def test_unsorted_input_is_sorted_internally() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    events = [
        make_event(timestamp=base + timedelta(seconds=20), source_ip="1.1.1.1"),
        make_event(timestamp=base, source_ip="1.1.1.1"),
        make_event(timestamp=base + timedelta(seconds=10), source_ip="1.1.1.1"),
    ]
    incidents = group_events(events, window_seconds=900)
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.first_event_at == base
    assert inc.last_event_at == base + timedelta(seconds=20)


def test_techniques_and_tactics_are_promoted_unique() -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    events = [
        make_event(
            timestamp=base,
            technique_ids=["T1110"],
            tactic_ids=["TA0006"],
        ),
        make_event(
            timestamp=base + timedelta(seconds=30),
            technique_ids=["T1110", "T1078"],
            tactic_ids=["TA0006"],
        ),
    ]
    incidents = group_events(events, window_seconds=900)
    assert len(incidents) == 1
    assert sorted(incidents[0].technique_ids) == ["T1078", "T1110"]
    assert incidents[0].tactic_ids == ["TA0006"]
