"""FastAPI dependency providers for the api service.

Every dependency is exported as a small factory function so unit tests
can override them via ``app.dependency_overrides`` without monkey-
patching module globals.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .clients.correlator import CorrelatorClient
from .clients.opensearch import OpenSearchIncidentReader
from .config import APISettings, get_settings
from .fp.classifier import FPClassifier, get_classifier
from .fp.db import FeedbackDB, get_feedback_db
from .fp.whitelist import WhitelistRule, load_whitelist
from .runbooks import RunbookLibrary, get_runbook_library
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


@lru_cache(maxsize=1)
def _feedback_db_singleton() -> FeedbackDB:
    settings = get_settings()
    return get_feedback_db(settings.tr1nity_api_fp_db or None)


@lru_cache(maxsize=1)
def _classifier_singleton() -> FPClassifier:
    settings = get_settings()
    return get_classifier(settings.tr1nity_api_fp_model_path or None)


@lru_cache(maxsize=1)
def _whitelist_singleton() -> tuple[WhitelistRule, ...]:
    settings = get_settings()
    raw_path = settings.tr1nity_api_fp_whitelist
    if raw_path == "off":
        return ()
    path = Path(raw_path) if raw_path else Path(__file__).resolve().parent / "fp" / "whitelist.yaml"
    return tuple(load_whitelist(path))


@lru_cache(maxsize=1)
def _runbook_library_singleton() -> RunbookLibrary:
    settings = get_settings()
    return get_runbook_library(settings.tr1nity_api_runbooks_dir or None)


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


def get_feedback_db_dep() -> FeedbackDB:
    """Provide the SQLite feedback DB singleton (Phase 4)."""
    return _feedback_db_singleton()


def get_fp_classifier_dep() -> FPClassifier:
    """Provide the Layer-2 classifier singleton (Phase 4)."""
    return _classifier_singleton()


def get_whitelist_dep() -> tuple[WhitelistRule, ...]:
    """Provide the bundled YAML whitelist (Phase 4 Layer 1)."""
    return _whitelist_singleton()


def get_runbook_library_dep() -> RunbookLibrary:
    """Provide the runbook library singleton (Phase 4)."""
    return _runbook_library_singleton()


def reset_dependency_caches() -> None:
    """For tests — clear singletons so a fresh client is created next call."""
    _correlator_singleton.cache_clear()
    _opensearch_singleton.cache_clear()
    _feedback_db_singleton.cache_clear()
    _classifier_singleton.cache_clear()
    _whitelist_singleton.cache_clear()
    _runbook_library_singleton.cache_clear()


__all__ = [
    "_correlator_singleton",
    "_opensearch_singleton",
    "get_correlator_client",
    "get_feedback_db_dep",
    "get_fp_classifier_dep",
    "get_opensearch_reader",
    "get_runbook_library_dep",
    "get_settings_dep",
    "get_store_dep",
    "get_whitelist_dep",
    "reset_dependency_caches",
]
