"""
parse_query — extract disease target and patient ID from a natural language query.

Refactored from a Lambda handler into an in-container Strands tool (task 5.1).
Returns a structured error dict on bad input instead of raising (task 5.2,
Requirement 2.8).
"""

from __future__ import annotations

import re
import time
from typing import Mapping, Optional, Union

from src.config import DISEASE_CONFIG, SUPPORTED_DISEASES
from src.observability import log_tool_end, log_tool_error, log_tool_start

TOOL_NAME = "parse_query"

# Either a ParsedQuery dataclass (from src.models) or a plain dict-like
# object carrying the same keys. Kept as a union so the pretty printer can
# be called from tools that return dicts (tasks 5.1/5.2) and from code that
# still uses the dataclass form in src.models.
ParsedQueryLike = Union[Mapping[str, object], object]


def parse_query(query: str) -> dict:
    """Extract disease target, display name, and patient ID from a prompt.

    Returns one of:
      * {"disease_target": str, "disease_display": str, "patient_id": str}
      * {"error_code": str, "message": str}

    Error codes:
      * MISSING_FIELD      — query argument is missing/empty
      * INVALID_QUERY      — patient identifier could not be extracted
      * DISEASE_NOT_SUPPORTED — no supported-disease alias found in the prompt
    """
    start = time.time()
    log_tool_start(TOOL_NAME)

    if not query or not str(query).strip():
        err = {"error_code": "MISSING_FIELD", "message": "query is required"}
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="invalid_input")
        return err

    q = str(query).lower().strip()

    # Find disease (longest alias match first)
    disease_target: Optional[str] = None
    for alias, target in sorted(
        SUPPORTED_DISEASES.items(), key=lambda x: -len(x[0])
    ):
        if alias in q:
            disease_target = target
            break

    if disease_target is None:
        supported = [cfg["display_name"] for cfg in DISEASE_CONFIG.values()]
        err = {
            "error_code": "DISEASE_NOT_SUPPORTED",
            "message": f"Unsupported disease. Supported: {', '.join(supported)}",
        }
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="unsupported_disease")
        return err

    patterns = [
        r"patient[\s_-]+([a-zA-Z0-9][a-zA-Z0-9_-]*)",
        r"(?:^|[\s,;])(?:id|identifier)[\s:]+([a-zA-Z0-9][a-zA-Z0-9_-]*)",
        r"#\s*([a-zA-Z0-9][a-zA-Z0-9_-]*)",
    ]
    patient_id: Optional[str] = None
    for pat in patterns:
        m = re.search(pat, str(query), re.IGNORECASE)
        if m:
            patient_id = m.group(1)
            break

    if patient_id is None:
        err = {
            "error_code": "INVALID_QUERY",
            "message": (
                "Could not find patient identifier. "
                "Use format: 'patient X', 'id: X', or '#X'"
            ),
        }
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_patient_id")
        return err

    cfg = DISEASE_CONFIG[disease_target]
    result = {
        "disease_target": disease_target,
        "disease_display": cfg["display_name"],
        "patient_id": patient_id,
    }
    log_tool_end(
        TOOL_NAME,
        (time.time() - start) * 1000,
        patient_id=patient_id,
        disease_target=disease_target,
    )
    return result


def _safe_parse_query(query: str) -> dict:
    """Wrapper that converts unexpected exceptions into structured errors."""
    start = time.time()
    try:
        return parse_query(query)
    except Exception as exc:  # pragma: no cover - defensive
        log_tool_error(TOOL_NAME, exc, (time.time() - start) * 1000)
        return {"error_code": "INVALID_QUERY", "message": str(exc)}


# ── Pretty printer (task 7.1) ────────────────────────────────

def _extract(parsed: ParsedQueryLike, key: str) -> Optional[str]:
    """Read ``key`` from either a Mapping or an attribute-style object."""
    if isinstance(parsed, Mapping):
        value = parsed.get(key)
    else:
        value = getattr(parsed, key, None)
    if value is None:
        return None
    return str(value)


def format_parsed_query(parsed: ParsedQueryLike) -> str:
    """Render a ``ParsedQuery`` back into a canonical natural-language prompt.

    The output MUST contain both the disease display name and the literal
    patient ID so that a subsequent call to ``parse_query`` can recover the
    same ``(disease_target, patient_id)`` pair — this is the round-trip
    property enforced by ``tests/property/test_parse_query_roundtrip.py``
    (Requirements 9.1, 9.2, 9.3).

    Accepts either a ``dict``-like mapping (the shape returned by the
    refactored ``parse_query`` tool) or any object with
    ``disease_target`` / ``disease_display`` / ``patient_id`` attributes
    (``src.models.ParsedQuery``).

    Raises ``ValueError`` if required fields are missing, so callers don't
    silently produce an unparsable prompt.
    """
    disease_target = _extract(parsed, "disease_target")
    patient_id = _extract(parsed, "patient_id")
    disease_display = _extract(parsed, "disease_display")

    if not disease_target:
        raise ValueError("ParsedQuery is missing disease_target")
    if not patient_id:
        raise ValueError("ParsedQuery is missing patient_id")

    # Fall back to the configured display name if the caller didn't supply
    # one (preserves round-trip for objects built by hand from just
    # disease_target + patient_id).
    if not disease_display:
        cfg = DISEASE_CONFIG.get(disease_target)
        if not cfg:
            raise ValueError(
                f"Unknown disease_target in ParsedQuery: {disease_target!r}"
            )
        disease_display = cfg["display_name"]

    # Canonical phrasing — identical to the "what is the likelihood of
    # patient X having Y?" shape the parser was tuned against.
    return (
        f"What is the likelihood of patient {patient_id} "
        f"having {disease_display}?"
    )
