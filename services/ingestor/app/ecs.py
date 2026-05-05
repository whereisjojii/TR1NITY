"""ECS (Elastic Common Schema) event model and helpers.

TR1NITY normalizes every input source (Wazuh, firewall syslog, ModSecurity /
WAF audit, Suricata EVE, ...) into the same ECS-shaped JSON document so that
downstream correlation, search, and reporting do not need source-specific
logic.

The schema is intentionally a *strict subset* of ECS 8.x — only the fields
TR1NITY actually consumes are typed here. Unknown fields go under the
``tr1nity`` namespace so we never lose data, and the raw original payload is
preserved (truncated) under ``tr1nity.raw`` for analyst inspection.

References:
    - https://www.elastic.co/guide/en/ecs/current/index.html
    - https://www.elastic.co/guide/en/ecs/current/ecs-allowed-values-event-kind.html
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ECS_VERSION = "8.11"
NORMALIZER_VERSION = "0.2.0"

# Maximum bytes of raw payload we keep verbatim; anything larger is truncated
# and a hash is recorded so the original can be retrieved from cold storage.
RAW_KEEP_BYTES = 8 * 1024  # 8 KiB

# ---------------------------------------------------------------------------
# Allowed value enumerations (ECS canonical)
# ---------------------------------------------------------------------------

EventKind = Literal[
    "alert",
    "event",
    "metric",
    "signal",
    "state",
    "pipeline_error",
]

EventCategory = Literal[
    "authentication",
    "configuration",
    "database",
    "driver",
    "email",
    "file",
    "host",
    "iam",
    "intrusion_detection",
    "malware",
    "network",
    "package",
    "process",
    "registry",
    "session",
    "threat",
    "vulnerability",
    "web",
]

EventType = Literal[
    "access",
    "admin",
    "allowed",
    "change",
    "connection",
    "creation",
    "deletion",
    "denied",
    "end",
    "error",
    "info",
    "installation",
    "protocol",
    "start",
    "user",
]

EventOutcome = Literal["success", "failure", "unknown"]

NetworkDirection = Literal[
    "ingress",
    "egress",
    "inbound",
    "outbound",
    "internal",
    "external",
    "unknown",
]

# TR1NITY-internal source identifier — which connector produced the event.
TR1NITYSource = Literal[
    "wazuh",
    "firewall",
    "waf",
    "suricata",
    "synthetic",
]


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class EventBlock(BaseModel):
    """ECS ``event.*`` field group."""

    model_config = ConfigDict(extra="allow")

    kind: EventKind = "event"
    category: list[EventCategory] = Field(default_factory=list)
    type: list[EventType] = Field(default_factory=list)
    action: str | None = None
    outcome: EventOutcome | None = None
    # ECS event.severity is integer 0–7 (syslog-style); we map via SEVERITY_MAP.
    severity: int = 0
    # event.module is the high-level integration name (e.g. "wazuh"),
    # event.dataset is more specific (e.g. "wazuh.alert").
    module: str
    dataset: str
    original: str | None = None  # raw original (truncated upstream)
    id: str | None = None  # stable per-event UUID
    ingested: datetime | None = None  # when ingestor received it


class HostBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    hostname: str | None = None
    ip: list[str] = Field(default_factory=list)
    os: dict[str, Any] | None = None


class SourceDestBlock(BaseModel):
    """Used for both ``source.*`` and ``destination.*``."""

    model_config = ConfigDict(extra="allow")
    ip: str | None = None
    port: int | None = None
    address: str | None = None
    domain: str | None = None
    bytes: int | None = None
    packets: int | None = None


class UserBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    id: str | None = None
    domain: str | None = None


class NetworkBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    transport: str | None = None  # tcp / udp / icmp
    protocol: str | None = None  # http / dns / smb ...
    direction: NetworkDirection | None = None
    bytes: int | None = None
    packets: int | None = None


class HTTPBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    version: str | None = None


class URLBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    full: str | None = None
    domain: str | None = None
    path: str | None = None
    query: str | None = None
    scheme: str | None = None


class RuleBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None


class ThreatTechnique(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None  # MITRE ATT&CK technique ID (e.g. T1110)
    name: str | None = None


class ThreatTactic(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str | None = None  # e.g. TA0006
    name: str | None = None  # e.g. Credential Access


class ThreatBlock(BaseModel):
    model_config = ConfigDict(extra="allow")
    framework: str | None = None  # "MITRE ATT&CK"
    technique: list[ThreatTechnique] = Field(default_factory=list)
    tactic: list[ThreatTactic] = Field(default_factory=list)


class TR1NITYBlock(BaseModel):
    """TR1NITY-private namespace; never collides with stock ECS."""

    model_config = ConfigDict(extra="allow")
    source: TR1NITYSource
    normalizer_version: str = NORMALIZER_VERSION
    raw: str | None = None  # truncated original payload (string form)
    raw_hash_sha256: str | None = None  # full payload digest (always present)


# ---------------------------------------------------------------------------
# Top-level ECS event
# ---------------------------------------------------------------------------


class ECSEvent(BaseModel):
    """A single ECS-normalized security event ready to ship to OpenSearch."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    timestamp: datetime = Field(alias="@timestamp")
    ecs_version: str = Field(default=ECS_VERSION, alias="ecs.version")

    event: EventBlock
    host: HostBlock | None = None
    source: SourceDestBlock | None = None
    destination: SourceDestBlock | None = None
    user: UserBlock | None = None
    network: NetworkBlock | None = None
    http: HTTPBlock | None = None
    url: URLBlock | None = None
    rule: RuleBlock | None = None
    threat: ThreatBlock | None = None
    message: str | None = None
    tags: list[str] = Field(default_factory=list)

    tr1nity: TR1NITYBlock

    def to_index_doc(self) -> dict[str, Any]:
        """Render to the dotted-key dict shape OpenSearch expects.

        Pydantic's ``model_dump(by_alias=True)`` already handles ``@timestamp``
        and ``ecs.version``. Sub-blocks remain nested objects, which is the
        correct ECS layout for OpenSearch / Elasticsearch.
        """
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

# Map TR1NITY's 0–4 internal severity scale to ECS event.severity (0–7).
# 0 = informational, 1 = low, 2 = medium, 3 = high, 4 = critical.
SEVERITY_MAP: dict[int, int] = {0: 0, 1: 2, 2: 4, 3: 6, 4: 7}


def truncate_raw(payload: str | bytes) -> tuple[str, str]:
    """Return ``(truncated_string, full_sha256_hex)``."""
    if isinstance(payload, bytes):
        full_hash = hashlib.sha256(payload).hexdigest()
        text = payload.decode("utf-8", errors="replace")
    else:
        full_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        text = payload
    if len(text) > RAW_KEEP_BYTES:
        text = text[:RAW_KEEP_BYTES] + "...[truncated]"
    return text, full_hash


def new_event_id() -> str:
    """Stable per-event UUID4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Timezone-aware current UTC."""
    return datetime.now(UTC)
