"""
select_model — pick primary and secondary model for a disease target.

Refactored from a Lambda handler into an in-container Strands tool (task 5.1).
Returns a structured error dict on bad input instead of raising (task 5.2,
Requirement 2.8).
"""

from __future__ import annotations

import time

from src.config import BENCHMARK_F1, DISEASE_CONFIG
from src.observability import log_tool_end, log_tool_error, log_tool_start

TOOL_NAME = "select_model"


def select_model(disease_target: str) -> dict:
    """Pick primary/secondary model based on benchmark F1 scores.

    Returns one of:
      * {"primary": str, "secondary": str|None,
         "primary_f1": float, "secondary_f1": float|None, "rationale": str}
      * {"error_code": str, "message": str}

    Error codes:
      * MISSING_FIELD         — disease_target missing
      * DISEASE_NOT_SUPPORTED — disease_target not a recognized key
    """
    start = time.time()
    log_tool_start(TOOL_NAME, disease_target=disease_target)

    if not disease_target:
        err = {"error_code": "MISSING_FIELD", "message": "disease_target is required"}
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field")
        return err

    if disease_target not in DISEASE_CONFIG:
        valid = list(DISEASE_CONFIG.keys())
        err = {
            "error_code": "DISEASE_NOT_SUPPORTED",
            "message": f"Unknown disease_target '{disease_target}'. Valid: {valid}",
        }
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="unsupported_disease")
        return err

    try:
        cfg = DISEASE_CONFIG[disease_target]
        scores = BENCHMARK_F1[disease_target]
        primary = cfg["primary_model"]
        secondary = "tabpfn" if primary == "autogluon" else "autogluon"

        # CHD special case: TabPFN F1=0.000 — don't use as secondary
        if (
            disease_target == "coronary_heart_disease_prediction"
            and secondary == "tabpfn"
        ):
            secondary = None

        rationale = f"{primary} selected (benchmark F1={scores[primary]:.3f})"
        if secondary:
            rationale += (
                f", {secondary} as cross-validation "
                f"(F1={scores[secondary]:.3f})"
            )

        result = {
            "primary": primary,
            "secondary": secondary,
            "primary_f1": scores[primary],
            "secondary_f1": scores.get(secondary, 0) if secondary else None,
            "rationale": rationale,
        }
        log_tool_end(
            TOOL_NAME, (time.time() - start) * 1000,
            disease_target=disease_target, primary=primary,
        )
        return result
    except Exception as exc:  # pragma: no cover - defensive
        log_tool_error(
            TOOL_NAME, exc, (time.time() - start) * 1000,
            disease_target=disease_target,
        )
        return {"error_code": "INVALID_QUERY", "message": str(exc)}
