"""Settings for the correlator service.

Environment-driven, validated at startup. Mirrors the pattern used by the
ingestor service so deployments stay consistent — every operational knob
is one env var, defaults are tuned for ``docker compose up`` to work on
a fresh checkout (DRY_RUN on, no secrets required).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class CorrelatorSettings(BaseSettings):
    """Environment-driven configuration for the correlator service."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Service identity
    tr1nity_env: str = Field(default="dev", description="Deployment env label")

    # OpenSearch wiring (shared with ingestor in production)
    opensearch_url: str = "https://wazuh-indexer:9200"
    opensearch_username: str = ""
    opensearch_password: SecretStr = SecretStr("")
    opensearch_verify_tls: bool = True

    # Index patterns
    events_index_pattern: str = "tr1nity-events-*"
    incidents_index_prefix: str = "tr1nity-incidents"

    # When DRY_RUN is on the correlator does not touch OpenSearch — it
    # consumes events from an in-memory queue and emits incidents to stdout.
    # Default ON so a fresh ``docker compose up`` works without the indexer.
    dry_run: bool = True

    # Correlation tuning
    # ----------------
    # Window over which related events are merged into one incident.
    incident_window_seconds: int = Field(default=900, ge=60, le=24 * 3600)
    # Hard ceiling: how many events one incident can absorb before we cut
    # it loose and start a fresh incident (prevents runaway grouping when
    # one IP is genuinely scanning everything for hours).
    incident_max_events: int = Field(default=500, ge=10, le=10_000)

    # Polling cadence for the OpenSearch consumer (seconds).
    poll_interval_seconds: int = Field(default=10, ge=1, le=600)

    # Threat-intel tuning
    intel_cache_ttl_seconds: int = Field(default=3600, ge=60, le=24 * 3600)
    intel_enabled: bool = True

    # SIGMA rules
    sigma_rules_dir: str = "rules"
    sigma_enabled: bool = True


@lru_cache(maxsize=1)
def get_settings() -> CorrelatorSettings:
    """Cache one Settings instance per process."""
    return CorrelatorSettings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """For tests only — clear the cached settings instance."""
    get_settings.cache_clear()
