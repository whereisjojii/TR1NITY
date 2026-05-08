"""Feature extraction — incident dict → numeric vector for the L2 classifier.

Centralised here so the trainer and the runtime scorer agree on the
feature shape. Every feature is bounded and float-typed; missing
sub-fields fall back to neutral values so the classifier still has
something to chew on.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

# Stable, ordered list — keep in sync between train.py and the runtime
# scorer. Adding a feature requires bumping this list and a `make
# retrain` so the model dimensionality matches.
FEATURE_NAMES: tuple[str, ...] = (
    "severity",
    "member_count",
    "source_count",
    "technique_count",
    "sigma_match_count",
    "intel_hit_count",
    "hour_of_day",
    "is_internal_source",
    "has_user",
    "has_destination",
)


def extract_features(incident: dict[str, Any]) -> dict[str, float]:
    """Return a dict view of the feature vector for ``incident``.

    Returning a dict (rather than a numpy array) keeps the feature
    surface readable, lets us serialise it into the feedback DB, and
    avoids importing numpy at request time when sklearn isn't actually
    in use.
    """
    members = incident.get("members") or []
    members_list = members if isinstance(members, list) else []

    severity = _clamp(_to_float(incident.get("severity"), 0.0), 0.0, 7.0)
    member_count = float(len(members_list))
    sources = incident.get("sources") or []
    source_count = float(len(sources)) if isinstance(sources, list) else 0.0
    techniques = incident.get("technique_ids") or []
    technique_count = float(len(techniques)) if isinstance(techniques, list) else 0.0
    sigma = incident.get("sigma_matches") or []
    sigma_match_count = float(len(sigma)) if isinstance(sigma, list) else 0.0
    intel = incident.get("intel_hits") or []
    intel_hit_count = float(len(intel)) if isinstance(intel, list) else 0.0

    hour_of_day = _hour_of_day(incident.get("last_event_at") or incident.get("created_at"))
    internal_source = float(_has_internal_source_ip(members_list))
    has_user = float(any(_member_has(m, "user") for m in members_list))
    has_destination = float(any(_member_has(m, "destination_ip") for m in members_list))

    return {
        "severity": severity,
        "member_count": member_count,
        "source_count": source_count,
        "technique_count": technique_count,
        "sigma_match_count": sigma_match_count,
        "intel_hit_count": intel_hit_count,
        "hour_of_day": hour_of_day,
        "is_internal_source": internal_source,
        "has_user": has_user,
        "has_destination": has_destination,
    }


def vectorize(features: dict[str, float]) -> list[float]:
    """Project a feature dict to the canonical ordered list."""
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _hour_of_day(value: Any) -> float:
    if not isinstance(value, str):
        return 0.0
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return float(ts.hour)


def _has_internal_source_ip(members: Iterable[Any]) -> bool:
    for m in members:
        if not isinstance(m, dict):
            continue
        ip = m.get("source_ip")
        if isinstance(ip, str) and _is_internal(ip):
            return True
        # Walk ECS-style nested form too.
        src = m.get("source") if isinstance(m.get("source"), dict) else None
        if src and isinstance(src.get("ip"), str) and _is_internal(src["ip"]):
            return True
    return False


def _member_has(member: Any, key: str) -> bool:
    if not isinstance(member, dict):
        return False
    if member.get(key):
        return True
    # ECS nested fallback (e.g. ``destination.ip``).
    nested = member.get(key.split("_")[0]) if "_" in key else None
    return bool(isinstance(nested, dict) and nested.get(key.split("_", 1)[1]))


def _is_internal(ip: str) -> bool:
    if ip.startswith("10."):
        return True
    if ip.startswith("192.168."):
        return True
    if ip.startswith("127."):
        return True
    if ip.startswith("172."):
        try:
            second = int(ip.split(".")[1])
        except (ValueError, IndexError):
            return False
        return 16 <= second <= 31
    return False
