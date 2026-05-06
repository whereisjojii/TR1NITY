"""Incident-domain helpers shared across routers.

The api never owns incidents — the correlator does. This module hosts
the *composition* helpers that take raw incident dicts (from the
correlator's in-memory cache + the api's recent-buffer + OpenSearch) and
shape them for the Cockpit:

- ``compose_incidents``: dedupe, attach FP score, sort.
- ``compute_attack_heatmap``: roll up technique frequencies into the
  Navigator-style heatmap payload.
- ``rank_similar``: compute a deterministic Phase-3 similarity score so
  the "similar past incidents" panel works before ChromaDB lands in
  Phase 5.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from .store import CockpitStore

log = logging.getLogger(__name__)


SortKey = Literal["fp_score", "severity", "created_at", "last_event_at"]


# ---------------------------------------------------------------------------
# Composition (queue listing)
# ---------------------------------------------------------------------------


def compose_incidents(
    *,
    correlator_items: Iterable[dict[str, Any]] | None,
    cached_items: Iterable[dict[str, Any]] | None,
    opensearch_items: Iterable[dict[str, Any]] | None,
    store: CockpitStore,
    sort_by: SortKey = "fp_score",
    descending: bool = False,
    severity_min: int | None = None,
    sources: list[str] | None = None,
    technique: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Merge incident sources, dedupe by ``incident_id``, sort + filter.

    Sort default is ``fp_score`` ascending — the Cockpit alert queue
    surfaces the **most likely true positives** first. The roadmap is
    explicit about this and the UI relies on it.
    """
    merged: dict[str, dict[str, Any]] = {}

    # Order matters: we want correlator (freshest in-memory tick) to win
    # over the api's recent buffer to win over OpenSearch (oldest, but
    # most durable). Loops below merge later sources only when an id is
    # still missing.
    for source in (correlator_items, cached_items, opensearch_items):
        if not source:
            continue
        for raw in source:
            if not isinstance(raw, dict):
                continue
            iid = raw.get("incident_id")
            if not isinstance(iid, str) or not iid:
                continue
            if iid in merged:
                continue
            merged[iid] = dict(raw)

    out: list[dict[str, Any]] = []
    for raw in merged.values():
        decorated = _decorate(raw, store)
        if severity_min is not None and decorated.get("severity", 0) < severity_min:
            continue
        if sources is not None:
            inc_sources = decorated.get("sources") or []
            if not isinstance(inc_sources, list):
                inc_sources = []
            if not set(inc_sources).intersection(sources):
                continue
        if technique is not None:
            techniques = decorated.get("technique_ids") or []
            if not isinstance(techniques, list) or technique not in techniques:
                continue
        out.append(decorated)

    out.sort(
        key=lambda inc: _sort_value(inc, sort_by),
        reverse=descending,
    )

    if limit is not None and limit > 0:
        out = out[:limit]
    return out


def _decorate(raw: dict[str, Any], store: CockpitStore) -> dict[str, Any]:
    """Attach analyst-derived fields the api owns."""
    iid = raw.get("incident_id")
    score = store.fp_score(iid) if isinstance(iid, str) and iid else 0.5
    raw["fp_score"] = score
    fb = store.get_fp(iid) if isinstance(iid, str) and iid else None
    raw["fp_feedback"] = fb.to_dict() if fb is not None else None
    return raw


def _sort_value(inc: dict[str, Any], key: SortKey) -> float:
    if key == "fp_score":
        return float(inc.get("fp_score", 0.5))
    if key == "severity":
        return float(inc.get("severity", 0))
    if key in {"created_at", "last_event_at"}:
        ts = inc.get(key)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0
        if isinstance(ts, int | float):
            return float(ts)
        return 0.0
    return 0.0


# ---------------------------------------------------------------------------
# ATT&CK heatmap
# ---------------------------------------------------------------------------


def compute_attack_heatmap(incidents: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate technique frequencies for the Navigator-style heatmap.

    Output shape mirrors the analytics card the React UI consumes:

        {
          "techniques": [
            {"id": "T1190", "count": 12, "tactics": ["TA0001"]},
            ...
          ],
          "tactics": [
            {"id": "TA0001", "count": 12},
            ...
          ],
          "total_incidents": 17,
          "covered_incidents": 14
        }
    """
    technique_counts: dict[str, int] = {}
    technique_tactics: dict[str, set[str]] = {}
    tactic_counts: dict[str, int] = {}
    total = 0
    covered = 0

    for inc in incidents:
        if not isinstance(inc, dict):
            continue
        total += 1
        techs = inc.get("technique_ids") or []
        tactics = inc.get("tactic_ids") or []
        if isinstance(techs, list) and any(isinstance(t, str) and t for t in techs):
            covered += 1
        if isinstance(techs, list):
            for t in techs:
                if isinstance(t, str) and t:
                    technique_counts[t] = technique_counts.get(t, 0) + 1
                    technique_tactics.setdefault(t, set())
        if isinstance(tactics, list):
            for ta in tactics:
                if isinstance(ta, str) and ta:
                    tactic_counts[ta] = tactic_counts.get(ta, 0) + 1
            if isinstance(techs, list):
                for t in techs:
                    if isinstance(t, str) and t:
                        for ta in tactics:
                            if isinstance(ta, str) and ta:
                                technique_tactics.setdefault(t, set()).add(ta)

    techniques = [
        {
            "id": tid,
            "count": count,
            "tactics": sorted(technique_tactics.get(tid, set())),
        }
        for tid, count in technique_counts.items()
    ]
    techniques.sort(key=lambda x: (-x["count"], x["id"]))
    tactics = [{"id": ta, "count": c} for ta, c in tactic_counts.items()]
    tactics.sort(key=lambda x: (-x["count"], x["id"]))

    return {
        "techniques": techniques,
        "tactics": tactics,
        "total_incidents": total,
        "covered_incidents": covered,
    }


# ---------------------------------------------------------------------------
# Similar incidents (Phase 3 heuristic)
# ---------------------------------------------------------------------------


def rank_similar(
    target: dict[str, Any],
    candidates: Iterable[dict[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the most-similar candidates to ``target``.

    The Phase-3 heuristic is intentionally simple and deterministic:

    1. **Source IP overlap** — exact-match shared source IP across
       members is worth +0.5.
    2. **ATT&CK technique overlap** — Jaccard similarity over technique
       IDs, scaled by 0.4.
    3. **Sources overlap** — Jaccard over the incident's ``sources``
       list (wazuh / firewall / waf), scaled by 0.1.

    Phase 5 swaps the body of this function for a ChromaDB cosine
    similarity over incident embeddings — the *interface* (and the
    field names emitted) stay identical so the React component does
    not need to change.
    """
    if not isinstance(target, dict):
        return []
    target_id = target.get("incident_id")
    target_techs = _safe_str_list(target.get("technique_ids"))
    target_sources = _safe_str_list(target.get("sources"))
    target_ips = _member_source_ips(target)

    scored: list[tuple[float, dict[str, Any]]] = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        if cand.get("incident_id") == target_id:
            continue
        cand_techs = _safe_str_list(cand.get("technique_ids"))
        cand_sources = _safe_str_list(cand.get("sources"))
        cand_ips = _member_source_ips(cand)

        score = 0.0
        if target_ips and cand_ips and target_ips.intersection(cand_ips):
            score += 0.5
        score += 0.4 * _jaccard(target_techs, cand_techs)
        score += 0.1 * _jaccard(target_sources, cand_sources)
        if score <= 0:
            continue

        cand_with_score = dict(cand)
        cand_with_score["similarity_score"] = round(score, 4)
        scored.append((score, cand_with_score))

    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("incident_id", ""))))
    return [item for _, item in scored[: max(0, limit)]]


def _safe_str_list(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {v for v in value if isinstance(v, str) and v}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _member_source_ips(incident: dict[str, Any]) -> set[str]:
    members = incident.get("members") or []
    if not isinstance(members, list):
        return set()
    out: set[str] = set()
    for m in members:
        if not isinstance(m, dict):
            continue
        ip = m.get("source_ip")
        if isinstance(ip, str) and ip:
            out.add(ip)
    return out
