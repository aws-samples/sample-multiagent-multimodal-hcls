"""
run_inference — dual-model inference via SageMaker real-time endpoints.

Refactored from a Lambda handler into an in-container Strands tool (task 5.3).
Invokes SageMaker endpoints using ``sagemaker-runtime:InvokeEndpoint`` rather
than via AWS Lambda (Requirements 2.2, 2.7).

Endpoint names are read from env vars with the defaults required by
Requirements 6.5 and 6.6:

    SAGEMAKER_AUTOGLUON_ENDPOINT  default "healthcare-autogluon"
    SAGEMAKER_TABPFN_ENDPOINT     default "healthcare-tabpfn"

Structured errors are returned on invalid input or SageMaker failure
(Requirement 2.8).
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.observability import (
    log_tool_end,
    log_tool_error,
    log_tool_start,
)

TOOL_NAME = "run_inference"


def _endpoint_for(model_name: str) -> str:
    """Resolve model_name → endpoint name from env (lazy)."""
    if model_name == "autogluon":
        return os.environ.get(
            "SAGEMAKER_AUTOGLUON_ENDPOINT", "healthcare-autogluon"
        )
    if model_name == "tabpfn":
        return os.environ.get(
            "SAGEMAKER_TABPFN_ENDPOINT", "healthcare-tabpfn"
        )
    raise ValueError(f"Unsupported model_name: {model_name}")


def invoke_endpoint(
    model_name: str,
    feature_vector: list,
    feature_names: list,
    disease_target: str,
    sm_runtime: Any = None,
) -> dict:
    """Call one SageMaker endpoint and return a prediction dict.

    Raises ClientError / BotoCoreError on boto3 failure; callers should wrap.
    """
    if sm_runtime is None:
        sm_runtime = boto3.client("sagemaker-runtime", region_name=os.environ.get("AWS_REGION", "us-west-2"))

    endpoint_name = _endpoint_for(model_name)
    payload = json.dumps(
        {
            "feature_vector": feature_vector,
            "feature_names": feature_names,
            "disease_target": disease_target,
        }
    )

    start = time.time()
    response = sm_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Body=payload,
    )
    elapsed_ms = (time.time() - start) * 1000

    body = json.loads(response["Body"].read().decode("utf-8"))
    result = {
        "model": model_name,
        "model_name": model_name,  # preserved for back-compat
        "probability": float(body.get("probability", 0.0)),
        "inference_time_ms": round(elapsed_ms, 2),
    }
    if "feature_importance" in body and body["feature_importance"]:
        result["feature_importance"] = body["feature_importance"]
    return result


def run_inference(
    feature_vector: list,
    feature_names: list,
    disease_target: str,
    primary_model: str,
    secondary_model: Optional[str] = None,
    sm_runtime: Any = None,
) -> dict:
    """Run primary + optional secondary inference with fallback.

    Returns one of:
      * {"primary": {...}, "secondary": {...}}    (secondary omitted if None)
      * {"error_code": str, "message": str}

    Error codes:
      * MISSING_FIELD       — required argument missing
      * INFERENCE_FAILED    — both endpoints failed
    """
    start = time.time()
    log_tool_start(
        TOOL_NAME,
        disease_target=disease_target,
        primary_model=primary_model,
        secondary_model=secondary_model,
    )

    if not feature_vector or not feature_names:
        err = {
            "error_code": "MISSING_FIELD",
            "message": "feature_vector and feature_names are required",
        }
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field")
        return err
    if not disease_target or not primary_model:
        err = {
            "error_code": "MISSING_FIELD",
            "message": "disease_target and primary_model are required",
        }
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="missing_field")
        return err

    primary_result: Optional[dict] = None
    secondary_result: Optional[dict] = None
    primary_err: Optional[Exception] = None
    secondary_err: Optional[Exception] = None

    # Run primary and secondary in parallel
    futures = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures['primary'] = pool.submit(
            invoke_endpoint, primary_model, feature_vector, feature_names,
            disease_target, sm_runtime,
        )
        if secondary_model:
            futures['secondary'] = pool.submit(
                invoke_endpoint, secondary_model, feature_vector, feature_names,
                disease_target, sm_runtime,
            )

    try:
        primary_result = futures['primary'].result()
    except (ClientError, BotoCoreError, ValueError, KeyError) as exc:
        primary_err = exc
        log_tool_error(
            TOOL_NAME, exc, (time.time() - start) * 1000,
            disease_target=disease_target, model=primary_model, stage="primary",
        )

    if 'secondary' in futures:
        try:
            secondary_result = futures['secondary'].result()
        except (ClientError, BotoCoreError, ValueError, KeyError) as exc:
            secondary_err = exc
            log_tool_error(
                TOOL_NAME, exc, (time.time() - start) * 1000,
                disease_target=disease_target, model=secondary_model, stage="secondary",
            )

    # Fallback: promote secondary if primary failed
    if primary_result is None and secondary_result is not None:
        primary_result = secondary_result
        secondary_result = None

    if primary_result is None:
        err_msg_parts = []
        if primary_err is not None:
            err_msg_parts.append(f"primary ({primary_model}): {primary_err}")
        if secondary_err is not None:
            err_msg_parts.append(f"secondary ({secondary_model}): {secondary_err}")
        err = {
            "error_code": "INFERENCE_FAILED",
            "message": "SageMaker inference failed for all configured models. "
            + "; ".join(err_msg_parts),
        }
        log_tool_end(TOOL_NAME, (time.time() - start) * 1000, outcome="both_failed")
        return err

    output: dict = {"primary": primary_result}
    if secondary_result is not None:
        output["secondary"] = secondary_result

    log_tool_end(
        TOOL_NAME, (time.time() - start) * 1000,
        disease_target=disease_target,
        primary_prob=primary_result["probability"],
        has_secondary=secondary_result is not None,
    )
    return output
