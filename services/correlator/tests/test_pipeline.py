"""End-to-end pipeline tests.

These wire the consumer, SIGMA engine, intel cache, and sinks together
the way the running service does, then verify the incidents look right.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.consumer import InMemoryEventConsumer
from app.intel import FileProvider
from app.pipeline import CorrelatorPipeline
from app.sigma import SigmaEngine, load_rules_from_dir
from app.sinks import StdoutIncidentSink

from tests.conftest import make_event


def _bundled_sigma() -> SigmaEngine:
    rules_dir = Path(__file__).resolve().parents[1] / "app" / "sigma" / "rules"
    return SigmaEngine(rules=load_rules_from_dir(rules_dir))


def _bundled_intel() -> FileProvider:
    ioc = Path(__file__).resolve().parents[1] / "app" / "intel" / "data" / "ioc.json"
    return FileProvider.from_file(ioc)


def test_pipeline_groups_events_into_one_incident() -> None:
    consumer = InMemoryEventConsumer()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    consumer.push(
        [
            make_event(source="firewall", timestamp=base, event_action="block"),
            make_event(
                source="waf",
                timestamp=base + timedelta(seconds=60),
                message="UNION SELECT users",
            ),
            make_event(
                source="wazuh",
                timestamp=base + timedelta(seconds=120),
                rule_id="5503",
                rule_category="authentication_failures",
            ),
        ]
    )
    pipeline = CorrelatorPipeline.assemble(
        consumer=consumer,
        sinks=[StdoutIncidentSink(stream=io.StringIO())],
        sigma_engine=_bundled_sigma(),
        intel_providers=[_bundled_intel()],
    )

    pipeline.tick()
    assert len(pipeline.last_incidents) == 1
    incident = pipeline.last_incidents[0]
    assert incident.member_count == 3
    assert sorted(incident.sources) == ["firewall", "waf", "wazuh"]


def test_pipeline_promotes_attack_chain_via_sigma() -> None:
    consumer = InMemoryEventConsumer()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    consumer.push(
        [
            make_event(source="firewall", timestamp=base, event_action="deny"),
            make_event(
                source="waf",
                timestamp=base + timedelta(seconds=60),
                message="malicious UNION SELECT",
            ),
            make_event(
                source="wazuh",
                timestamp=base + timedelta(seconds=120),
                rule_id="5503",
                rule_category="authentication_failures",
            ),
        ]
    )
    pipeline = CorrelatorPipeline.assemble(
        consumer=consumer,
        sinks=[StdoutIncidentSink(stream=io.StringIO())],
        sigma_engine=_bundled_sigma(),
    )

    pipeline.tick()
    inc = pipeline.last_incidents[0]
    # Tactics should at least include Recon, Initial Access, and Credential Access,
    # in canonical kill-chain order. (Other rule tags may legitimately add more.)
    for tac in ("TA0043", "TA0001", "TA0006"):
        assert tac in inc.tactic_ids
    rank = {t: i for i, t in enumerate(["TA0043", "TA0001", "TA0006"])}
    seen = [tac for tac in inc.tactic_ids if tac in rank]
    assert seen == ["TA0043", "TA0001", "TA0006"]
    assert "T1595" in inc.technique_ids  # firewall portscan
    assert "T1190" in inc.technique_ids  # WAF SQLi
    assert "T1110" in inc.technique_ids  # Wazuh brute force
    assert inc.summary is not None
    assert "ATT&CK chain" in inc.summary
    assert inc.severity >= 6  # promoted by SIGMA "high" levels


def test_pipeline_attaches_intel_hits() -> None:
    consumer = InMemoryEventConsumer()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    consumer.push(
        [
            make_event(source="firewall", timestamp=base, event_action="block"),
            make_event(
                source="firewall",
                timestamp=base + timedelta(seconds=10),
                event_action="block",
            ),
        ]
    )
    pipeline = CorrelatorPipeline.assemble(
        consumer=consumer,
        sinks=[StdoutIncidentSink(stream=io.StringIO())],
        intel_providers=[_bundled_intel()],
    )
    pipeline.tick()
    inc = pipeline.last_incidents[0]
    assert len(inc.intel_hits) == 1
    assert inc.intel_hits[0]["indicator"] == "203.0.113.45"
    assert inc.intel_hits[0]["feed"] == "tr1nity-bundled"


def test_pipeline_emits_to_stdout_sink() -> None:
    consumer = InMemoryEventConsumer()
    consumer.push([make_event(source="firewall", event_action="block")])
    buf = io.StringIO()
    pipeline = CorrelatorPipeline.assemble(
        consumer=consumer,
        sinks=[StdoutIncidentSink(stream=buf)],
    )
    results = pipeline.tick()
    assert results[0].accepted == 1
    lines = [line for line in buf.getvalue().splitlines() if line]
    assert len(lines) == 1
    doc = json.loads(lines[0])
    assert doc["grouping_key"].startswith("src_ip:")


def test_pipeline_tick_with_no_events_is_a_no_op() -> None:
    consumer = InMemoryEventConsumer()
    pipeline = CorrelatorPipeline.assemble(
        consumer=consumer,
        sinks=[StdoutIncidentSink(stream=io.StringIO())],
    )
    results = pipeline.tick()
    assert pipeline.last_incidents == []
    assert results[0].accepted == 0
    assert results[0].rejected == 0


def test_two_separate_ips_yield_two_incidents() -> None:
    consumer = InMemoryEventConsumer()
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    consumer.push(
        [
            make_event(source_ip="203.0.113.45", timestamp=base, event_action="block"),
            make_event(
                source_ip="198.51.100.1",
                timestamp=base + timedelta(seconds=5),
                event_action="block",
            ),
        ]
    )
    pipeline = CorrelatorPipeline.assemble(
        consumer=consumer,
        sinks=[StdoutIncidentSink(stream=io.StringIO())],
    )
    pipeline.tick()
    assert len(pipeline.last_incidents) == 2
    keys = {inc.grouping_key for inc in pipeline.last_incidents}
    assert keys == {"src_ip:203.0.113.45", "src_ip:198.51.100.1"}
