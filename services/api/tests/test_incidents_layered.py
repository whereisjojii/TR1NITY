"""Phase-4 integration tests — composite scoring through the queue route."""

from __future__ import annotations

from typing import Any

from app.fp.suppressions import SuppressionRule
from app.fp.whitelist import WhitelistRule
from app.incidents import compose_incidents
from app.runbooks import RunbookLibrary
from app.store import CockpitStore


def _incident(incident_id: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "incident_id": incident_id,
        "summary": "Synthetic chain",
        "severity": 6,
        "sources": ["firewall", "wazuh"],
        "technique_ids": ["T1110.001"],
        "members": [{"source": {"ip": "203.0.113.45"}}],
        "created_at": "2024-01-01T00:00:00Z",
        "last_event_at": "2024-01-01T00:30:00Z",
    }
    base.update(overrides)
    return base


def test_compose_attaches_layered_score_when_whitelist_matches(tmp_path) -> None:
    rules = [WhitelistRule(name="r", match={"sources": ["firewall"]}, fp_score=0.9)]
    store = CockpitStore()
    items = compose_incidents(
        correlator_items=[_incident("i-1")],
        cached_items=None,
        opensearch_items=None,
        store=store,
        whitelist=rules,
    )
    assert len(items) == 1
    inc = items[0]
    assert inc["fp_score"] == 0.9
    layers = [layer["layer"] for layer in inc["fp_layers"]]
    assert "L1" in layers


def test_compose_attaches_runbook_url_for_known_technique(tmp_path) -> None:
    from pathlib import Path

    library = RunbookLibrary(
        runbooks_dir=Path(__file__).resolve().parents[2].parent / "docs" / "runbooks"
    )
    items = compose_incidents(
        correlator_items=[_incident("i-1", technique_ids=["T1190"])],
        cached_items=None,
        opensearch_items=None,
        store=CockpitStore(),
        runbook_library=library,
    )
    assert items[0]["runbook_url"] == "/api/runbooks/T1190"


def test_phase3_behaviour_when_no_layers_passed() -> None:
    store = CockpitStore()
    items = compose_incidents(
        correlator_items=[_incident("i-1")],
        cached_items=None,
        opensearch_items=None,
        store=store,
    )
    inc = items[0]
    # Phase-3 store-only fallback gives the neutral 0.5 score.
    assert inc["fp_score"] == 0.5
    assert inc["fp_layers"] == []


def test_suppression_overrides_when_higher_than_layer1() -> None:
    rules = [WhitelistRule(name="r1", match={"sources": ["firewall"]}, fp_score=0.5)]
    from datetime import UTC, datetime, timedelta

    suppression = SuppressionRule(
        suppression_id="s1",
        name="manual",
        match={"sources": ["firewall"]},
        fp_score=0.95,
        ttl_days=7,
        author="alice",
        reason="approved",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    items = compose_incidents(
        correlator_items=[_incident("i-1")],
        cached_items=None,
        opensearch_items=None,
        store=CockpitStore(),
        whitelist=rules,
        suppressions=[suppression],
    )
    inc = items[0]
    assert inc["fp_score"] == 0.95
