"""MITRE ATT&CK chain promotion + tactic ordering.

The grouping layer collects technique IDs verbatim from member events.
This module turns that flat set into something analyst-friendly:

* Resolves each technique to its tactic so we can render the kill-chain
  ("Recon → Initial Access → Credential Access").
* Orders tactics by a canonical kill-chain sequence so two incidents
  with the same techniques always render identically.
* Looks up human-readable names for technique IDs we know about.

The lookup table is intentionally **not** a full ATT&CK Enterprise
import — that would balloon the repo and lock us to one matrix version.
We embed only the techniques TR1NITY's ingestor parsers can emit (Wazuh,
firewall, ModSec WAF), plus a small handful of common ones the SIGMA
rule pack will reference. Adding a new technique is one tuple here.
"""

from __future__ import annotations

from typing import Final

# Canonical kill-chain order (Enterprise matrix).
TACTIC_ORDER: Final[list[str]] = [
    "TA0043",  # Reconnaissance
    "TA0042",  # Resource Development
    "TA0001",  # Initial Access
    "TA0002",  # Execution
    "TA0003",  # Persistence
    "TA0004",  # Privilege Escalation
    "TA0005",  # Defense Evasion
    "TA0006",  # Credential Access
    "TA0007",  # Discovery
    "TA0008",  # Lateral Movement
    "TA0009",  # Collection
    "TA0011",  # Command and Control
    "TA0010",  # Exfiltration
    "TA0040",  # Impact
]

TACTIC_NAMES: Final[dict[str, str]] = {
    "TA0043": "Reconnaissance",
    "TA0042": "Resource Development",
    "TA0001": "Initial Access",
    "TA0002": "Execution",
    "TA0003": "Persistence",
    "TA0004": "Privilege Escalation",
    "TA0005": "Defense Evasion",
    "TA0006": "Credential Access",
    "TA0007": "Discovery",
    "TA0008": "Lateral Movement",
    "TA0009": "Collection",
    "TA0011": "Command and Control",
    "TA0010": "Exfiltration",
    "TA0040": "Impact",
}

# Technique -> (name, primary tactic). Trimmed to what TR1NITY actually emits.
TECHNIQUE_INDEX: Final[dict[str, tuple[str, str]]] = {
    # Reconnaissance
    "T1595": ("Active Scanning", "TA0043"),
    "T1592": ("Gather Victim Host Information", "TA0043"),
    # Initial Access
    "T1190": ("Exploit Public-Facing Application", "TA0001"),
    "T1133": ("External Remote Services", "TA0001"),
    # Execution / Command-and-Control
    "T1059": ("Command and Scripting Interpreter", "TA0002"),
    "T1071": ("Application Layer Protocol", "TA0011"),
    # Credential Access
    "T1110": ("Brute Force", "TA0006"),
    "T1110.001": ("Brute Force: Password Guessing", "TA0006"),
    "T1110.003": ("Brute Force: Password Spraying", "TA0006"),
    # T1078 (Valid Accounts) is a multi-tactic technique in ATT&CK
    # (Defense Evasion / Initial Access / Persistence / Privilege Escalation).
    # In our SOC narrative it always shows up *after* a successful brute-force
    # — i.e. the attacker now has working credentials and is using them to get
    # in — so we map it to the Initial Access tactic (TA0001), not Credential
    # Access (TA0006), which is reserved for techniques that *obtain* creds.
    "T1078": ("Valid Accounts", "TA0001"),
    # Defense Evasion
    "T1027": ("Obfuscated Files or Information", "TA0005"),
    # Discovery
    "T1046": ("Network Service Discovery", "TA0007"),
    # Impact
    "T1486": ("Data Encrypted for Impact", "TA0040"),
    # WAF-flavored
    "T1083": ("File and Directory Discovery", "TA0007"),
    "T1505": ("Server Software Component", "TA0003"),
}


def technique_name(technique_id: str) -> str | None:
    entry = TECHNIQUE_INDEX.get(technique_id)
    return entry[0] if entry else None


def tactic_for(technique_id: str) -> str | None:
    """Return the primary tactic ID for a technique, or ``None`` if unknown."""
    entry = TECHNIQUE_INDEX.get(technique_id)
    return entry[1] if entry else None


def order_tactics(tactic_ids: list[str]) -> list[str]:
    """Return ``tactic_ids`` sorted by canonical kill-chain order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for t in tactic_ids:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    rank = {t: i for i, t in enumerate(TACTIC_ORDER)}
    # Unknown tactics sort to the end, in input order.
    return sorted(deduped, key=lambda t: rank.get(t, len(TACTIC_ORDER) + deduped.index(t)))


def order_techniques(technique_ids: list[str]) -> list[str]:
    """Return techniques sorted by their tactic's kill-chain position."""
    seen: set[str] = set()
    deduped: list[str] = []
    for t in technique_ids:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    rank = {t: i for i, t in enumerate(TACTIC_ORDER)}

    def key(tech: str) -> tuple[int, str]:
        tac = tactic_for(tech)
        return (rank.get(tac or "", len(TACTIC_ORDER)), tech)

    return sorted(deduped, key=key)


def render_chain(technique_ids: list[str]) -> str:
    """Render a human-readable kill-chain string.

    e.g. ``"Recon (T1595) → Initial Access (T1190) → Brute Force (T1110)"``.
    Unknown technique IDs are kept verbatim so a Sigma-tagged technique
    we have not added to TECHNIQUE_INDEX yet still renders.
    """
    if not technique_ids:
        return ""
    ordered = order_techniques(technique_ids)
    parts: list[str] = []
    for tid in ordered:
        name = technique_name(tid)
        parts.append(f"{name} ({tid})" if name else tid)
    return " → ".join(parts)


def chain_metadata(technique_ids: list[str]) -> dict[str, list[str]]:
    """Return ordered technique IDs + tactic IDs for an Incident."""
    ordered_techniques = order_techniques(technique_ids)
    tactics: list[str] = []
    for tid in ordered_techniques:
        tac = tactic_for(tid)
        if tac and tac not in tactics:
            tactics.append(tac)
    return {
        "technique_ids": ordered_techniques,
        "tactic_ids": order_tactics(tactics),
    }
