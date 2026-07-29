"""
format_response — build the structured InferenceResponse.

Refactored from a Lambda handler into an in-container Strands tool (task 5.1).
Returns a structured error dict on bad input instead of raising (task 5.2,
Requirement 2.8).
"""

from __future__ import annotations

import time
from typing import List, Optional

from src.config import CONFIDENCE_THRESHOLDS, CONSISTENCY_THRESHOLD
from src.observability import log_tool_end, log_tool_error, log_tool_start

TOOL_NAME = "format_response"

DISCLAIMER = (
    "\u26a0 DISCLAIMER: These predictions are based on models trained on "
    "synthetic data (Synthea Coherent Dataset) and should NOT be used for "
    "clinical decision-making. Always consult a healthcare professional."
)


def compute_confidence(probability: float) -> str:
    if probability >= CONFIDENCE_THRESHOLDS["high"]:
        return "HIGH"
    if probability >= CONFIDENCE_THRESHOLDS["medium"]:
        return "MEDIUM"
    return "LOW"


def compute_consistency(p_primary: float, p_secondary: float) -> str:
    diff = abs(p_primary - p_secondary)
    return "CONSISTENT" if diff <= CONSISTENCY_THRESHOLD else "DIVERGENT"


def build_contributing_factors(
    feature_importance: Optional[dict], max_factors: int = 5
) -> List[str]:
    if not feature_importance:
        return []
    items = list(feature_importance.items())[:max_factors]
    return [f"{feat} (importance: {imp})" for feat, imp in items]


def format_response(
    patient_id: str,
    disease_display: str,
    primary: dict,
    secondary: Optional[dict] = None,
    primary_f1: float = 0.0,
    secondary_f1: Optional[float] = None,
) -> dict:
    """Build the structured InferenceResponse."""
    start = time.time()
    log_tool_start(TOOL_NAME, patient_id=patient_id)

    if not patient_id:
        err = {"error_code": "MISSING_FIELD", "message": "patient_id is required"}
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field")
        return err
    if not disease_display:
        err = {"error_code": "MISSING_FIELD", "message": "disease_display is required"}
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field")
        return err
    if not isinstance(primary, dict) or "probability" not in primary:
        err = {
            "error_code": "INVALID_QUERY",
            "message": "primary must be a dict with a 'probability' field",
        }
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="invalid_input")
        return err

    try:
        # Support both "model" (new in-container shape) and "model_name" (legacy)
        primary_model = primary.get("model_name") or primary.get("model") or ""
        p = float(primary["probability"])
        confidence = compute_confidence(p)

        consistency = None
        if secondary:
            consistency = compute_consistency(p, float(secondary["probability"]))

        factors = build_contributing_factors(primary.get("feature_importance"))

        model_eval = {
            "primary": {
                "model": primary_model,
                "benchmark_f1": primary_f1,
                "inference_time_ms": primary.get("inference_time_ms"),
            }
        }
        if secondary:
            secondary_model = (
                secondary.get("model_name") or secondary.get("model") or ""
            )
            model_eval["secondary"] = {
                "model": secondary_model,
                "benchmark_f1": secondary_f1,
                "inference_time_ms": secondary.get("inference_time_ms"),
            }
            model_eval["consistency"] = consistency
            model_eval["probability_diff"] = round(
                abs(p - float(secondary["probability"])), 4
            )

        pct = round(p * 100, 1)
        summary = (
            f"Patient {patient_id} has a {pct}% predicted likelihood "
            f"of {disease_display}."
        )
        summary += (
            f"\nConfidence: {confidence} | Primary model: "
            f"{primary_model} (benchmark F1={primary_f1:.3f})"
        )
        if secondary:
            s_pct = round(float(secondary["probability"]) * 100, 1)
            secondary_model = (
                secondary.get("model_name") or secondary.get("model") or ""
            )
            summary += (
                f"\nCross-validation ({secondary_model}): "
                f"{s_pct}% \u2014 {consistency}"
            )
        if factors:
            summary += "\n\nTop contributing factors:"
            for f in factors:
                summary += f"\n  \u2022 {f}"

        secondary_model_name = (
            (secondary.get("model_name") or secondary.get("model"))
            if secondary
            else None
        )
        secondary_prob = (
            float(secondary["probability"]) if secondary else None
        )

        result = {
            "patient_id": patient_id,
            "disease": disease_display,
            "probability": p,
            "primary_model": primary_model,
            "primary_probability": p,
            "secondary_model": secondary_model_name,
            "secondary_probability": secondary_prob,
            "confidence": confidence,
            "consistency": consistency,
            "contributing_factors": factors,
            "disclaimer": DISCLAIMER,
            "summary": summary + "\n\n" + DISCLAIMER,
            "model_evaluation": model_eval,
        }
        log_tool_end(
            TOOL_NAME, (time.time() - start) * 1000,
            patient_id=patient_id, confidence=confidence,
        )
        return result
    except Exception as exc:
        log_tool_error(
            TOOL_NAME, exc, (time.time() - start) * 1000,
            patient_id=patient_id,
        )
        return {
            "error_code": "INVALID_QUERY",
            "message": f"Failed to format response: {type(exc).__name__}: {exc}",
        }
