"""Shared test fixtures and Hypothesis strategies."""

import pytest
from hypothesis import strategies as st

from src.config import SUPPORTED_DISEASES, DISEASE_CONFIG, BENCHMARK_F1


# ── Hypothesis Strategies ─────────────────────────────────────

disease_aliases = st.sampled_from(list(SUPPORTED_DISEASES.keys()))
disease_targets = st.sampled_from(list(DISEASE_CONFIG.keys()))

patient_id_chars = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=3, max_size=20,
)

probability_values = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

feature_importance_dicts = st.dictionaries(
    keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=2, max_size=15),
    values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    min_size=0, max_size=20,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def sample_patient_id():
    return "abc-123-def-456"


@pytest.fixture
def sample_disease_target():
    return "stroke_prediction"


@pytest.fixture
def all_disease_targets():
    return list(DISEASE_CONFIG.keys())
