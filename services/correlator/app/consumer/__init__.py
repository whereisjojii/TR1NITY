"""Where ECS events come from for the correlator."""

from .base import EventConsumer
from .memory import InMemoryEventConsumer
from .opensearch import OpenSearchEventConsumer

__all__ = [
    "EventConsumer",
    "InMemoryEventConsumer",
    "OpenSearchEventConsumer",
]
