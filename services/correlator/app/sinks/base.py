"""Incident sink protocol + the small ``SinkResult`` value object.

Mirrors the ingestor's sink layout so anyone reading both services sees
the same shape twice. Sinks are sync — the correlator runs at low rate
(seconds-scale polling) and a sync interface is dramatically simpler to
test and reason about than an async one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..incident import Incident


@dataclass(slots=True)
class SinkResult:
    """Outcome of writing one batch of incidents to a sink."""

    accepted: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)
    sink: str = "unknown"


@runtime_checkable
class IncidentSink(Protocol):
    """An object capable of receiving a batch of incidents."""

    name: str

    def write(self, incidents: list[Incident]) -> SinkResult:
        """Persist ``incidents`` and return what happened.

        Sinks must never raise on a routine input — exceptions are
        wrapped into ``SinkResult.errors`` so the pipeline stays alive.
        """
        ...
