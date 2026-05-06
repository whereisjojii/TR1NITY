"""Unit tests for the incident composition / heatmap / similarity helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.incidents import compose_incidents, compute_attack_heatmap, rank_similar
from app.store import CockpitStore, FPFeedback

from .fixtures.incidents import incident


def _store_with_fp(fp: dict[str, bool]) -> CockpitStore:
    store = CockpitStore()
    for inc_id, is_fp in fp.items():
        store.record_fp(FPFeedback(incident_id=inc_id, is_fp=is_fp))
    return store


def test_compose_dedupes_across_sources() -> None:
    a = incident(incident_id="a")
    b = incident(incident_id="b")
    out = compose_incidents(
        correlator_items=[a],
        cached_items=[a, b],
        opensearch_items=[b],
        store=CockpitStore(),
    )
    assert {inc["incident_id"] for inc in out} == {"a", "b"}


def test_compose_sorts_by_fp_score_ascending() -> None:
    store = _store_with_fp({"a": False, "b": True})
    out = compose_incidents(
        correlator_items=[incident(incident_id="a"), incident(incident_id="b")],
        cached_items=None,
        opensearch_items=None,
        store=store,
    )
    assert [inc["incident_id"] for inc in out] == ["a", "b"]
    assert out[0]["fp_score"] == pytest.approx(0.0)
    assert out[1]["fp_score"] == pytest.approx(1.0)


def test_compose_severity_filter() -> None:
    out = compose_incidents(
        correlator_items=[
            incident(incident_id="low", severity=2),
            incident(incident_id="high", severity=6),
        ],
        cached_items=None,
        opensearch_items=None,
        store=CockpitStore(),
        severity_min=5,
    )
    assert [inc["incident_id"] for inc in out] == ["high"]


def test_compose_source_and_technique_filter() -> None:
    items = [
        incident(incident_id="wazuh-only", sources=["wazuh"], technique_ids=["T1110"]),
        incident(incident_id="waf-only", sources=["waf"], technique_ids=["T1190"]),
        incident(
            incident_id="multi", sources=["wazuh", "firewall"], technique_ids=["T1190", "T1110"]
        ),
    ]
    by_source = compose_incidents(
        correlator_items=items,
        cached_items=None,
        opensearch_items=None,
        store=CockpitStore(),
        sources=["waf"],
    )
    assert {i["incident_id"] for i in by_source} == {"waf-only"}

    by_technique = compose_incidents(
        correlator_items=items,
        cached_items=None,
        opensearch_items=None,
        store=CockpitStore(),
        technique="T1190",
    )
    assert {i["incident_id"] for i in by_technique} == {"waf-only", "multi"}


def test_compose_limit_applied_after_sort() -> None:
    items = [incident(incident_id=f"i-{n}", severity=n) for n in range(7)]
    out = compose_incidents(
        correlator_items=items,
        cached_items=None,
        opensearch_items=None,
        store=CockpitStore(),
        sort_by="severity",
        descending=True,
        limit=3,
    )
    assert [i["incident_id"] for i in out] == ["i-6", "i-5", "i-4"]


def test_compose_sort_by_created_at_descending() -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    items = [
        incident(incident_id="old", created_at=base),
        incident(incident_id="new", created_at=base + timedelta(hours=2)),
    ]
    out = compose_incidents(
        correlator_items=items,
        cached_items=None,
        opensearch_items=None,
        store=CockpitStore(),
        sort_by="created_at",
        descending=True,
    )
    assert [i["incident_id"] for i in out] == ["new", "old"]


def test_compute_attack_heatmap_aggregates_techniques_and_tactics() -> None:
    incidents = [
        incident(
            incident_id="a", technique_ids=["T1190", "T1110"], tactic_ids=["TA0001", "TA0006"]
        ),
        incident(incident_id="b", technique_ids=["T1190"], tactic_ids=["TA0001"]),
        incident(incident_id="c", technique_ids=[], tactic_ids=[]),
    ]
    summary = compute_attack_heatmap(incidents)
    technique_counts = {t["id"]: t["count"] for t in summary["techniques"]}
    assert technique_counts == {"T1190": 2, "T1110": 1}
    tactic_counts = {t["id"]: t["count"] for t in summary["tactics"]}
    assert tactic_counts == {"TA0001": 2, "TA0006": 1}
    assert summary["total_incidents"] == 3
    assert summary["covered_incidents"] == 2


def test_rank_similar_returns_relevant_pool() -> None:
    target = incident(
        incident_id="t",
        source_ip="203.0.113.10",
        technique_ids=["T1190"],
        sources=["waf"],
    )
    matches = [
        incident(
            incident_id="same-ip",
            source_ip="203.0.113.10",
            technique_ids=["T1078"],
            sources=["wazuh"],
        ),
        incident(
            incident_id="same-tech",
            source_ip="198.51.100.7",
            technique_ids=["T1190"],
            sources=["waf"],
        ),
        incident(
            incident_id="unrelated",
            source_ip="198.51.100.99",
            technique_ids=["T1486"],
            sources=["wazuh"],
        ),
    ]
    out = rank_similar(target, matches, limit=10)
    ids = [r["incident_id"] for r in out]
    assert "unrelated" not in ids
    assert "same-ip" in ids
    assert "same-tech" in ids
    # Same-IP scoring is heavier than same-technique.
    assert ids[0] == "same-ip"
    assert all("similarity_score" in r for r in out)


def test_rank_similar_excludes_self_and_respects_limit() -> None:
    target = incident(
        incident_id="t",
        source_ip="203.0.113.10",
        technique_ids=["T1190"],
        sources=["waf"],
    )
    pool = [target] + [
        incident(
            incident_id=f"m-{i}",
            source_ip="203.0.113.10",
            technique_ids=["T1190"],
            sources=["waf"],
        )
        for i in range(5)
    ]
    out = rank_similar(target, pool, limit=2)
    assert len(out) == 2
    assert all(r["incident_id"] != "t" for r in out)
