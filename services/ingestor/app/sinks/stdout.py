"""Stdout sink — emits one JSON document per line.

Used for:
* unit tests (no external dependencies),
* the ``DRY_RUN=true`` ingestor mode for local development,
* operators who want to pipe normalized events into another tool.
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Iterable
from typing import TextIO

from ..ecs import ECSEvent
from .base import EventSink, SinkResult


class StdoutSink(EventSink):
    name = "stdout"

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream: TextIO = stream if stream is not None else sys.stdout

    async def write(self, events: Iterable[ECSEvent]) -> SinkResult:
        result = SinkResult()
        for ev in events:
            try:
                self._stream.write(json.dumps(ev.to_index_doc(), default=str) + "\n")
                result.accepted += 1
            except (TypeError, ValueError) as e:  # serialization failures only
                result.rejected += 1
                result.errors.append(f"stdout-serialize: {type(e).__name__}: {e}")
        with contextlib.suppress(OSError, ValueError):
            self._stream.flush()
        return result

    async def healthy(self) -> bool:
        return not getattr(self._stream, "closed", False)

    async def close(self) -> None:
        # We intentionally do not close stdout/stderr.
        return None
