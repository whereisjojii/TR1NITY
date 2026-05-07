"""SQLite-backed feedback DB for the FP loop.

Stores two things:

* ``fp_feedback`` — every analyst "Mark FP" / "Mark TP" click, with the
  incident's feature vector at the time of the click. The Layer-2
  trainer (``app.fp.train``) reads this table to fit the classifier.
* ``suppressions`` — Layer-3 analyst-authored rules with a TTL. Loaded
  on every incident-listing request so newly-added suppressions take
  effect immediately and expired ones drop out without a separate
  cron.

Why stdlib ``sqlite3`` and not SQLAlchemy: the schema is two narrow
tables with no relationships and the workload is bounded (one row per
analyst click + a small operator-curated rule set). Keeping the
dependency surface minimal is more valuable here than an ORM. The
fp-handling design doc explicitly calls this out as a SQLite store.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Row dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FeedbackRow:
    """One analyst FP/TP click with the incident's feature snapshot."""

    feedback_id: str
    incident_id: str
    is_fp: bool
    reason: str | None
    submitted_by: str
    submitted_at: datetime
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "incident_id": self.incident_id,
            "is_fp": self.is_fp,
            "reason": self.reason,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at.isoformat(),
            "features": dict(self.features),
        }


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS fp_feedback (
    feedback_id   TEXT PRIMARY KEY,
    incident_id   TEXT NOT NULL,
    is_fp         INTEGER NOT NULL,
    reason        TEXT,
    submitted_by  TEXT NOT NULL,
    submitted_at  TEXT NOT NULL,
    features_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_fp_feedback_incident ON fp_feedback(incident_id);
CREATE INDEX IF NOT EXISTS idx_fp_feedback_submitted_at ON fp_feedback(submitted_at);

CREATE TABLE IF NOT EXISTS suppressions (
    suppression_id TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    match_json     TEXT NOT NULL,
    fp_score       REAL NOT NULL,
    ttl_days       INTEGER,
    author         TEXT NOT NULL DEFAULT 'anonymous',
    reason         TEXT,
    created_at     TEXT NOT NULL,
    expires_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_suppressions_expires ON suppressions(expires_at);
"""


class FeedbackDB:
    """Thread-safe sqlite wrapper for the FP loop's persistent state."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        self._lock = threading.RLock()
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # ``check_same_thread=False`` is safe because every access is
        # serialised through ``self._lock``.
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------
    # FP feedback
    # ------------------------------------------------------------------

    def record_feedback(
        self,
        *,
        incident_id: str,
        is_fp: bool,
        reason: str | None = None,
        submitted_by: str = "anonymous",
        features: dict[str, Any] | None = None,
        submitted_at: datetime | None = None,
    ) -> FeedbackRow:
        feedback_id = str(uuid.uuid4())
        ts = submitted_at or datetime.now(UTC)
        feature_payload = dict(features or {})
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO fp_feedback
                    (feedback_id, incident_id, is_fp, reason,
                     submitted_by, submitted_at, features_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    incident_id,
                    1 if is_fp else 0,
                    reason,
                    submitted_by,
                    ts.isoformat(),
                    json.dumps(feature_payload, sort_keys=True),
                ),
            )
            self._conn.commit()
        return FeedbackRow(
            feedback_id=feedback_id,
            incident_id=incident_id,
            is_fp=is_fp,
            reason=reason,
            submitted_by=submitted_by,
            submitted_at=ts,
            features=feature_payload,
        )

    def list_feedback(self, *, limit: int | None = None) -> list[FeedbackRow]:
        sql = "SELECT * FROM fp_feedback ORDER BY submitted_at DESC"
        params: tuple[Any, ...] = ()
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            params = (int(limit),)
        with self._lock:
            rows = list(self._conn.execute(sql, params).fetchall())
        return [_row_to_feedback(r) for r in rows]

    def latest_feedback(self, incident_id: str) -> FeedbackRow | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM fp_feedback WHERE incident_id = ? "
                "ORDER BY submitted_at DESC LIMIT 1",
                (incident_id,),
            ).fetchone()
        return _row_to_feedback(row) if row is not None else None

    def feedback_count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM fp_feedback").fetchone()
        return int(row["n"]) if row is not None else 0

    # ------------------------------------------------------------------
    # Suppressions (Layer 3)
    # ------------------------------------------------------------------

    def insert_suppression(
        self,
        *,
        name: str,
        match: dict[str, Any],
        fp_score: float,
        ttl_days: int | None,
        author: str = "anonymous",
        reason: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        suppression_id = str(uuid.uuid4())
        created = created_at or datetime.now(UTC)
        expires = (created + timedelta(days=int(ttl_days))) if ttl_days and ttl_days > 0 else None
        score = max(0.0, min(1.0, float(fp_score)))
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO suppressions
                    (suppression_id, name, match_json, fp_score,
                     ttl_days, author, reason, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    suppression_id,
                    name.strip(),
                    json.dumps(match, sort_keys=True),
                    score,
                    int(ttl_days) if ttl_days else None,
                    author,
                    reason,
                    created.isoformat(),
                    expires.isoformat() if expires else None,
                ),
            )
            self._conn.commit()
        return {
            "suppression_id": suppression_id,
            "name": name.strip(),
            "match": dict(match),
            "fp_score": score,
            "ttl_days": int(ttl_days) if ttl_days else None,
            "author": author,
            "reason": reason,
            "created_at": created.isoformat(),
            "expires_at": expires.isoformat() if expires else None,
        }

    def list_suppressions(
        self,
        *,
        include_expired: bool = False,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        ts = (now or datetime.now(UTC)).isoformat()
        with self._lock:
            if include_expired:
                rows = self._conn.execute(
                    "SELECT * FROM suppressions ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM suppressions "
                    "WHERE expires_at IS NULL OR expires_at > ? "
                    "ORDER BY created_at DESC",
                    (ts,),
                ).fetchall()
        return [_row_to_suppression(r) for r in rows]

    def get_suppression(self, suppression_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM suppressions WHERE suppression_id = ?",
                (suppression_id,),
            ).fetchone()
        return _row_to_suppression(row) if row is not None else None

    def delete_suppression(self, suppression_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM suppressions WHERE suppression_id = ?",
                (suppression_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def prune_expired(self, *, now: datetime | None = None) -> int:
        ts = (now or datetime.now(UTC)).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM suppressions WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (ts,),
            )
            self._conn.commit()
            return int(cur.rowcount)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def transaction(self) -> Iterable[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _row_to_feedback(row: sqlite3.Row) -> FeedbackRow:
    raw_features = row["features_json"] or "{}"
    try:
        features = json.loads(raw_features)
    except json.JSONDecodeError:
        features = {}
    return FeedbackRow(
        feedback_id=row["feedback_id"],
        incident_id=row["incident_id"],
        is_fp=bool(row["is_fp"]),
        reason=row["reason"],
        submitted_by=row["submitted_by"],
        submitted_at=_parse_iso(row["submitted_at"]),
        features=features if isinstance(features, dict) else {},
    )


def _row_to_suppression(row: sqlite3.Row) -> dict[str, Any]:
    raw_match = row["match_json"] or "{}"
    try:
        match = json.loads(raw_match)
    except json.JSONDecodeError:
        match = {}
    return {
        "suppression_id": row["suppression_id"],
        "name": row["name"],
        "match": match if isinstance(match, dict) else {},
        "fp_score": float(row["fp_score"]),
        "ttl_days": int(row["ttl_days"]) if row["ttl_days"] is not None else None,
        "author": row["author"],
        "reason": row["reason"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
    }


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Module-level singleton (mirror of ``app.store`` pattern)
# ---------------------------------------------------------------------------


_singleton: FeedbackDB | None = None
_singleton_lock = threading.Lock()


def get_feedback_db(path: str | Path | None = None) -> FeedbackDB:
    """Return a process-wide feedback DB.

    Defaults to an in-memory DB so the cockpit boots even on a brand-new
    container; production wires a real path via the ``TR1NITY_API_FP_DB``
    env var (see ``app.config``).
    """
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = FeedbackDB(path=path or ":memory:")
        return _singleton


def replace_feedback_db(db: FeedbackDB) -> None:
    """Test hook — swap the singleton."""
    global _singleton
    with _singleton_lock:
        if _singleton is not None and _singleton is not db:
            _singleton.close()
        _singleton = db
