"""FastAPI dependency providers for the api service.

Every dependency is exported as a small factory function so unit tests
can override them via ``app.dependency_overrides`` without monkey-
patching module globals.
"""

from __future__ import annotations

from functools import lru_cache

from .clients.correlator import CorrelatorClient
from .clients.opensearch import OpenSearchIncidentReader
from .config import APISettings, get_settings
from .store import CockpitStore, get_store


@lru_cache(maxsize=1)
def _correlator_singleton() -> CorrelatorClient:
    settings = get_settings()
    return CorrelatorClient(base_url=settings.correlator_url)


@lru_cache(maxsize=1)
def _opensearch_singleton() -> OpenSearchIncidentReader:
    settings = get_settings()
    return OpenSearchIncidentReader(
        base_url=settings.opensearch_url,
        username=settings.opensearch_username,
        password=settings.opensearch_password.get_secret_value(),
        verify_tls=settings.opensearch_verify_tls,
        index_pattern=settings.incidents_index_pattern,
    )


def get_correlator_client() -> CorrelatorClient:
    """Provide the singleton correlator client."""
    return _correlator_singleton()


def get_opensearch_reader() -> OpenSearchIncidentReader:
    """Provide the singleton OpenSearch incident reader."""
    return _opensearch_singleton()


def get_settings_dep() -> APISettings:
    """Provide the cached APISettings instance."""
    return get_settings()


def get_store_dep() -> CockpitStore:
    """Provide the in-process CockpitStore singleton."""
    return get_store()


def reset_dependency_caches() -> None:
    """For tests — clear singletons so a fresh client is created next call."""
    _correlator_singleton.cache_clear()
    _opensearch_singleton.cache_clear()


__all__ = [
    "_correlator_singleton",
    "_opensearch_singleton",
    "get_correlator_client",
    "get_opensearch_reader",
    "get_settings_dep",
    "get_store_dep",
    "reset_dependency_caches",
]
