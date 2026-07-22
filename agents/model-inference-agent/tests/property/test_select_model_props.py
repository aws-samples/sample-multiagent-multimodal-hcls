"""
Property-based tests for select_model tool.

Feature: healthcare-agent-v2
Property 5: Model selection is deterministic and complete.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.tools.select_model import select_model
from src.config import DISEASE_CONFIG, BENCHMARK_F1


disease_targets = st.sampled_from(list(DISEASE_CONFIG.keys()))


# ── Property 5: Model selection is deterministic and complete ─
# Feature: healthcare-agent-v2, Property 5: Model selection is
# deterministic and complete
# **Validates: Requirements 4.1, 4.4**

@given(target=disease_targets)
@settings(max_examples=200)
def test_select_model_deterministic_and_complete(target):
    """For any valid disease_target, select_model returns a complete
    ModelSelection with non-null primary, non-null primary_f1, and
    non-empty rationale. Calling twice gives identical results."""
    r1 = select_model(target)
    r2 = select_model(target)

    # Completeness
    assert r1["primary"] is not None
    assert r1["primary"] in ("autogluon", "tabpfn")
    assert isinstance(r1["primary_f1"], float)
    assert r1["primary_f1"] >= 0.0
    assert isinstance(r1["rationale"], str)
    assert len(r1["rationale"]) > 0

    # Secondary is either a valid model name or None
    assert r1["secondary"] in ("autogluon", "tabpfn", None)

    # If secondary is None, secondary_f1 must also be None
    if r1["secondary"] is None:
        assert r1["secondary_f1"] is None
    else:
        assert isinstance(r1["secondary_f1"], float)

    # Determinism — identical results
    assert r1 == r2


@given(target=disease_targets)
@settings(max_examples=100)
def test_select_model_matches_config(target):
    """For any disease, the primary model matches DISEASE_CONFIG."""
    r = select_model(target)
    expected_primary = DISEASE_CONFIG[target]["primary_model"]
    assert r["primary"] == expected_primary
    assert r["primary_f1"] == BENCHMARK_F1[target][expected_primary]


def test_chd_has_no_secondary():
    """CHD special case: TabPFN F1=0.000, so secondary is None."""
    r = select_model("coronary_heart_disease_prediction")
    assert r["primary"] == "autogluon"
    assert r["secondary"] is None
    assert r["secondary_f1"] is None


def test_invalid_disease_returns_structured_error():
    """Unknown ``disease_target`` yields a structured error dict
    (Requirement 2.8)."""
    result = select_model("nonexistent_disease")
    assert result.get("error_code") == "DISEASE_NOT_SUPPORTED"
    assert "Unknown disease_target" in result["message"]
