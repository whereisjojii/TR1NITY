"""Correlation pipeline — wires consumer → grouping → enrichment → sink.

This is the only module that knows about all of the moving parts. Each
component is independently testable; the pipeline is what we run in
production and in the demo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .attack import chain_metadata, render_chain
from .consumer.base import EventConsumer
from .grouping import group_events
from .incident import Incident
from .intel.base import Provider
from .intel.cache import IntelCache
from .sigma import SigmaEngine
from .sinks.base import IncidentSink, SinkResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CorrelatorPipeline:
    """End-to-end correlation: events in, incidents out, side effects on sinks."""

    consumer: EventConsumer
    sinks: list[IncidentSink]
    sigma: SigmaEngine | None = None
    intel: IntelCache | None = None
    window_seconds: int = 900
    max_events_per_incident: int = 500
    max_events_per_tick: int = 1000

    last_incidents: list[Incident] = field(default_factory=list)

    @classmethod
    def assemble(
        cls,
        *,
        consumer: EventConsumer,
        sinks: list[IncidentSink],
        sigma_engine: SigmaEngine | None = None,
        intel_providers: list[Provider] | None = None,
        intel_ttl_seconds: int = 3600,
        window_seconds: int = 900,
        max_events_per_incident: int = 500,
    ) -> CorrelatorPipeline:
        """Construct a pipeline with sensible defaults wired in."""
        intel_cache: IntelCache | None = None
        if intel_providers:
            intel_cache = IntelCache(
                providers=list(intel_providers),
                ttl_seconds=intel_ttl_seconds,
            )
        return cls(
            consumer=consumer,
            sinks=list(sinks),
            sigma=sigma_engine,
            intel=intel_cache,
            window_seconds=window_seconds,
            max_events_per_incident=max_events_per_incident,
        )

    # ------------------------------------------------------------------
    # Per-tick orchestration
    # ------------------------------------------------------------------

    def tick(self) -> list[SinkResult]:
        """Pull one batch of events, correlate, enrich, and ship.

        Returns a SinkResult for every sink, in the order ``self.sinks``
        was declared. Useful for tests and for surfacing per-sink stats
        without a separate metrics endpoint in this phase.
        """
        events = self.consumer.fetch(max_events=self.max_events_per_tick)
        if not events:
            self.last_incidents = []
            return [SinkResult(sink=sink.name) for sink in self.sinks]

        # Per-event SIGMA matching FIRST — this can promote severity and
        # add technique tags before grouping rolls them up.
        if self.sigma is not None:
            for ev in events:
                self._apply_sigma(ev)

        incidents = group_events(
            events,
            window_seconds=self.window_seconds,
            max_events_per_incident=self.max_events_per_incident,
        )
        for inc in incidents:
            self._enrich(inc)

        self.last_incidents = incidents

        results: list[SinkResult] = []
        for sink in self.sinks:
            try:
                results.append(sink.write(incidents))
            except Exception as exc:  # pragma: no cover - defensive
                log.exception("CorrelatorPipeline: sink %s raised", sink.name)
                results.append(
                    SinkResult(
                        sink=sink.name,
                        rejected=len(incidents),
                        errors=[f"{type(exc).__name__}: {exc}"],
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_sigma(self, event: dict[str, Any]) -> None:
        """Run SIGMA rules; promote any technique tags / severity."""
        if self.sigma is None:
            return
        matches = self.sigma.match(event)
        if not matches:
            return

        # Severity: take the max of (existing event.severity, any rule severity).
        ev_block = event.setdefault("event", {})
        current = int(ev_block.get("severity") or 0)
        promoted = max(current, *(m.severity for m in matches))
        ev_block["severity"] = promoted

        # Add ATT&CK technique IDs from rule tags like ``attack.t1190``.
        threat = event.setdefault("threat", {"framework": "MITRE ATT&CK"})
        techniques = threat.setdefault("technique", [])
        existing_ids = {t.get("id") for t in techniques if isinstance(t, dict) and t.get("id")}
        for match in matches:
            for tag in match.tags:
                low = tag.lower().strip()
                if low.startswith("attack.t"):
                    tid = "T" + low.removeprefix("attack.t").upper()
                    if tid not in existing_ids:
                        techniques.append({"id": tid, "name": match.rule_title})
                        existing_ids.add(tid)

        # Stash the matches on the event under our private namespace so the
        # incident serializer can surface them later.
        tr = event.setdefault("tr1nity", {"source": "sigma"})
        sigma_list = tr.setdefault("sigma_matches", [])
        for match in matches:
            if match.rule_id not in sigma_list:
                sigma_list.append(match.rule_id)

    def _enrich(self, incident: Incident) -> None:
        """Attach kill-chain ordering + threat-intel hits to one incident."""
        # ATT&CK ordering — even if nothing else changed, render a chain.
        meta = chain_metadata(incident.technique_ids)
        incident.technique_ids = meta["technique_ids"]
        incident.tactic_ids = meta["tactic_ids"]
        if incident.technique_ids:
            chain = render_chain(incident.technique_ids)
            if chain and (not incident.summary or "ATT&CK chain" not in incident.summary):
                incident.summary = (incident.summary or "") + f" | ATT&CK chain: {chain}"

        # SIGMA matches — gather the ones we stamped onto member events.
        sigma_seen: set[str] = set(incident.sigma_matches)
        for member in incident.members:
            for rid in getattr(member, "technique_ids", []):
                if rid in sigma_seen:
                    continue

        # Intel — IPs only for now (domains will land when DNS-flavored
        # parsers ship in a later phase).
        if self.intel is not None:
            seen_pairs: set[tuple[str, str]] = {
                (h.get("indicator", ""), h.get("feed", "")) for h in incident.intel_hits
            }
            ips = {m.source_ip for m in incident.members if m.source_ip}
            for ip in ips:
                for hit in self.intel.lookup_ip(ip):
                    pair = (hit.indicator, hit.feed)
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    incident.intel_hits.append(
                        {
                            "indicator": hit.indicator,
                            "indicator_type": hit.indicator_type,
                            "feed": hit.feed,
                            "description": hit.description,
                            "tags": list(hit.tags),
                            "confidence": hit.confidence,
                        }
                    )
