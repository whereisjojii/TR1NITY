"""Unit tests for the in-process CockpitStore."""

from __future__ import annotations

import threading

import pytest
from app.store import CockpitStore, FPFeedback


def test_record_and_score_fp() -> None:
    store = CockpitStore()
    assert store.fp_score("inc-1") == pytest.approx(0.5)
    store.record_fp(FPFeedback(incident_id="inc-1", is_fp=True, reason="scanner"))
    assert store.fp_score("inc-1") == pytest.approx(1.0)
    store.record_fp(FPFeedback(incident_id="inc-1", is_fp=False))
    assert store.fp_score("inc-1") == pytest.approx(0.0)


def test_create_case_validates_title() -> None:
    store = CockpitStore()
    with pytest.raises(ValueError):
        store.create_case(title="   ")


def test_case_lifecycle() -> None:
    store = CockpitStore()
    case = store.create_case(title="SQLi from 203.0.113.10", severity=6, tags=["web"])
    assert case.severity == 6
    assert case.status == "open"

    fetched = store.get_case(case.case_id)
    assert fetched is not None
    assert fetched.title == case.title

    updated = store.update_case(case.case_id, status="containment", severity=7)
    assert updated is not None
    assert updated.status == "containment"
    assert updated.severity == 7

    listed = store.list_cases(status="containment")
    assert [c.case_id for c in listed] == [case.case_id]

    note_case = store.add_case_note(case.case_id, author="alice", body="contained")
    assert note_case is not None
    assert note_case.notes[-1]["author"] == "alice"

    assert store.delete_case(case.case_id) is True
    assert store.get_case(case.case_id) is None
    assert store.delete_case(case.case_id) is False


def test_case_status_validation() -> None:
    store = CockpitStore()
    with pytest.raises(ValueError):
        store.create_case(title="bad", status="not-a-status")  # type: ignore[arg-type]
    case = store.create_case(title="ok")
    with pytest.raises(ValueError):
        store.update_case(case.case_id, status="not-a-status")


def test_severity_clamped() -> None:
    store = CockpitStore()
    case = store.create_case(title="clamp", severity=42)
    assert case.severity == 7
    case2 = store.create_case(title="clamp2", severity=-1)
    assert case2.severity == 0


def test_remember_incidents_dedupes_by_id() -> None:
    store = CockpitStore()
    a = {"incident_id": "x1", "severity": 3}
    b = {"incident_id": "x1", "severity": 7}
    c = {"incident_id": "x2", "severity": 1}
    store.remember_incidents([a])
    store.remember_incidents([b, c])
    items = store.list_recent_incidents()
    assert len(items) == 2
    severities = {i["incident_id"]: i["severity"] for i in items}
    assert severities == {"x1": 7, "x2": 1}


def test_remember_incidents_skips_invalid() -> None:
    store = CockpitStore()
    store.remember_incidents([{"no_id": True}, {"incident_id": ""}, {"incident_id": "ok"}])
    assert [i["incident_id"] for i in store.list_recent_incidents()] == ["ok"]


def test_recent_buffer_capacity() -> None:
    store = CockpitStore(recent_incidents_capacity=3)
    for i in range(5):
        store.remember_incidents([{"incident_id": f"id-{i}"}])
    items = store.list_recent_incidents()
    assert [i["incident_id"] for i in items] == ["id-2", "id-3", "id-4"]


def test_thread_safe_records() -> None:
    store = CockpitStore()
    threads = [
        threading.Thread(
            target=lambda i=i: store.record_fp(FPFeedback(incident_id=f"i-{i}", is_fp=True))
        )
        for i in range(50)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(store.list_fp()) == 50
