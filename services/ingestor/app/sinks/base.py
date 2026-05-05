"""Sink protocol and shared result type."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from ..ecs import ECSEvent


@dataclass(slots=True)
class SinkResult:
    """Outcome of a single :py:meth:`EventSink.write` call.

    ``accepted`` + ``rejected`` should always equal ``len(input)``.
    ``errors`` is a short list of human-readable diagnostics; full payloads
    never appear here so that logs do not leak event data.
    """

    accepted: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)

    def __add__(self, other: SinkResult) -> SinkResult:
        return SinkResult(
            accepted=self.accepted + other.accepted,
            rejected=self.rejected + other.rejected,
            errors=self.errors + other.errors,
        )


class EventSink(Protocol):
    """Anything that can durably (or visibly) accept normalized events."""

    name: str

    async def write(self, events: Iterable[ECSEvent]) -> SinkResult:  # pragma: no cover - protocol
        ...

    async def healthy(self) -> bool:  # pragma: no cover - protocol
        ...

    async def close(self) -> None:  # pragma: no cover - protocol
        ...
