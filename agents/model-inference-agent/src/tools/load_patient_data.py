"""
load_patient_data — load a patient's feature vector from S3.

Refactored from a Lambda handler into an in-container Strands tool (task 5.1).
Returns a structured error dict on bad input instead of raising (task 5.2,
Requirement 2.8).

Preprocessing logic is identical to the v1/v3 reference so the preserved
property tests still pass unchanged.
"""

from __future__ import annotations

import io
import os
import time
from typing import Dict

import boto3
import numpy as np
import pandas as pd

from src.config import (
    CLINICAL_DROP_COLS,
    DISEASE_CODES,
    GENOMIC_DROP_COLS,
    IMAGING_DROP_COLS,
    S3_BUCKET,
    S3_DATA_PREFIX,
)
from src.observability import log_tool_end, log_tool_error, log_tool_start

TOOL_NAME = "load_patient_data"


# ── Preprocessing (identical to v1) ───────────────────────────

def _parse_diagnosis_codes(code_str: str) -> set:
    if pd.isna(code_str) or code_str == "0":
        return set()
    return set(
        str(code_str)
        .replace("'", "")
        .replace(" ", "")
        .replace("{", "")
        .replace("}", "")
        .split(",")
    )


def _add_target_labels(df: pd.DataFrame) -> pd.DataFrame:
    for label in DISEASE_CODES:
        df[label] = "0"
    for i in range(len(df)):
        codes = _parse_diagnosis_codes(df.loc[i, "diagnosisCode"])
        for label, code in DISEASE_CODES.items():
            if code in codes:
                df.loc[i, label] = "1"
    return df


def preprocess_modality(
    df: pd.DataFrame, drop_cols: list, modality_name: str
) -> pd.DataFrame:
    out = df.copy()
    out = out.replace(np.nan, 0).astype(str)
    out = _add_target_labels(out)
    existing_drop = [c for c in drop_cols if c in out.columns]
    out.drop(existing_drop, axis=1, inplace=True)
    return out


def build_combined_dataset(
    modalities: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    target_cols = list(DISEASE_CODES.keys())
    clinical = modalities["clinical"]
    genomic = modalities["genomic"].drop(columns=target_cols, errors="ignore")
    imaging = modalities["imaging"].drop(columns=target_cols, errors="ignore")
    combined = clinical.merge(
        genomic, on="patientID", how="inner", suffixes=("", "_genomic")
    )
    combined = combined.merge(
        imaging, on="patientID", how="inner", suffixes=("", "_imaging")
    )
    combined = combined.astype(str).replace({"{": "", "}": ""}, regex=True)
    return combined


# ── S3 Data Loading ───────────────────────────────────────────

CSV_FILES = {
    "clinical": "final_clinical_df.csv",
    "genomic": "final_genomic_df.csv",
    "imaging": "final_imaging_df.csv",
}

DROP_COLS_MAP = {
    "clinical": CLINICAL_DROP_COLS,
    "genomic": GENOMIC_DROP_COLS,
    "imaging": IMAGING_DROP_COLS,
}


def load_csvs_from_s3(
    bucket: str, prefix: str, s3_client=None
) -> Dict[str, pd.DataFrame]:
    """Read the 3 CSV files from S3 and return raw DataFrames."""
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-west-2"))

    modalities = {}
    for name, filename in CSV_FILES.items():
        key = f"{prefix}{filename}"
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        df = pd.read_csv(io.BytesIO(resp["Body"].read()))
        modalities[name] = df
    return modalities


def preprocess_all(raw: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Preprocess all 3 modalities."""
    return {
        name: preprocess_modality(df, DROP_COLS_MAP[name], name)
        for name, df in raw.items()
    }


def prepare_feature_vector(
    combined: pd.DataFrame,
    patient_row: pd.Series,
    disease_target: str,
) -> tuple:
    """Prepare single-patient feature vector for model input.

    Returns (feature_values_list, feature_names_list).
    """
    other_targets = [d for d in DISEASE_CODES if d != disease_target]
    drop_cols = ["patientID"] + other_targets
    drop_cols = [c for c in drop_cols if c in combined.columns]

    row_df = patient_row.to_frame().T.copy()
    row_df = row_df.drop(columns=drop_cols, errors="ignore")

    feature_names = row_df.columns.tolist()
    feature_values = row_df.values.tolist()[0]
    return feature_values, feature_names


# ── Core Logic ────────────────────────────────────────────────

def load_patient_data(
    patient_id: str,
    disease_target: str,
    bucket: str = S3_BUCKET,
    prefix: str = S3_DATA_PREFIX,
    s3_client=None,
) -> dict:
    """Load patient data from S3, preprocess, and return feature vector.

    Returns one of:
      * {"patient_id_actual": str, "feature_vector": [[...]],
         "feature_names": [...], "n_patients": int, "n_features": int}
      * {"error_code": str, "message": str}

    Error codes:
      * MISSING_FIELD       — patient_id or disease_target missing
      * PATIENT_NOT_FOUND   — patient not found in the combined dataset
      * DATA_UNAVAILABLE    — S3 / preprocessing failure (bucket missing, etc.)
    """
    start = time.time()
    log_tool_start(
        TOOL_NAME, patient_id=patient_id, disease_target=disease_target
    )

    if not patient_id:
        err = {"error_code": "MISSING_FIELD", "message": "patient_id is required"}
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field")
        return err
    if not disease_target:
        err = {"error_code": "MISSING_FIELD", "message": "disease_target is required"}
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field")
        return err

    try:
        raw = load_csvs_from_s3(bucket, prefix, s3_client)
        modalities = preprocess_all(raw)
        combined = build_combined_dataset(modalities)
    except Exception as exc:
        log_tool_error(
            TOOL_NAME, exc, (time.time() - start) * 1000,
            patient_id=patient_id, disease_target=disease_target,
        )
        return {
            "error_code": "DATA_UNAVAILABLE",
            "message": (
                f"Failed to load patient data from s3://{bucket}/{prefix}: "
                f"{type(exc).__name__}: {exc}"
            ),
        }

    patient_row = combined[combined["patientID"] == patient_id]
    if patient_row.empty:
        patient_row = combined[
            combined["patientID"].str.contains(patient_id, case=False, na=False)
        ]

    if patient_row.empty:
        available = combined["patientID"].tolist()[:5]
        err = {
            "error_code": "PATIENT_NOT_FOUND",
            "message": (
                f"Patient '{patient_id}' not found. "
                f"Available IDs (first 5): {available}"
            ),
            "example_patient_ids": available,
        }
        log_tool_end(
            TOOL_NAME, (time.time() - start) * 1000,
            patient_id=patient_id, outcome="not_found",
        )
        return err

    row = patient_row.iloc[0]
    actual_pid = row["patientID"]
    feature_values, feature_names = prepare_feature_vector(
        combined, row, disease_target
    )

    result = {
        "patient_id_actual": actual_pid,
        "feature_vector": [feature_values],
        "feature_names": feature_names,
        "n_patients": len(combined),
        "n_features": combined.shape[1],
    }
    log_tool_end(
        TOOL_NAME, (time.time() - start) * 1000,
        patient_id=actual_pid, disease_target=disease_target,
        n_features=len(feature_names),
    )
    return result
