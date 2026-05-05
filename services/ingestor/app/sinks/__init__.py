"""Sinks — destinations for normalized ECSEvents."""

from .base import EventSink, SinkResult
from .opensearch import OpenSearchSink
from .stdout import StdoutSink

__all__ = ["EventSink", "OpenSearchSink", "SinkResult", "StdoutSink"]
