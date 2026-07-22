"""Unit tests for ``parse_query`` tool — edge cases and specific examples.

Post-refactor (task 5): the Lambda handler has been removed. ``parse_query``
is now a pure in-container Strands ``@tool`` that returns a structured error
dict (``{"error_code", "message"}``) instead of raising on bad input
(Requirement 2.8). These tests exercise that contract directly.
"""

from __future__ import annotations

import pytest

from src.tools.parse_query import parse_query


class TestParseQueryDiseaseAliases:
    """Every documented alias resolves to the correct disease target."""

    def test_hypertension_alias(self):
        r = parse_query("What is the likelihood of patient p1 having hypertension?")
        assert r["disease_target"] == "hypertension_prediction"

    def test_high_blood_pressure_alias(self):
        r = parse_query("patient abc123 high blood pressure risk")
        assert r["disease_target"] == "hypertension_prediction"

    def test_htn_alias(self):
        r = parse_query("patient x1 htn")
        assert r["disease_target"] == "hypertension_prediction"

    def test_stroke_alias(self):
        r = parse_query("patient p2 stroke likelihood")
        assert r["disease_target"] == "stroke_prediction"

    def test_cva_alias(self):
        r = parse_query("patient p2 cerebrovascular accident")
        assert r["disease_target"] == "stroke_prediction"

    def test_chd_alias(self):
        r = parse_query("patient p3 chd risk")
        assert r["disease_target"] == "coronary_heart_disease_prediction"

    def test_cad_alias(self):
        r = parse_query("patient p3 cad")
        assert r["disease_target"] == "coronary_heart_disease_prediction"

    def test_heart_disease_alias(self):
        r = parse_query("patient p3 heart disease")
        assert r["disease_target"] == "coronary_heart_disease_prediction"

    def test_coronary_artery_disease_alias(self):
        r = parse_query("patient p3 coronary artery disease")
        assert r["disease_target"] == "coronary_heart_disease_prediction"

    def test_alzheimers_alias(self):
        r = parse_query("patient p4 alzheimer's")
        assert r["disease_target"] == "alzheimers_prediction"

    def test_alzheimers_no_apostrophe(self):
        r = parse_query("patient p4 alzheimers")
        assert r["disease_target"] == "alzheimers_prediction"


class TestParseQueryPatientFormats:
    """All 3 documented patient-ID formats resolve."""

    def test_patient_space_format(self):
        r = parse_query("patient abc-123 stroke")
        assert r["patient_id"] == "abc-123"

    def test_id_colon_format(self):
        r = parse_query("id: xyz789 stroke risk")
        assert r["patient_id"] == "xyz789"

    def test_hash_format(self):
        r = parse_query("#pat001 stroke")
        assert r["patient_id"] == "pat001"

    def test_case_insensitive_patient(self):
        r = parse_query("Patient ABC stroke")
        assert r["patient_id"] == "ABC"


class TestParseQueryStructuredErrors:
    """Requirement 2.8: structured errors replace uncaught exceptions."""

    def test_missing_query(self):
        r = parse_query("")
        assert r["error_code"] == "MISSING_FIELD"

    def test_invalid_disease(self):
        r = parse_query("patient p1 unknown_disease_xyz")
        assert r["error_code"] == "DISEASE_NOT_SUPPORTED"
        assert "Unsupported disease" in r["message"]

    def test_missing_patient_identifier(self):
        r = parse_query("what are the risk factors for stroke")
        assert r["error_code"] == "INVALID_QUERY"
        assert "patient identifier" in r["message"]
