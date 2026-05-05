"""Where finalized incidents go."""

from .base import IncidentSink, SinkResult
from .opensearch import OpenSearchIncidentSink
from .stdout import StdoutIncidentSink

__all__ = [
    "IncidentSink",
    "OpenSearchIncidentSink",
    "SinkResult",
    "StdoutIncidentSink",
]
