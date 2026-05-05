"""ATT&CK chain promotion + ordering tests."""

from __future__ import annotations

from app.attack import (
    chain_metadata,
    order_tactics,
    order_techniques,
    render_chain,
    tactic_for,
    technique_name,
)


def test_known_techniques_resolve_to_names_and_tactics() -> None:
    assert technique_name("T1110") == "Brute Force"
    assert tactic_for("T1110") == "TA0006"


def test_unknown_technique_is_passed_through() -> None:
    assert technique_name("T9999") is None
    assert tactic_for("T9999") is None


def test_tactic_order_matches_kill_chain() -> None:
    # Recon → Initial Access → Credential Access
    ordered = order_tactics(["TA0006", "TA0001", "TA0043"])
    assert ordered == ["TA0043", "TA0001", "TA0006"]


def test_techniques_sorted_by_their_tactic_position() -> None:
    techniques = ["T1110", "T1190", "T1595"]  # cred-access, initial, recon
    ordered = order_techniques(techniques)
    assert ordered == ["T1595", "T1190", "T1110"]


def test_render_chain_renders_human_readable_string() -> None:
    chain = render_chain(["T1110", "T1190", "T1595"])
    assert "Active Scanning (T1595)" in chain
    assert "Exploit Public-Facing Application (T1190)" in chain
    assert "Brute Force (T1110)" in chain
    parts = [p.strip() for p in chain.split("→")]
    assert parts[0].startswith("Active Scanning")
    assert parts[-1].startswith("Brute Force")


def test_render_chain_keeps_unknown_techniques_verbatim() -> None:
    chain = render_chain(["T9999"])
    assert chain == "T9999"


def test_chain_metadata_returns_ordered_unique_lists() -> None:
    meta = chain_metadata(["T1110", "T1110", "T1190"])
    assert meta["technique_ids"] == ["T1190", "T1110"]
    assert meta["tactic_ids"] == ["TA0001", "TA0006"]


def test_chain_metadata_handles_empty_input() -> None:
    meta = chain_metadata([])
    assert meta == {"technique_ids": [], "tactic_ids": []}
