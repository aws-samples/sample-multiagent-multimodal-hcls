"""
Observability helpers for Model Inference Agent tools.

Provides structured JSON logging for tool start/end/error plus feature-vector
scrubbing so full feature vectors are never emitted at INFO level or below
(Requirement 7.5).

All helpers emit a single line JSON-formatted log entry so CloudWatch Logs
Insights can query fields directly (Requirements 7.2, 7.3, 7.4, 7.7).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("model_inference_agent")
if not logger.handlers:
    # Configure once; AgentCore containers set root handlers so we rely on
    # propagation, but add a default INFO handler if the root isn't set up.
    logger.setLevel(logging.INFO)


def _emit(level: int, payload: dict) -> None:
    """Emit a JSON-structured log record at the requested level."""
    try:
        logger.log(level, json.dumps(payload, default=str))
    except Exception:  # pragma: no cover - logging must never raise
        logger.log(level, str(payload))


def log_tool_start(tool_name: str, **ctx: Any) -> None:
    """Log the start of a tool invocation.

    Requirement 7.2: INFO log at start of each pipeline tool, containing the
    tool name and the patient ID (when available).
    """
    record = {"tool": tool_name, "status": "start"}
    patient_id = ctx.get("patient_id")
    if patient_id is not None:
        record["patient_id"] = patient_id
    disease_target = ctx.get("disease_target")
    if disease_target is not None:
        record["disease_target"] = disease_target
    for k, v in ctx.items():
        if k in record:
            continue
        record[k] = v
    _emit(logging.INFO, record)


def log_tool_end(tool_name: str, elapsed_ms: float, **ctx: Any) -> None:
    """Log successful completion of a tool invocation.

    Requirement 7.3: INFO log at end of each successful tool call, containing
    the tool name and elapsed milliseconds.
    """
    record = {
        "tool": tool_name,
        "status": "success",
        "elapsed_ms": round(float(elapsed_ms), 2),
    }
    patient_id = ctx.get("patient_id")
    if patient_id is not None:
        record["patient_id"] = patient_id
    disease_target = ctx.get("disease_target")
    if disease_target is not None:
        record["disease_target"] = disease_target
    for k, v in ctx.items():
        if k in record:
            continue
        record[k] = v
    _emit(logging.INFO, record)


def log_tool_error(
    tool_name: str, exc: Exception, elapsed_ms: float, **ctx: Any
) -> None:
    """Log a tool invocation failure.

    Requirement 7.4: ERROR log on exception with tool name, patient ID if
    known, exception type and message.
    """
    record = {
        "tool": tool_name,
        "status": "error",
        "elapsed_ms": round(float(elapsed_ms), 2),
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
    }
    patient_id = ctx.get("patient_id")
    if patient_id is not None:
        record["patient_id"] = patient_id
    disease_target = ctx.get("disease_target")
    if disease_target is not None:
        record["disease_target"] = disease_target
    for k, v in ctx.items():
        if k in record:
            continue
        record[k] = v
    _emit(logging.ERROR, record)


def log_pubmed_invocation(disease: str, risk_factor_count: int) -> None:
    """Log an invocation of send_pubmed_query.

    Requirement 7.7: INFO log when send_pubmed_query is invoked, containing
    the disease name and the number of risk factors passed.
    """
    _emit(
        logging.INFO,
        {
            "tool": "send_pubmed_query",
            "status": "invoke",
            "disease": disease,
            "risk_factor_count": int(risk_factor_count),
        },
    )


_FEATURE_VECTOR_RE = re.compile(
    r'("{field}"\s*:\s*)\[(?:[^\[\]]|\[[^\]]*\])*\]',
    re.DOTALL,
)


def scrub_feature_vector(
    log_msg: str, feature_vector_field_name: str = "feature_vector"
) -> str:
    """Redact a feature_vector field from a log message.

    Requirement 7.5: full feature vector must never be logged at INFO or below.
    This helper is used when callers want to log a payload that may contain
    the vector; it leaves the shape of the message intact but replaces the
    value with "<redacted>".
    """
    pattern = re.compile(
        r'("' + re.escape(feature_vector_field_name) + r'"\s*:\s*)'
        r'(\[(?:[^\[\]]|\[[^\]]*\])*\])',
        re.DOTALL,
    )
    return pattern.sub(r'\1"<redacted>"', log_msg)


def feature_vector_shape(feature_vector: Any) -> dict:
    """Return only shape/dtype summary for DEBUG logging.

    Requirement 7.5: if the feature vector must be logged for DEBUG, log only
    shape/dtype summary, not values.
    """
    try:
        if feature_vector is None:
            return {"rows": 0, "cols": 0}
        if isinstance(feature_vector, list):
            rows = len(feature_vector)
            cols = (
                len(feature_vector[0])
                if rows and isinstance(feature_vector[0], list)
                else 0
            )
            dtype = (
                type(feature_vector[0][0]).__name__
                if rows and cols
                else "unknown"
            )
            return {"rows": rows, "cols": cols, "dtype": dtype}
    except Exception:  # pragma: no cover
        pass
    return {"summary": "unavailable"}
