"""Settings for the api service.

Mirrors the patterns used by the ingestor (Phase 1) and correlator
(Phase 2) services: every operational knob is one environment variable,
defaults are tuned for ``docker compose up`` to work on a fresh checkout
without external services, and validation runs at startup so
mis-configuration fails loudly.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class APISettings(BaseSettings):
    """Environment-driven configuration for the api service.

    Production env vars (most important):

    * ``CORRELATOR_URL`` — base URL of the Phase-2 correlator service.
    * ``OPENSEARCH_URL`` — used as a fallback read source for incidents
      when ``DRY_RUN=false`` and the correlator only emits to OpenSearch.
    * ``TR1NITY_API_JWT_SECRET`` — analyst auth (Phase 4 will start
      enforcing it; Phase 3 just stores it).
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

    # Upstream services. The api is a thin gateway over the correlator
    # for incidents and (in later phases) the ai-assist service for
    # drafts. Defaults match the docker-compose service names.
    correlator_url: str = "http://correlator:8002"
    ingestor_url: str = "http://ingestor:8001"
    ai_assist_url: str = "http://ai-assist:8003"

    # OpenSearch fallback for production reads (when the correlator only
    # caches the *last* tick in memory and we want the persisted view).
    opensearch_url: str = "https://wazuh-indexer:9200"
    opensearch_username: str = ""
    opensearch_password: SecretStr = SecretStr("")
    opensearch_verify_tls: bool = False
    incidents_index_pattern: str = "tr1nity-incidents-*"

    # Auth — Phase 3 stores the secret without enforcing it (the React
    # UI talks to the API directly inside the trusted container network).
    # Phase 4 layers on real auth.
    tr1nity_api_jwt_secret: SecretStr = SecretStr("change-me-to-a-random-32-char-string-min")

    # WebSocket fan-out cadence — when no correlator URL is reachable the
    # /ws/incidents stream falls back to this heartbeat interval.
    ws_heartbeat_seconds: int = Field(default=30, ge=5, le=300)

    # Cockpit static-asset directory. Empty string = no static mount
    # (default for unit tests). The Dockerfile builds the React app into
    # ``/app/static`` and sets this var.
    cockpit_static_dir: str = ""

    # CORS — by default the same-origin contract holds because the API
    # serves the static UI itself. Devs running ``pnpm dev`` on
    # localhost:5173 set this to that origin.
    cockpit_dev_origin: str = ""

    # Hard caps to avoid pathological queries.
    incidents_max_page_size: int = Field(default=200, ge=1, le=1000)

    # ---- Phase 4: FP loop & runbooks ---------------------------------
    # SQLite feedback DB path. Empty string → in-memory (dev/tests).
    tr1nity_api_fp_db: str = ""
    # YAML whitelist (Layer 1). Empty string → use the bundled file
    # next to the module; explicit "off" disables Layer 1 entirely.
    tr1nity_api_fp_whitelist: str = ""
    # sklearn classifier model (Layer 2). Empty string → no model yet,
    # which is fine: the layer is silently skipped until `make retrain`
    # produces a file.
    tr1nity_api_fp_model_path: str = ""
    # Directory containing the markdown runbook library. Empty string
    # → use the in-repo ``docs/runbooks`` directory.
    tr1nity_api_runbooks_dir: str = ""


@lru_cache(maxsize=1)
def get_settings() -> APISettings:
    """Cache one Settings instance per process."""
    return APISettings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """For tests only — clear the cached settings instance."""
    get_settings.cache_clear()
