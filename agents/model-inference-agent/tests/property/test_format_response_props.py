"""
Property-based tests for format_response tool.

Feature: healthcare-agent-v2
Properties 7, 8, 9, 10.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.tools.format_response import (
    compute_confidence, compute_consistency,
    format_response, build_contributing_factors,
)

probs = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

fi_dicts = st.dictionaries(
    keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=2, max_size=12),
    values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    min_size=0, max_size=20,
)


def _primary(prob, fi=None):
    d = {"model_name": "autogluon", "probability": prob, "inference_time_ms": 50.0}
    if fi:
        d["feature_importance"] = fi
    return d


def _secondary(prob):
    return {"model_name": "tabpfn", "probability": prob, "inference_time_ms": 80.0}


# ── Property 7: Confidence level computation ──────────────────
# Feature: healthcare-agent-v2, Property 7: Confidence level computation
# **Validates: Requirements 6.1**

@given(p=probs)
@settings(max_examples=200)
def test_confidence_thresholds(p):
    c = compute_confidence(p)
    if p >= 0.75:
        assert c == "HIGH"
    elif p >= 0.50:
        assert c == "MEDIUM"
    else:
        assert c == "LOW"


# ── Property 8: Consistency rating computation ────────────────
# Feature: healthcare-agent-v2, Property 8: Consistency rating
# **Validates: Requirements 6.2**

@given(p1=probs, p2=probs)
@settings(max_examples=200)
def test_consistency_thresholds(p1, p2):
    c = compute_consistency(p1, p2)
    diff = abs(p1 - p2)
    if diff <= 0.15:
        assert c == "CONSISTENT"
    else:
        assert c == "DIVERGENT"


# ── Property 9: Response output completeness ──────────────────
# Feature: healthcare-agent-v2, Property 9: Response output completeness
# **Validates: Requirements 6.3, 6.4**

REQUIRED_FIELDS = [
    "patient_id", "disease", "primary_model", "primary_probability",
    "confidence", "disclaimer", "summary", "model_evaluation",
]


@given(p=probs)
@settings(max_examples=200)
def test_response_completeness(p):
    """For any valid inputs, format_response returns all required fields
    and disclaimer is non-empty."""
    r = format_response(
        patient_id="test-001",
        disease_display="Stroke",
        primary=_primary(p),
        secondary=None,
        primary_f1=1.0,
    )
    for field in REQUIRED_FIELDS:
        assert field in r, f"Missing field: {field}"
    assert len(r["disclaimer"]) > 0
    assert len(r["summary"]) > 0


@given(p1=probs, p2=probs)
@settings(max_examples=200)
def test_response_completeness_with_secondary(p1, p2):
    """With secondary model, all fields present plus secondary fields."""
    r = format_response(
        patient_id="test-002",
        disease_display="Hypertension",
        primary=_primary(p1),
        secondary=_secondary(p2),
        primary_f1=0.909,
        secondary_f1=0.833,
    )
    for field in REQUIRED_FIELDS:
        assert field in r
    assert r["secondary_model"] == "tabpfn"
    assert r["secondary_probability"] == p2
    assert r["consistency"] in ("CONSISTENT", "DIVERGENT")


# ── Property 10: Contributing factors bounded ─────────────────
# Feature: healthcare-agent-v2, Property 10: Contributing factors bounded
# **Validates: Requirements 6.5**

@given(fi=fi_dicts)
@settings(max_examples=200)
def test_contributing_factors_max_5(fi):
    """For any feature importance dict, contributing_factors has at most 5."""
    factors = build_contributing_factors(fi)
    assert len(factors) <= 5


@given(fi=fi_dicts, p=probs)
@settings(max_examples=100)
def test_factors_in_full_response(fi, p):
    """Contributing factors in full response are bounded at 5."""
    r = format_response(
        patient_id="test-003",
        disease_display="Stroke",
        primary=_primary(p, fi if fi else None),
        secondary=None,
        primary_f1=1.0,
    )
    assert len(r["contributing_factors"]) <= 5
