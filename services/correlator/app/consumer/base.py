"""EventConsumer protocol — where the correlator pulls ECS events from."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventConsumer(Protocol):
    """Source of ECS event dicts.

    The contract is intentionally minimal: callers ask for a batch and
    get back a list. Whether the implementation paginates an OpenSearch
    cursor or pops items from an in-memory queue is an internal detail.
    """

    def fetch(self, *, max_events: int) -> list[dict[str, Any]]:
        """Return up to ``max_events`` events; ``[]`` when nothing is ready."""
        ...
