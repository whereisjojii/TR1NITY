"""SIGMA rule engine — strict subset, in-process, pure Python.

See ``sigma/__init__.py`` for the design rationale. This file owns the
parser, the matcher, and a small directory loader. No I/O at match
time — once rules are loaded, matching is pure-data and side-effect
free, which makes it trivially safe to call in a hot loop.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

# Mapping of free-form SIGMA "level" to TR1NITY's 0-7 ECS severity scale.
# Conservative: we never push above 7.
SIGMA_LEVEL_TO_ECS_SEVERITY: dict[str, int] = {
    "informational": 0,
    "low": 2,
    "medium": 4,
    "high": 6,
    "critical": 7,
}


@dataclass(frozen=True, slots=True)
class SigmaMatch:
    """A single rule firing against a single event."""

    rule_id: str
    rule_title: str
    level: str
    severity: int
    tags: tuple[str, ...]


@dataclass(slots=True)
class _Selection:
    """Compiled form of a single named SIGMA selection."""

    fields: list[tuple[str, str, list[Any]]]
    # Each tuple: (dotted_field_path, operator, list_of_expected_values)


@dataclass(slots=True)
class SigmaRule:
    """A compiled SIGMA rule ready to match against events.

    We intentionally store the raw dict for inspection / round-trip,
    but matching uses only the compiled selections + condition string.
    """

    raw: dict[str, Any]
    rule_id: str
    title: str
    level: str
    tags: tuple[str, ...]
    selections: dict[str, _Selection]
    condition: str

    @property
    def severity(self) -> int:
        return SIGMA_LEVEL_TO_ECS_SEVERITY.get(self.level.lower(), 0)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _compile_selection(name: str, body: dict[str, Any]) -> _Selection:
    """Turn one SIGMA selection block into a compiled ``_Selection``.

    SIGMA syntax: each key is a (possibly modifier-suffixed) field path,
    each value is a single value or a list (treated as OR). Supported
    modifiers: ``contains``, ``startswith``, ``endswith``, ``re``. Bare
    keys mean ``equals``.
    """
    if not isinstance(body, dict):
        raise ValueError(f"SIGMA selection '{name}' must be a mapping, got {type(body).__name__}")
    fields: list[tuple[str, str, list[Any]]] = []
    for key, value in body.items():
        op = "eq"
        path = key
        if "|" in key:
            path, _, modifier = key.partition("|")
            modifier = modifier.lower().strip()
            if modifier in {"contains", "startswith", "endswith", "re"}:
                op = modifier
            else:
                raise ValueError(f"SIGMA selection '{name}': unsupported modifier '{modifier}'")
        values = value if isinstance(value, list) else [value]
        fields.append((path.strip(), op, list(values)))
    return _Selection(fields=fields)


def _parse_rule(doc: dict[str, Any], *, source_path: str | None = None) -> SigmaRule:
    """Compile a single YAML doc into a SigmaRule."""
    if "title" not in doc:
        raise ValueError(f"SIGMA rule missing 'title' (source={source_path})")
    if "detection" not in doc:
        raise ValueError(f"SIGMA rule '{doc.get('title')}' missing 'detection' block")

    detection = doc["detection"]
    if not isinstance(detection, dict):
        raise ValueError(f"SIGMA rule '{doc.get('title')}' detection must be mapping")
    if "condition" not in detection:
        raise ValueError(f"SIGMA rule '{doc.get('title')}' missing detection.condition")

    selections: dict[str, _Selection] = {}
    for sel_name, sel_body in detection.items():
        if sel_name == "condition":
            continue
        selections[sel_name] = _compile_selection(sel_name, sel_body)

    tags = doc.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    return SigmaRule(
        raw=doc,
        rule_id=str(doc.get("id") or doc["title"]),
        title=str(doc["title"]),
        level=str(doc.get("level") or "low"),
        tags=tuple(str(t) for t in tags),
        selections=selections,
        condition=str(detection["condition"]).strip(),
    )


def _parse_yaml_text(text: str, *, source_path: str | None = None) -> list[SigmaRule]:
    """Parse a YAML stream that may contain one or many rule docs."""
    docs = list(yaml.safe_load_all(text))
    rules: list[SigmaRule] = []
    for doc in docs:
        if not doc:
            continue
        if not isinstance(doc, dict):
            log.warning("SIGMA loader: skipping non-mapping doc in %s", source_path)
            continue
        rules.append(_parse_rule(doc, source_path=source_path))
    return rules


def load_rules_from_dir(directory: str | Path) -> list[SigmaRule]:
    """Load every ``*.yml`` / ``*.yaml`` file under ``directory``.

    Missing directory → empty list (no exception). This lets a deployment
    ship without rules and still boot.
    """
    base = Path(directory)
    if not base.is_dir():
        log.info("SIGMA loader: rule dir %s does not exist; no rules loaded", base)
        return []
    # ``*.y*ml`` would also match e.g. ``*.yyml`` / ``*.yzzzml`` — explicit
    # extensions only, deduplicated since one file can't be both.
    paths: set[Path] = set()
    for pattern in ("*.yml", "*.yaml"):
        paths.update(base.rglob(pattern))
    out: list[SigmaRule] = []
    for path in sorted(paths):
        try:
            text = path.read_text(encoding="utf-8")
            out.extend(_parse_yaml_text(text, source_path=str(path)))
        except Exception:  # pragma: no cover — file-system flake
            log.exception("SIGMA loader: failed to parse %s", path)
    log.info("SIGMA loader: %d rules from %s", len(out), base)
    return out


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _resolve_path(event: dict[str, Any], dotted: str) -> Any:
    """Walk ``event`` along a dotted path. Returns ``None`` if missing."""
    cur: Any = event
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def _value_matches(actual: Any, op: str, expected: Any) -> bool:
    """Compare one actual scalar against one expected scalar by op.

    ``actual`` may be a scalar OR a list (lists are treated as OR over
    elements — ECS often stores e.g. ``event.category`` as a list).
    """
    if isinstance(actual, list):
        return any(_value_matches(item, op, expected) for item in actual)

    if actual is None:
        return False

    if op == "eq":
        # Coerce to string for comparison so 200 == "200" works (common
        # source of false negatives in SIGMA-against-JSON matching).
        return str(actual) == str(expected)

    actual_s = str(actual)
    expected_s = str(expected)
    if op == "contains":
        return expected_s.casefold() in actual_s.casefold()
    if op == "startswith":
        return actual_s.casefold().startswith(expected_s.casefold())
    if op == "endswith":
        return actual_s.casefold().endswith(expected_s.casefold())
    if op == "re":
        try:
            return re.search(expected_s, actual_s, flags=re.IGNORECASE) is not None
        except re.error:
            log.warning("SIGMA: bad regex %r in rule selection", expected_s)
            return False
    return False


def _selection_matches(event: dict[str, Any], sel: _Selection) -> bool:
    """All fields in a selection must match (AND), each field's value
    list is OR'd."""
    for path, op, values in sel.fields:
        actual = _resolve_path(event, path)
        if not any(_value_matches(actual, op, exp) for exp in values):
            return False
    return True


# Tokens we recognize in the condition string.
_CONDITION_TOKEN = re.compile(r"\(|\)|\band\b|\bor\b|\bnot\b|\b1 of\b|[A-Za-z_][A-Za-z0-9_*]*")


def _eval_condition(
    condition: str,
    selections: dict[str, _Selection],
    event: dict[str, Any],
) -> bool:
    """Evaluate the SIGMA condition expression against ``event``.

    Supports: ``and``, ``or``, ``not``, parentheses, ``1 of <prefix>*``,
    and bare selection names. Anything else raises ``ValueError`` at
    rule-compile time, not match time, so we never silently swallow a
    typo'd condition.
    """
    tokens = _CONDITION_TOKEN.findall(condition)
    if not tokens:
        raise ValueError(f"SIGMA: empty condition: {condition!r}")

    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def consume() -> str:
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def parse_or() -> bool:
        left = parse_and()
        while peek() == "or":
            consume()
            right = parse_and()
            left = left or right
        return left

    def parse_and() -> bool:
        left = parse_unary()
        while peek() == "and":
            consume()
            right = parse_unary()
            left = left and right
        return left

    def parse_unary() -> bool:
        if peek() == "not":
            consume()
            return not parse_unary()
        return parse_atom()

    def parse_atom() -> bool:
        tok = peek()
        if tok is None:
            raise ValueError(f"SIGMA: unexpected end of condition: {condition!r}")
        if tok == "(":
            consume()
            value = parse_or()
            if peek() != ")":
                raise ValueError(f"SIGMA: missing ')' in {condition!r}")
            consume()
            return value
        if tok == "1 of":
            consume()
            target = consume()
            return _one_of(target, selections, event)
        consume()
        sel = selections.get(tok)
        if sel is None:
            raise ValueError(f"SIGMA: unknown selection {tok!r} in condition {condition!r}")
        return _selection_matches(event, sel)

    result = parse_or()
    if pos != len(tokens):
        raise ValueError(f"SIGMA: trailing tokens in condition {condition!r}")
    return result


def _one_of(
    target: str,
    selections: dict[str, _Selection],
    event: dict[str, Any],
) -> bool:
    """Implement ``1 of selection*`` (or ``1 of them``)."""
    if target == "them":
        names = list(selections)
    elif target.endswith("*"):
        prefix = target[:-1]
        names = [n for n in selections if n.startswith(prefix)]
    else:
        names = [target] if target in selections else []
    return any(_selection_matches(event, selections[name]) for name in names)


# ---------------------------------------------------------------------------
# Engine facade
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SigmaEngine:
    """Small façade: hold a list of compiled rules, match events against them."""

    rules: list[SigmaRule] = field(default_factory=list)

    def match(self, event: dict[str, Any]) -> list[SigmaMatch]:
        """Return every rule that fires for ``event``."""
        out: list[SigmaMatch] = []
        for rule in self.rules:
            try:
                if _eval_condition(rule.condition, rule.selections, event):
                    out.append(
                        SigmaMatch(
                            rule_id=rule.rule_id,
                            rule_title=rule.title,
                            level=rule.level,
                            severity=rule.severity,
                            tags=rule.tags,
                        )
                    )
            except Exception:
                # A buggy/unparseable rule must not take down the whole
                # batch — log and move on. ValueError is the typical
                # case from the parser, but a malformed event can also
                # surface IndexError / KeyError / TypeError from the
                # field walker, and we do not want any of those to drop
                # remaining rules in the loop.
                log.exception("SIGMA: rule %s evaluation error", rule.rule_id)
        return out
