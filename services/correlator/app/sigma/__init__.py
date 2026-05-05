"""TR1NITY's pragmatic SIGMA-style rule engine.

We deliberately do not depend on the upstream pySigma library yet — it
pulls a heavy backend ecosystem aimed at translating rules to vendor
query languages, which is wasted weight for our use case. We need
**in-process matching of YAML rules against in-memory ECS events**.
That is a few hundred lines, no native deps, easily testable, and it
keeps the door open for swapping in pySigma later.

Rules are written in a strict subset of the SIGMA spec:

* ``title``, ``id``, ``status``, ``description``, ``level`` (informational/
  low/medium/high/critical), ``tags`` (e.g. ``attack.t1110``).
* ``detection`` block with one or more named selections plus a
  ``condition`` that combines them with ``and`` / ``or`` / ``not`` / ``1 of``.
* Selections support equality and ``|contains`` / ``|startswith`` /
  ``|endswith`` / ``|re`` modifiers, and lists are treated as OR.

This is enough to match the SIGMA community-rules subset relevant to
SIEM/WAF/firewall ingest.
"""

from .engine import (
    SigmaEngine,
    SigmaMatch,
    SigmaRule,
    load_rules_from_dir,
)

__all__ = [
    "SigmaEngine",
    "SigmaMatch",
    "SigmaRule",
    "load_rules_from_dir",
]
