"""Settings for the ingestor service.

Every setting comes from an environment variable so production deployments
never need code changes — and so secrets stay out of the repo. Pydantic
validates types and ranges at startup; misconfiguration fails loudly rather
than silently falling back to insecure defaults.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class IngestorSettings(BaseSettings):
    """Environment-driven configuration.

    Production env vars (must be set in deployment):

    * ``INGESTOR_AUTH_TOKEN`` — shared secret for ``Authorization: Bearer …``
    * ``OPENSEARCH_URL`` — OpenSearch / Wazuh-indexer base URL
    * ``OPENSEARCH_USERNAME`` / ``OPENSEARCH_PASSWORD`` — credentials

    Defaults are tuned for local ``docker compose up``: dry-run on (no real
    OpenSearch needed), auth disabled (no random 401s on a fresh checkout),
    and short timeouts to fail fast rather than hang.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Service identity
    tr1nity_env: str = Field(default="dev", description="Deployment env label")

    # Auth — webhook bearer token. When ``enable_auth=False`` (default in dev)
    # the routers accept anonymous requests; ALWAYS set ``enable_auth=True``
    # plus a strong token in any non-loopback deployment.
    enable_auth: bool = False
    ingestor_auth_token: SecretStr = SecretStr("")

    # Sink wiring
    opensearch_url: str = "http://wazuh-indexer:9200"
    opensearch_username: str = ""
    opensearch_password: SecretStr = SecretStr("")
    opensearch_index_prefix: str = "tr1nity-events"
    opensearch_verify_tls: bool = True

    # If true, do NOT contact OpenSearch — write events to stdout instead.
    # Default ON so that ``docker compose up`` works on a fresh checkout
    # without needing the indexer to be healthy.
    dry_run: bool = True

    # Hard input limits — defenses against malicious / runaway producers.
    max_body_bytes: int = Field(default=1_048_576, ge=1024, le=64 * 1024 * 1024)
    max_lines_per_request: int = Field(default=1000, ge=1, le=100_000)
    max_events_per_request: int = Field(default=500, ge=1, le=10_000)


@lru_cache(maxsize=1)
def get_settings() -> IngestorSettings:
    """Cache one Settings instance per process."""
    s = IngestorSettings()  # type: ignore[call-arg]
    if s.enable_auth and not s.ingestor_auth_token.get_secret_value():
        log.warning("INGESTOR_AUTH_TOKEN is empty but ENABLE_AUTH=true — every request will 401.")
    if not s.dry_run and not s.opensearch_url:
        log.warning("DRY_RUN=false but OPENSEARCH_URL is empty.")
    return s


def reset_settings_cache() -> None:
    """For tests only — clear the cached settings instance."""
    get_settings.cache_clear()
