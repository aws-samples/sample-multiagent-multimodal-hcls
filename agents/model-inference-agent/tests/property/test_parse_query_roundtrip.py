"""
Round-trip property for the parsed-query pretty printer.

**Property 11: parse_query(format_parsed_query(parsed)) preserves
disease_target and patient_id.**

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import DISEASE_CONFIG
from src.tools.parse_query import format_parsed_query, parse_query


# ── Strategies ────────────────────────────────────────────────

disease_targets = st.sampled_from(list(DISEASE_CONFIG.keys()))

# Patient IDs that match the grammar recognised by ``parse_query``:
#   * start with an alphanumeric character
#   * contain only alphanumerics, '-', and '_'
#   * length 3–20
patient_ids = st.from_regex(
    r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,19}",
    fullmatch=True,
)


# ── Property 11 — Round trip ─────────────────────────────────

@settings(max_examples=100)
@given(disease_target=disease_targets, patient_id=patient_ids)
def test_parse_query_pretty_printer_roundtrip(
    disease_target: str, patient_id: str
) -> None:
    """For every supported (disease_target, patient_id), pretty-printing and
    re-parsing produces the same disease_target and patient_id.

    **Validates: Requirements 9.3, 9.4**
    """
    display = DISEASE_CONFIG[disease_target]["display_name"]
    parsed = {
        "disease_target": disease_target,
        "disease_display": display,
        "patient_id": patient_id,
    }
    prompt = format_parsed_query(parsed)

    # Pretty printer contract: both the display name and the literal patient
    # ID must appear in the rendered prompt (Req 9.1, 9.2).
    assert display in prompt, (prompt, display)
    assert patient_id in prompt, (prompt, patient_id)

    re_parsed = parse_query(prompt)

    assert re_parsed.get("error_code") is None, re_parsed
    assert re_parsed["disease_target"] == disease_target
    assert re_parsed["patient_id"] == patient_id


# ── Requirement 9.2 — concrete example ───────────────────────

def test_format_parsed_query_stroke_example():
    """**Validates: Requirements 9.2** — The concrete example from the
    requirements document renders a prompt that contains both "Stroke" and
    ``0074596f``.
    """
    parsed = {
        "disease_target": "stroke_prediction",
        "disease_display": "Stroke",
        "patient_id": "0074596f",
    }
    out = format_parsed_query(parsed)
    assert "Stroke" in out
    assert "0074596f" in out


# ── Missing-field contract ───────────────────────────────────

def test_format_parsed_query_rejects_missing_fields():
    """The pretty printer refuses to produce a silently-unparsable prompt."""
    with pytest.raises(ValueError, match="patient_id"):
        format_parsed_query(
            {"disease_target": "stroke_prediction", "disease_display": "Stroke"}
        )
    with pytest.raises(ValueError, match="disease_target"):
        format_parsed_query({"patient_id": "abc123"})


def test_format_parsed_query_accepts_dataclass():
    """Using the ``src.models.ParsedQuery`` dataclass should work identically
    to passing a dict with the same fields."""
    from src.models import ParsedQuery

    parsed = ParsedQuery(
        disease_target="hypertension_prediction",
        disease_display="Hypertension",
        patient_id="abc-999",
    )
    out = format_parsed_query(parsed)
    assert "Hypertension" in out
    assert "abc-999" in out

    re_parsed = parse_query(out)
    assert re_parsed["disease_target"] == "hypertension_prediction"
    assert re_parsed["patient_id"] == "abc-999"
