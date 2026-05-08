"""Runbook library — markdown files indexed by ATT&CK technique.

The fp-handling design + ROADMAP commit Phase 4 to ship at least 15
markdown runbooks so analysts have a clear "what do I do next" for
common ATT&CK techniques. Files live under ``docs/runbooks/`` and ship
in the repo so they're version-controlled, code-reviewable, and easy
to extend without redeploying.

Each file starts with a YAML frontmatter block:

    ---
    technique: T1110.001
    tactic: TA0006
    severity: high
    title: Brute-force authentication (Password Guessing)
    references:
      - https://attack.mitre.org/techniques/T1110/001/
    ---
    # Triage
    ...

The api exposes the index and individual runbooks via
``GET /api/runbooks`` and ``GET /api/runbooks/{technique_id}`` and
attaches the matching ``runbook_url`` to every served incident.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

DEFAULT_RUNBOOKS_DIR = Path(__file__).resolve().parents[3] / "docs" / "runbooks"
SEVERITY_RANK = {"info": 0, "low": 2, "medium": 4, "high": 6, "critical": 7}


@dataclass(slots=True, frozen=True)
class Runbook:
    """One parsed markdown runbook."""

    technique_id: str
    tactic_id: str | None
    title: str
    severity: str
    body: str
    references: tuple[str, ...] = ()
    path: str = ""

    def to_summary(self) -> dict[str, Any]:
        return {
            "technique_id": self.technique_id,
            "tactic_id": self.tactic_id,
            "title": self.title,
            "severity": self.severity,
            "url": f"/api/runbooks/{self.technique_id}",
            "references": list(self.references),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.to_summary(),
            "body": self.body,
        }


@dataclass(slots=True)
class RunbookLibrary:
    """Lazy, thread-safe, in-process index of runbooks."""

    runbooks_dir: Path
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _by_technique: dict[str, Runbook] = field(default_factory=dict)
    _loaded_at: datetime | None = None

    def load(self, *, force: bool = False) -> int:
        """Walk the runbooks directory and parse every ``*.md`` file."""
        with self._lock:
            if self._loaded_at is not None and not force:
                return len(self._by_technique)
            self._by_technique.clear()
            if not self.runbooks_dir.exists():
                log.info(
                    "Runbooks dir %s does not exist — runbook library empty.",
                    self.runbooks_dir,
                )
                self._loaded_at = datetime.now(UTC)
                return 0
            for path in sorted(self.runbooks_dir.glob("*.md")):
                if path.name.lower() == "readme.md":
                    continue
                try:
                    runbook = parse_runbook(path)
                except ValueError as exc:
                    log.warning("Skipping malformed runbook %s: %s", path, exc)
                    continue
                self._by_technique[runbook.technique_id] = runbook
            self._loaded_at = datetime.now(UTC)
            return len(self._by_technique)

    def list_summaries(self) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_loaded()
            summaries = [r.to_summary() for r in self._by_technique.values()]
        summaries.sort(
            key=lambda s: (
                -int(SEVERITY_RANK.get(str(s.get("severity", "")).lower(), 0)),
                str(s.get("technique_id")),
            )
        )
        return summaries

    def get(self, technique_id: str) -> Runbook | None:
        with self._lock:
            self._ensure_loaded()
            direct = self._by_technique.get(technique_id)
            if direct is not None:
                return direct
            # Fall back to the parent technique (e.g. T1110.001 → T1110)
            # so a sub-technique still surfaces a useful runbook.
            if "." in technique_id:
                parent = technique_id.split(".")[0]
                return self._by_technique.get(parent)
            return None

    def primary_runbook_url(self, technique_ids: list[str]) -> str | None:
        with self._lock:
            self._ensure_loaded()
            for tid in technique_ids:
                runbook = self.get(tid)
                if runbook is not None:
                    return f"/api/runbooks/{runbook.technique_id}"
        return None

    def reload(self) -> int:
        return self.load(force=True)

    def _ensure_loaded(self) -> None:
        if self._loaded_at is None:
            self.load()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_runbook(path: Path) -> Runbook:
    """Parse a markdown file with a YAML frontmatter into a :class:`Runbook`."""
    text = path.read_text(encoding="utf-8")
    front, body = _split_frontmatter(text)
    if front is None:
        raise ValueError(f"missing YAML frontmatter in {path.name}")
    try:
        meta = yaml.safe_load(front) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"bad YAML frontmatter in {path.name}: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"frontmatter in {path.name} must be a mapping")
    technique_id = str(meta.get("technique") or "").strip()
    if not technique_id:
        raise ValueError(f"runbook {path.name} missing required key: technique")
    refs_raw = meta.get("references") or []
    refs = tuple(str(r) for r in refs_raw if r) if isinstance(refs_raw, list) else ()
    return Runbook(
        technique_id=technique_id,
        tactic_id=str(meta["tactic"]).strip() if meta.get("tactic") else None,
        title=str(meta.get("title") or technique_id).strip(),
        severity=str(meta.get("severity") or "medium").strip().lower(),
        body=body.strip(),
        references=refs,
        path=str(path),
    )


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    return parts[1].strip(), parts[2]


# ---------------------------------------------------------------------------
# Singleton + helpers
# ---------------------------------------------------------------------------


_singleton: RunbookLibrary | None = None
_singleton_lock = threading.Lock()


def get_runbook_library(runbooks_dir: Path | str | None = None) -> RunbookLibrary:
    """Return the process-wide runbook library."""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            target_dir = Path(runbooks_dir) if runbooks_dir else DEFAULT_RUNBOOKS_DIR
            _singleton = RunbookLibrary(runbooks_dir=target_dir)
        return _singleton


def replace_runbook_library(library: RunbookLibrary) -> None:
    """Test hook — swap the singleton."""
    global _singleton
    with _singleton_lock:
        _singleton = library
