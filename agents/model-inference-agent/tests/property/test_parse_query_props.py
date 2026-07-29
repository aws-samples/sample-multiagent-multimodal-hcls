"""
Property-based tests for parse_query tool.

Feature: healthcare-agent-v2
Properties 1 & 2: Query parsing extraction and rejection.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.tools.parse_query import parse_query
from src.config import SUPPORTED_DISEASES, DISEASE_CONFIG


# ── Strategies ────────────────────────────────────────────────

disease_aliases = st.sampled_from(list(SUPPORTED_DISEASES.keys()))

patient_id_formats = st.one_of(
    # "patient X" format
    st.from_regex(r"[a-z0-9][a-z0-9_-]{2,19}", fullmatch=True).map(
        lambda pid: (f"patient {pid}", pid)
    ),
    # "id: X" format
    st.from_regex(r"[a-z0-9][a-z0-9_-]{2,19}", fullmatch=True).map(
        lambda pid: (f"id: {pid}", pid)
    ),
    # "#X" format
    st.from_regex(r"[a-z0-9][a-z0-9_-]{2,19}", fullmatch=True).map(
        lambda pid: (f"#{pid}", pid)
    ),
)


# ── Property 1: Correctly extracts disease and patient ID ─────
# Feature: healthcare-agent-v2, Property 1: Query parsing correctly
# extracts disease and patient ID
# **Validates: Requirements 2.2, 2.3**

@given(alias=disease_aliases, pid_fmt=patient_id_formats)
@settings(max_examples=200)
def test_parse_query_extracts_disease_and_patient(alias, pid_fmt):
    """For any valid query with a disease alias and patient ID,
    parse_query returns the correct disease_target and patient_id."""
    pid_text, expected_pid = pid_fmt

    # Build query like "What is the likelihood of patient X having stroke?"
    query = f"What is the likelihood of {pid_text} having {alias}?"

    result = parse_query(query)

    expected_target = SUPPORTED_DISEASES[alias]
    assert result["disease_target"] == expected_target
    assert result["patient_id"] == expected_pid
    assert result["disease_display"] == DISEASE_CONFIG[expected_target]["display_name"]


# ── Property 2: Rejects invalid queries ───────────────────────
# Feature: healthcare-agent-v2, Property 2: Query parsing rejects
# invalid queries
# **Validates: Requirements 2.4, 2.5**

# Strategy: strings that don't contain any disease alias
safe_chars = st.text(
    alphabet="xyz0123456789 ",
    min_size=5, max_size=40,
)


@given(query=safe_chars)
@settings(max_examples=200)
def test_parse_query_rejects_no_disease(query):
    """For any string without a recognized disease alias, ``parse_query``
    returns a structured error (Requirement 2.8)."""
    # Make sure the generated string doesn't accidentally contain an alias
    q_lower = query.lower()
    has_alias = any(alias in q_lower for alias in SUPPORTED_DISEASES)
    assume(not has_alias)

    result = parse_query(query)
    assert result.get("error_code") in {
        "DISEASE_NOT_SUPPORTED",
        "INVALID_QUERY",
        "MISSING_FIELD",
    }
    assert "message" in result


@given(alias=disease_aliases)
@settings(max_examples=200)
def test_parse_query_rejects_no_patient_id(alias):
    """For any string with a disease alias but no patient ID pattern,
    ``parse_query`` returns a structured ``INVALID_QUERY`` error."""
    # Use a query structure that can't accidentally match patient patterns.
    # Avoid "id" substring collisions from aliases like "cerebrovascular accident".
    query = f"What are the risk factors for {alias}?"

    # Some aliases may contain "id" substrings that match the regex.
    # Only test if the query truly has no patient-like pattern.
    import re
    patterns = [
        r"patient[\s_-]+([a-zA-Z0-9][a-zA-Z0-9_-]*)",
        r"(?:^|[\s,;])(?:id|identifier)[\s:]+([a-zA-Z0-9][a-zA-Z0-9_-]*)",
        r"#\s*([a-zA-Z0-9][a-zA-Z0-9_-]*)",
    ]
    has_pid = any(re.search(p, query, re.IGNORECASE) for p in patterns)
    assume(not has_pid)

    result = parse_query(query)
    assert result.get("error_code") == "INVALID_QUERY"
    assert "patient identifier" in result["message"]
