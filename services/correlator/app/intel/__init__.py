"""Threat-intel enrichment.

Free feeds only — TR1NITY's contract with users is "no paid APIs ever".
Today we ship:

* A bundled, file-based IOC list (``data/ioc.json``) that operators can
  hand-edit or replace with a downloaded snapshot.
* A pluggable provider protocol (`Provider`) so future phases can add
  AlienVault OTX, abuse.ch, SANS ISC, etc.

Lookups are read-only and cached in memory with a short TTL so the
correlator stays fast even when handling thousands of events per minute.
"""

from .base import IntelHit, Provider
from .cache import IntelCache
from .file_provider import FileProvider

__all__ = [
    "FileProvider",
    "IntelCache",
    "IntelHit",
    "Provider",
]
