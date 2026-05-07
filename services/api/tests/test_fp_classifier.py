"""Tests for the Layer-2 classifier wrapper."""

from __future__ import annotations

from pathlib import Path

from app.fp.classifier import FPClassifier
from app.fp.features import extract_features


def test_predict_falls_back_to_zero_when_no_model() -> None:
    clf = FPClassifier(model_path=Path("/nonexistent/no-model.pkl"))
    incident = {"incident_id": "i", "severity": 4, "members": [{"source_ip": "1.2.3.4"}]}
    assert clf.available is False
    assert clf.predict_fp_probability(incident) == 0.0


def test_status_reports_unavailable_with_reason() -> None:
    clf = FPClassifier(model_path=None)
    status = clf.status()
    assert status.available is False
    assert "no model" in status.reason


def test_features_have_stable_shape_for_random_incidents() -> None:
    incident = {
        "incident_id": "i",
        "severity": 5,
        "sources": ["firewall", "waf"],
        "technique_ids": ["T1110.001"],
        "sigma_matches": [{"id": "x"}],
        "intel_hits": [{"ioc": "1.2.3.4"}],
        "members": [
            {
                "source_ip": "10.0.0.5",
                "user": {"name": "alice"},
                "destination": {"ip": "10.0.0.10"},
            },
        ],
        "last_event_at": "2024-01-01T05:00:00Z",
    }
    features = extract_features(incident)
    assert features["severity"] == 5.0
    assert features["source_count"] == 2.0
    assert features["technique_count"] == 1.0
    assert features["is_internal_source"] == 1.0
    assert features["has_user"] == 1.0
    assert features["has_destination"] == 1.0
    # All features must be floats so the classifier can vectorise them.
    for name, value in features.items():
        assert isinstance(value, float), f"feature {name} is not a float"
