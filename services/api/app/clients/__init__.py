"""HTTP clients for upstream TR1NITY services.

The api service is a thin gateway in Phase 3. We deliberately keep one
client per upstream so retries, timeouts, and error mapping live in one
place per dependency.
"""

from .correlator import CorrelatorClient, CorrelatorError, CorrelatorUnavailableError
from .opensearch import OpenSearchIncidentReader

__all__ = [
    "CorrelatorClient",
    "CorrelatorError",
    "CorrelatorUnavailableError",
    "OpenSearchIncidentReader",
]
