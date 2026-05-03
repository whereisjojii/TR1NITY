"""FastAPI dependency callables.

* :func:`require_auth` enforces the bearer-token shared secret when
  ``ENABLE_AUTH=true``. Verification uses constant-time comparison so the
  endpoint cannot be used as a timing oracle for the secret.
* :func:`get_sink` returns the lazily-initialized event sink.
"""

from __future__ import annotations

import hmac
import logging
from functools import lru_cache

from fastapi import Header, HTTPException, status

from .config import IngestorSettings, get_settings
from .sinks import EventSink, OpenSearchSink, StdoutSink

log = logging.getLogger(__name__)


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Validate the ``Authorization: Bearer <token>`` header.

    A 401 is returned even when ``ENABLE_AUTH=false`` if the caller sent a
    *malformed* header — that's a sign of a misconfigured client, and we
    prefer loud failure over silently accepting weird inputs.
    """
    settings = get_settings()
    if not settings.enable_auth:
        # Still reject malformed headers — keeps client config honest.
        if authorization and not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization header present but malformed",
            )
        return

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = authorization.split(" ", 1)[1].strip()
    expected = settings.ingestor_auth_token.get_secret_value()
    if not expected or not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@lru_cache(maxsize=1)
def _build_sink_from_settings(settings_id: int) -> EventSink:
    # ``settings_id`` is purely a cache key derived from id(settings) so that
    # tests can swap settings and get a fresh sink.
    del settings_id
    settings: IngestorSettings = get_settings()
    if settings.dry_run:
        log.info("Ingestor running in DRY_RUN mode — events go to stdout.")
        return StdoutSink()
    return OpenSearchSink(
        base_url=settings.opensearch_url,
        username=settings.opensearch_username or None,
        password=settings.opensearch_password.get_secret_value() or None,
        index_prefix=settings.opensearch_index_prefix,
        verify_tls=settings.opensearch_verify_tls,
    )


def get_sink() -> EventSink:
    return _build_sink_from_settings(id(get_settings()))


def reset_sink_cache() -> None:
    """For tests only."""
    _build_sink_from_settings.cache_clear()
