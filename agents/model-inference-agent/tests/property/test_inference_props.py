"""
Property-based tests for run_inference tool.

Feature: healthcare-agent-v2
Property 6: Inference output validity.
"""

import json
import io
from unittest.mock import MagicMock
from hypothesis import given, settings
from hypothesis import strategies as st

from src.tools.run_inference import run_inference


# ── Mock SageMaker endpoint ──────────────────────────────────

def make_mock_sm_runtime(probability: float, feature_importance=None):
    """Create a mock sagemaker-runtime client returning given probability."""
    body_dict = {"probability": probability}
    if feature_importance:
        body_dict["feature_importance"] = feature_importance

    body_bytes = json.dumps(body_dict).encode("utf-8")
    mock_body = MagicMock()
    mock_body.read.return_value = body_bytes

    mock_client = MagicMock()
    mock_client.invoke_endpoint.return_value = {"Body": mock_body}
    return mock_client


def make_failing_mock():
    """Create a mock that raises on invoke_endpoint."""
    mock_client = MagicMock()
    mock_client.invoke_endpoint.side_effect = Exception("Endpoint down")
    return mock_client


# ── Strategies ────────────────────────────────────────────────

probabilities = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
model_names = st.sampled_from(["autogluon", "tabpfn"])

dummy_fv = [["0.5", "1.0", "0.3"]]
dummy_fn = ["feat_a", "feat_b", "feat_c"]


# ── Property 6: Inference output validity ─────────────────────
# Feature: healthcare-agent-v2, Property 6: Inference output validity
# **Validates: Requirements 5.1, 5.5**

@given(prob=probabilities, model=model_names)
@settings(max_examples=200)
def test_inference_output_probability_range(prob, model):
    """For any probability returned by the endpoint, the result
    probability is in [0.0, 1.0] and inference_time_ms >= 0."""
    mock = make_mock_sm_runtime(prob)
    result = run_inference(
        dummy_fv, dummy_fn, "stroke_prediction",
        model, None, sm_runtime=mock,
    )

    p = result["primary"]["probability"]
    assert 0.0 <= p <= 1.0
    assert result["primary"]["inference_time_ms"] >= 0.0
    assert result["primary"]["model_name"] == model


@given(p1=probabilities, p2=probabilities)
@settings(max_examples=200)
def test_dual_model_both_valid(p1, p2):
    """When both models succeed, both results have valid probabilities."""
    # Need separate mocks that return different probs per call
    call_count = {"n": 0}
    probs = [p1, p2]

    def mock_invoke(**kwargs):
        idx = call_count["n"]
        call_count["n"] += 1
        body = json.dumps({"probability": probs[idx]}).encode()
        mock_body = MagicMock()
        mock_body.read.return_value = body
        return {"Body": mock_body}

    mock_client = MagicMock()
    mock_client.invoke_endpoint.side_effect = mock_invoke

    result = run_inference(
        dummy_fv, dummy_fn, "stroke_prediction",
        "autogluon", "tabpfn", sm_runtime=mock_client,
    )

    assert 0.0 <= result["primary"]["probability"] <= 1.0
    assert "secondary" in result
    assert 0.0 <= result["secondary"]["probability"] <= 1.0
