"""
Property-based tests for the refactored ``load_patient_data`` in-container tool.

Covers:
  * Property 3 — Feature-vector equivalence to the v1 reference. Kept as an
    ``integration`` test because the equivalence check needs the real v1
    package plus the full Synthea CSVs (neither is vendored in the container
    image).
  * Property 4 — Unknown-patient error shape. Runs in the default suite using
    mocked S3 (moto) so no live AWS access is required.

All tests call the in-container ``src.tools.load_patient_data`` module
directly — no AWS Lambda invocations (Requirements 8.1, 8.2, 8.3).

**Validates: Requirements 8.6 (P3), 8.7 (P4)**
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from src.tools.load_patient_data import (
    build_combined_dataset,
    load_patient_data,
    preprocess_all,
    preprocess_modality,
)
from src.config import (
    CLINICAL_DROP_COLS,
    GENOMIC_DROP_COLS,
    IMAGING_DROP_COLS,
)


# ── Synthetic in-memory modalities ────────────────────────────

def _make_clinical(patient_ids: list[str]) -> pd.DataFrame:
    rows = []
    for i, pid in enumerate(patient_ids):
        rows.append(
            {
                "patientID": pid,
                "diagnosisCode": "{230690007}" if i % 2 == 0 else "{59621000}",
                "diagnosisDescription": "syn",
                "age": 40 + i,
                "bmi": 25.0 + i,
            }
        )
    return pd.DataFrame(rows)


def _make_genomic(patient_ids: list[str]) -> pd.DataFrame:
    rows = []
    for pid in patient_ids:
        rows.append(
            {
                "patientID": pid,
                "diagnosisCode": "0",
                "diagnosisDescription": "syn",
                "gene_a": "0.1",
                "gene_b": "0.2",
            }
        )
    return pd.DataFrame(rows)


def _make_imaging(patient_ids: list[str]) -> pd.DataFrame:
    rows = []
    for pid in patient_ids:
        rows.append(
            {
                "patientID": pid,
                "diagnosisCode": "0",
                "diagnosisDescription": "syn",
                "pixel_mean": 0.5,
                "pixel_std": 0.1,
            }
        )
    return pd.DataFrame(rows)


def _fake_s3_client(modalities: dict[str, pd.DataFrame]):
    """Return a fake boto3 s3-client whose ``get_object`` serves the CSVs."""

    class _FakeBody:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def read(self) -> bytes:
            return self._data

    class _FakeS3:
        def get_object(self, Bucket: str, Key: str):  # noqa: N803 boto style
            for name, df in modalities.items():
                if Key.endswith(f"final_{name}_df.csv"):
                    buf = io.StringIO()
                    df.to_csv(buf, index=False)
                    return {"Body": _FakeBody(buf.getvalue().encode("utf-8"))}
            raise KeyError(Key)

    return _FakeS3()


# ── Property 4 — Unknown patient error shape ─────────────────

@st.composite
def _fake_pid(draw) -> str:
    # Alphanumeric IDs that are clearly outside the synthetic ID space
    # we insert below.
    return "zz-" + draw(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
            min_size=6,
            max_size=16,
        )
    )


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(fake_id=_fake_pid())
def test_load_patient_data_unknown_patient_returns_structured_error(fake_id):
    """**Validates: Requirements 8.7** — For any unknown patient ID,
    ``load_patient_data`` returns a structured error dict (not an uncaught
    exception) whose ``example_patient_ids`` field lists at least one known
    patient ID."""

    known = ["abc001", "abc002", "abc003"]
    assume(fake_id not in known)

    s3 = _fake_s3_client(
        {
            "clinical": _make_clinical(known),
            "genomic": _make_genomic(known),
            "imaging": _make_imaging(known),
        }
    )

    result = load_patient_data(
        patient_id=fake_id,
        disease_target="stroke_prediction",
        bucket="synthea-coherent-data-multimodal",
        prefix="preprocessing/",
        s3_client=s3,
    )

    assert isinstance(result, dict)
    assert result.get("error_code") == "PATIENT_NOT_FOUND"
    assert "message" in result
    assert "not found" in result["message"].lower()
    # The error carries at least one example patient ID so the caller can
    # recover without reading the full dataset.
    assert "example_patient_ids" in result
    assert len(result["example_patient_ids"]) >= 1
    assert all(pid in known for pid in result["example_patient_ids"])


def test_load_patient_data_known_patient_returns_feature_vector():
    """Known patient IDs produce a non-empty feature vector — the positive
    counterpart to Property 4 so regressions in the happy path are caught
    inside the default PBT run as well."""
    known = ["abc001", "abc002", "abc003"]
    s3 = _fake_s3_client(
        {
            "clinical": _make_clinical(known),
            "genomic": _make_genomic(known),
            "imaging": _make_imaging(known),
        }
    )

    result = load_patient_data(
        patient_id="abc001",
        disease_target="stroke_prediction",
        bucket="synthea-coherent-data-multimodal",
        prefix="preprocessing/",
        s3_client=s3,
    )

    assert result.get("error_code") is None, result
    assert result["patient_id_actual"] == "abc001"
    assert len(result["feature_vector"]) == 1
    assert len(result["feature_vector"][0]) > 0
    assert len(result["feature_names"]) == len(result["feature_vector"][0])


# ── Property 3 — v1 equivalence (integration-only) ───────────
#
# The v1 reference package ``model_inference_agent.preprocessing`` is not
# vendored into the SMUS repo. Running this check requires the v1 source tree
# and the full Synthea CSVs under ``data/raw/preprocessing/``. Skipped by
# default so the PBT suite stays fast and S3-free (Requirement 8.15).

DATA_DIR = Path("data/raw/preprocessing")


@pytest.mark.integration
def test_preprocessing_equivalence_to_v1():
    """**Validates: Requirements 8.6** — v2 combined dataset matches v1 for
    every cell. Skipped unless the v1 source and raw CSVs are present."""
    try:
        from model_inference_agent.preprocessing import (  # type: ignore
            build_combined_dataset as v1_build,
            preprocess_modality as v1_preprocess,
        )
    except ImportError:
        pytest.skip("v1 model_inference_agent package not available")

    if not DATA_DIR.exists():
        pytest.skip(f"Synthea CSVs not present at {DATA_DIR}")

    raw = {
        "clinical": pd.read_csv(DATA_DIR / "final_clinical_df.csv"),
        "genomic": pd.read_csv(DATA_DIR / "final_genomic_df.csv"),
        "imaging": pd.read_csv(DATA_DIR / "final_imaging_df.csv"),
    }
    v1_mods = {
        "clinical": v1_preprocess(raw["clinical"], CLINICAL_DROP_COLS, "clinical"),
        "genomic": v1_preprocess(raw["genomic"], GENOMIC_DROP_COLS, "genomic"),
        "imaging": v1_preprocess(raw["imaging"], IMAGING_DROP_COLS, "imaging"),
    }
    v1_combined = v1_build(v1_mods)

    v2_combined = build_combined_dataset(preprocess_all(raw))

    v1_sorted = v1_combined.sort_values("patientID").reset_index(drop=True)
    v2_sorted = v2_combined.sort_values("patientID").reset_index(drop=True)
    pd.testing.assert_frame_equal(v1_sorted, v2_sorted)
