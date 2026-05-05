"""In-memory EventConsumer used in tests + DRY_RUN mode."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class InMemoryEventConsumer:
    """A simple FIFO of pre-supplied event dicts."""

    _queue: deque[dict[str, Any]] = field(default_factory=deque)

    def push(self, events: Iterable[dict[str, Any]]) -> None:
        """Append one or more events to the back of the queue."""
        for ev in events:
            self._queue.append(ev)

    def fetch(self, *, max_events: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for _ in range(max_events):
            if not self._queue:
                break
            out.append(self._queue.popleft())
        return out

    def __len__(self) -> int:
        return len(self._queue)
