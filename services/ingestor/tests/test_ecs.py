"""ECS schema tests."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ecs import (
    ECS_VERSION,
    SEVERITY_MAP,
    ECSEvent,
    EventBlock,
    SourceDestBlock,
    TR1NITYBlock,
    new_event_id,
    truncate_raw,
)


def _minimal_event(**overrides) -> ECSEvent:
    base = {
        "@timestamp": datetime.now(UTC),
        "event": EventBlock(
            kind="event",
            module="test",
            dataset="test.fixture",
        ),
        "tr1nity": TR1NITYBlock(source="synthetic"),
    }
    base.update(overrides)
    return ECSEvent(**base)


def test_ecs_event_renders_canonical_fields() -> None:
    ev = _minimal_event()
    doc = ev.to_index_doc()
    assert "@timestamp" in doc
    assert doc["ecs.version"] == ECS_VERSION
    assert doc["event"]["module"] == "test"
    assert doc["tr1nity"]["source"] == "synthetic"


def test_severity_map_is_monotonically_non_decreasing() -> None:
    levels = [SEVERITY_MAP[i] for i in range(5)]
    assert levels == sorted(levels)
    # Must stay within the ECS-allowed 0..7 syslog scale.
    assert all(0 <= s <= 7 for s in levels)


def test_truncate_raw_truncates_oversized_inputs() -> None:
    huge = "x" * (16 * 1024)
    truncated, full_hash = truncate_raw(huge)
    assert truncated.endswith("...[truncated]")
    assert len(truncated) < len(huge)
    assert len(full_hash) == 64  # sha256 hex


def test_truncate_raw_preserves_short_inputs() -> None:
    msg = "small"
    truncated, full_hash = truncate_raw(msg)
    assert truncated == msg
    assert len(full_hash) == 64


def test_new_event_id_returns_unique_uuids() -> None:
    ids = {new_event_id() for _ in range(10)}
    assert len(ids) == 10


def test_source_dest_block_accepts_extra_fields() -> None:
    # We allow extras so that connectors can keep source-specific data
    # without us having to update the schema for every minor field.
    block = SourceDestBlock(ip="10.0.0.10", port=22, geo_country="PK")  # type: ignore[call-arg]
    dumped = block.model_dump(exclude_none=True)
    assert dumped["geo_country"] == "PK"
