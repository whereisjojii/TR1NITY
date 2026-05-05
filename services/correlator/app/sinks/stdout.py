"""Stdout sink — used in DRY_RUN and tests.

Writes one JSON line per incident so the output is grep/jq-friendly
and ships through the standard container log pipeline without any
extra config.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from typing import TextIO

from ..incident import Incident
from .base import SinkResult

log = logging.getLogger(__name__)


@dataclass(slots=True)
class StdoutIncidentSink:
    """Newline-delimited JSON to ``stream`` (default: sys.stdout)."""

    name: str = "stdout"
    stream: TextIO = field(default_factory=lambda: sys.stdout)

    def write(self, incidents: list[Incident]) -> SinkResult:
        result = SinkResult(sink=self.name)
        for inc in incidents:
            try:
                self.stream.write(json.dumps(inc.to_index_doc(), default=str) + "\n")
                result.accepted += 1
            except (OSError, ValueError) as exc:
                result.rejected += 1
                result.errors.append(f"{type(exc).__name__}: {exc}")
                log.warning("StdoutIncidentSink: failed to write incident: %s", exc)
        try:
            if not self.stream.closed:
                self.stream.flush()
        except (OSError, ValueError):
            pass
        return result
