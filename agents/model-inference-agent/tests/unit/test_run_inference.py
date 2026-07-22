"""Unit tests for ``run_inference`` — fallback and error behaviour.

Post-refactor (task 5): ``run_inference`` is an in-container Strands tool
that invokes SageMaker via ``sagemaker-runtime:InvokeEndpoint``. These tests
exercise the fallback semantics and structured-error contract.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.tools.run_inference import run_inference


# ── SageMaker runtime mocks ──────────────────────────────────

def _mock_sm(prob, fi=None):
    body = {"probability": prob}
    if fi:
        body["feature_importance"] = fi
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps(body).encode()
    m = MagicMock()
    m.invoke_endpoint.return_value = {"Body": mock_body}
    return m


def _failing_then_success(prob):
    """First call fails (ClientError), second succeeds."""
    from botocore.exceptions import ClientError

    call = {"n": 0}

    def side_effect(**kw):
        call["n"] += 1
        if call["n"] == 1:
            raise ClientError(
                {"Error": {"Code": "ModelError", "Message": "Primary down"}},
                "InvokeEndpoint",
            )
        body = json.dumps({"probability": prob}).encode()
        mb = MagicMock()
        mb.read.return_value = body
        return {"Body": mb}

    m = MagicMock()
    m.invoke_endpoint.side_effect = side_effect
    return m


FV = [["0.5", "1.0"]]
FN = ["a", "b"]


class TestFallbackBehavior:
    def test_primary_fails_secondary_promoted(self):
        mock = _failing_then_success(0.72)
        result = run_inference(
            FV, FN, "stroke_prediction", "autogluon", "tabpfn",
            sm_runtime=mock,
        )
        # Secondary was promoted to primary after primary failed.
        assert result["primary"]["model_name"] == "tabpfn"
        assert result["primary"]["probability"] == 0.72
        assert "secondary" not in result

    def test_both_fail_returns_structured_error(self):
        """Requirement 2.8: both models failing yields a structured error
        rather than an uncaught exception."""
        from botocore.exceptions import ClientError

        mock = MagicMock()
        mock.invoke_endpoint.side_effect = ClientError(
            {"Error": {"Code": "ModelError", "Message": "All down"}},
            "InvokeEndpoint",
        )
        result = run_inference(
            FV, FN, "stroke_prediction", "autogluon", "tabpfn",
            sm_runtime=mock,
        )
        assert result["error_code"] == "INFERENCE_FAILED"
        assert "All down" in result["message"]

    def test_chd_no_secondary(self):
        mock = _mock_sm(0.65, {"age": 0.1})
        result = run_inference(
            FV, FN, "coronary_heart_disease_prediction",
            "autogluon", None, sm_runtime=mock,
        )
        assert result["primary"]["probability"] == 0.65
        assert "secondary" not in result

    def test_feature_importance_included(self):
        fi = {"age": 0.15, "bmi": 0.10}
        mock = _mock_sm(0.80, fi)
        result = run_inference(
            FV, FN, "hypertension_prediction",
            "autogluon", None, sm_runtime=mock,
        )
        assert result["primary"]["feature_importance"] == fi


class TestStructuredErrors:
    """Requirement 2.8: invalid input yields a structured error."""

    def test_missing_feature_vector(self):
        r = run_inference([], FN, "stroke_prediction", "autogluon")
        assert r["error_code"] == "MISSING_FIELD"

    def test_missing_disease_target(self):
        r = run_inference(FV, FN, "", "autogluon")
        assert r["error_code"] == "MISSING_FIELD"

    def test_missing_primary_model(self):
        r = run_inference(FV, FN, "stroke_prediction", "")
        assert r["error_code"] == "MISSING_FIELD"
