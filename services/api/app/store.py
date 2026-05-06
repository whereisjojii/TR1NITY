"""In-memory analyst-state store for Phase 3.

The Cockpit needs to remember three things across requests:

1. **FP feedback** — analyst clicks "Mark FP" on an incident. Phase 4
   will train the sklearn classifier on this. Phase 3 just persists
   the feedback in process so the UI can sort by ``fp_score`` and the
   queue stays consistent across reloads.
2. **Cases** — the lightweight built-in case manager (alternative to
   TheHive). One incident may belong to one case; one case can group
   many incidents.
3. **Recent incidents cache** — a small ring buffer of incidents the
   api has seen. The correlator only keeps the last *tick*; we keep
   a longer window so the queue reflects the recent past even if the
   correlator just rebooted.

All Phase-3 state is **non-durable on purpose**: Phase 4 swaps this out
for Postgres-backed storage. The interface is intentionally narrow so
that swap is ~one file later.
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from collections import OrderedDict, deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FP feedback
# ---------------------------------------------------------------------------


FPSource = Literal["analyst", "whitelist", "classifier"]


@dataclass(slots=True)
class FPFeedback:
    """One analyst-supplied FP signal for an incident."""

    incident_id: str
    is_fp: bool
    reason: str | None = None
    source: FPSource = "analyst"
    submitted_by: str = "anonymous"
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "is_fp": self.is_fp,
            "reason": self.reason,
            "source": self.source,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


CaseStatus = Literal["open", "investigating", "containment", "resolved", "closed"]
_CASE_STATUSES = {"open", "investigating", "containment", "resolved", "closed"}


@dataclass(slots=True)
class Case:
    """A lightweight investigation case."""

    title: str
    case_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: int = 0  # ECS-style 0..7
    status: CaseStatus = "open"
    summary: str | None = None
    incident_ids: list[str] = field(default_factory=list)
    assigned_to: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "severity": self.severity,
            "status": self.status,
            "summary": self.summary,
            "incident_ids": list(self.incident_ids),
            "assigned_to": self.assigned_to,
            "tags": list(self.tags),
            "notes": [dict(n) for n in self.notes],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# In-process state
# ---------------------------------------------------------------------------


class CockpitStore:
    """Thread-safe in-memory store for Phase-3 cockpit state.

    Phase 4 replaces this with a SQLAlchemy-backed Postgres store. The
    public surface here matches the planned production interface, so
    routers don't have to change.
    """

    def __init__(self, *, recent_incidents_capacity: int = 1000) -> None:
        self._lock = threading.RLock()
        self._fp: dict[str, FPFeedback] = {}
        # Insertion-ordered case map so listings are stable.
        self._cases: OrderedDict[str, Case] = OrderedDict()
        self._recent_incidents: deque[dict[str, Any]] = deque(maxlen=recent_incidents_capacity)
        self._recent_seen_ids: set[str] = set()

    # ----- FP feedback -------------------------------------------------

    def record_fp(self, feedback: FPFeedback) -> FPFeedback:
        with self._lock:
            self._fp[feedback.incident_id] = feedback
        return feedback

    def get_fp(self, incident_id: str) -> FPFeedback | None:
        with self._lock:
            return self._fp.get(incident_id)

    def list_fp(self) -> list[FPFeedback]:
        with self._lock:
            return list(self._fp.values())

    def fp_score(self, incident_id: str) -> float:
        """Return a 0..1 FP score for an incident.

        Phase-3 logic is deterministic and analyst-driven:
        - Explicit "is FP" → 1.0
        - Explicit "not FP" → 0.0
        - No feedback → 0.5 (neutral, lets sorting still work).
        Phase 4 replaces the neutral 0.5 with the sklearn classifier's
        probability and exposes a calibration dial.
        """
        fb = self.get_fp(incident_id)
        if fb is None:
            return 0.5
        return 1.0 if fb.is_fp else 0.0

    # ----- Cases -------------------------------------------------------

    def create_case(
        self,
        *,
        title: str,
        severity: int = 0,
        status: CaseStatus = "open",
        summary: str | None = None,
        incident_ids: Iterable[str] | None = None,
        assigned_to: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> Case:
        if not title.strip():
            raise ValueError("case title cannot be empty")
        if status not in _CASE_STATUSES:
            raise ValueError(f"invalid case status: {status!r}")
        case = Case(
            title=title.strip(),
            severity=_clamp_severity(severity),
            status=status,
            summary=summary,
            incident_ids=list(incident_ids or []),
            assigned_to=assigned_to,
            tags=list(tags or []),
        )
        with self._lock:
            self._cases[case.case_id] = case
        return case

    def get_case(self, case_id: str) -> Case | None:
        with self._lock:
            return self._cases.get(case_id)

    def list_cases(
        self,
        *,
        status: CaseStatus | None = None,
        assigned_to: str | None = None,
    ) -> list[Case]:
        with self._lock:
            cases = list(self._cases.values())
        if status is not None:
            cases = [c for c in cases if c.status == status]
        if assigned_to is not None:
            cases = [c for c in cases if c.assigned_to == assigned_to]
        # Newest-first for the queue UI.
        cases.sort(key=lambda c: c.updated_at, reverse=True)
        return cases

    def update_case(self, case_id: str, **changes: Any) -> Case | None:
        allowed = {
            "title",
            "severity",
            "status",
            "summary",
            "incident_ids",
            "assigned_to",
            "tags",
        }
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                return None
            for key, value in changes.items():
                if key not in allowed or value is None:
                    continue
                if key == "severity":
                    case.severity = _clamp_severity(int(value))
                elif key == "status":
                    if value not in _CASE_STATUSES:
                        raise ValueError(f"invalid case status: {value!r}")
                    case.status = value  # type: ignore[assignment]
                elif key in {"incident_ids", "tags"}:
                    setattr(case, key, list(value))
                else:
                    setattr(case, key, value)
            case.updated_at = datetime.now(UTC)
            return case

    def add_case_note(
        self,
        case_id: str,
        *,
        author: str,
        body: str,
    ) -> Case | None:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                return None
            case.notes.append(
                {
                    "author": author,
                    "body": body,
                    "at": datetime.now(UTC).isoformat(),
                }
            )
            case.updated_at = datetime.now(UTC)
            return case

    def delete_case(self, case_id: str) -> bool:
        with self._lock:
            return self._cases.pop(case_id, None) is not None

    # ----- Recent incidents cache -------------------------------------

    def remember_incidents(self, incidents: Iterable[dict[str, Any]]) -> int:
        added = 0
        with self._lock:
            for inc in incidents:
                iid = inc.get("incident_id")
                if not isinstance(iid, str) or not iid:
                    continue
                if iid in self._recent_seen_ids:
                    # Refresh by removing the stale copy first.
                    self._recent_incidents = deque(
                        (i for i in self._recent_incidents if i.get("incident_id") != iid),
                        maxlen=self._recent_incidents.maxlen,
                    )
                self._recent_incidents.append(inc)
                self._recent_seen_ids.add(iid)
                added += 1
            # Re-sync seen-set if buffer eviction dropped some.
            self._recent_seen_ids = {
                str(i.get("incident_id"))
                for i in self._recent_incidents
                if isinstance(i.get("incident_id"), str)
            }
        return added

    def iter_recent_incidents(self) -> Iterator[dict[str, Any]]:
        with self._lock:
            yield from list(self._recent_incidents)

    def list_recent_incidents(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent_incidents)

    def clear_recent_incidents(self) -> None:
        with self._lock:
            self._recent_incidents.clear()
            self._recent_seen_ids.clear()

    # ----- Test helpers ------------------------------------------------

    def reset(self) -> None:
        """Wipe everything — used between unit tests."""
        with self._lock:
            self._fp.clear()
            self._cases.clear()
            self._recent_incidents.clear()
            self._recent_seen_ids.clear()


def _clamp_severity(value: int) -> int:
    if math.isnan(float(value)):
        return 0
    return max(0, min(7, int(value)))


# A module-level singleton so routers can grab the store via Depends().
# Tests reset it through ``CockpitStore.reset`` in fixtures.
_default_store: CockpitStore | None = None


def get_store() -> CockpitStore:
    global _default_store
    if _default_store is None:
        _default_store = CockpitStore()
    return _default_store


def replace_store(store: CockpitStore) -> CockpitStore:
    """For tests — swap in a fresh store."""
    global _default_store
    _default_store = store
    return store
