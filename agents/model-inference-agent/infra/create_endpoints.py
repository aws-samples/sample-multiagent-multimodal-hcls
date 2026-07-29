"""
Create SageMaker endpoints for AutoGluon and TabPFN models.

Usage: python infra/create_endpoints.py

This uses the SageMaker Python SDK to create real-time endpoints
with custom inference containers.
"""

import os
import json
import boto3
import time

REGION = os.environ.get("AWS_REGION", "us-east-1")
ACCOUNT_ID = "014097726564"
BUCKET = f"healthcare-agent-v2-{ACCOUNT_ID}"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/healthcare-agent-v2-sagemaker-role"

sm_client = boto3.client("sagemaker", region_name=REGION)

# Use the AWS-managed PyTorch inference container (has pip, can install deps)
# PyTorch 2.1 on Python 3.10
PYTORCH_IMAGE = f"763104351884.dkr.ecr.{REGION}.amazonaws.com/pytorch-inference:2.1.0-cpu-py310-ubuntu20.04-sagemaker"


def create_model(name: str, model_s3_uri: str):
    """Create a SageMaker Model."""
    print(f"  Creating model: {name}")
    try:
        sm_client.create_model(
            ModelName=name,
            PrimaryContainer={
                "Image": PYTORCH_IMAGE,
                "ModelDataUrl": model_s3_uri,
                "Environment": {
                    "SAGEMAKER_PROGRAM": "inference.py",
                    "SAGEMAKER_SUBMIT_DIRECTORY": model_s3_uri,
                },
            },
            ExecutionRoleArn=ROLE_ARN,
        )
        print(f"    ✓ Model {name} created")
    except sm_client.exceptions.ClientError as e:
        if "Cannot create already existing model" in str(e):
            print(f"    Model {name} already exists")
        else:
            raise


def create_endpoint_config(name: str, model_name: str):
    """Create a SageMaker EndpointConfig."""
    print(f"  Creating endpoint config: {name}")
    try:
        sm_client.create_endpoint_config(
            EndpointConfigName=name,
            ProductionVariants=[{
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "InstanceType": "ml.m5.large",
                "InitialInstanceCount": 1,
                "InitialVariantWeight": 1.0,
            }],
        )
        print(f"    ✓ Endpoint config {name} created")
    except sm_client.exceptions.ClientError as e:
        if "Cannot create already existing" in str(e):
            print(f"    Endpoint config {name} already exists")
        else:
            raise


def create_endpoint(name: str, config_name: str):
    """Create a SageMaker Endpoint (async — takes ~5-8 min)."""
    print(f"  Creating endpoint: {name}")
    try:
        sm_client.create_endpoint(
            EndpointName=name,
            EndpointConfigName=config_name,
        )
        print(f"    ✓ Endpoint {name} creation started (takes ~5-8 min)")
    except sm_client.exceptions.ClientError as e:
        if "Cannot create already existing" in str(e):
            print(f"    Endpoint {name} already exists")
        else:
            raise


def wait_for_endpoint(name: str, max_wait: int = 600):
    """Wait for endpoint to become InService."""
    print(f"  Waiting for {name} to become InService...")
    start = time.time()
    while time.time() - start < max_wait:
        resp = sm_client.describe_endpoint(EndpointName=name)
        status = resp["EndpointStatus"]
        if status == "InService":
            print(f"    ✓ {name} is InService")
            return True
        elif status == "Failed":
            reason = resp.get("FailureReason", "Unknown")
            print(f"    ✗ {name} FAILED: {reason}")
            return False
        elapsed = int(time.time() - start)
        print(f"    Status: {status} ({elapsed}s elapsed)")
        time.sleep(30)
    print(f"    ✗ Timeout waiting for {name}")
    return False


def main():
    print("=" * 60)
    print("  SageMaker Endpoint Deployment")
    print("=" * 60)

    # AutoGluon
    print("\n[1/2] AutoGluon Endpoint")
    ag_model_uri = f"s3://{BUCKET}/sagemaker/autogluon/model.tar.gz"
    create_model("healthcare-autogluon", ag_model_uri)
    create_endpoint_config("healthcare-autogluon-config", "healthcare-autogluon")
    create_endpoint("healthcare-autogluon", "healthcare-autogluon-config")

    # TabPFN
    print("\n[2/2] TabPFN Endpoint")
    tp_model_uri = f"s3://{BUCKET}/sagemaker/tabpfn/model.tar.gz"
    create_model("healthcare-tabpfn", tp_model_uri)
    create_endpoint_config("healthcare-tabpfn-config", "healthcare-tabpfn")
    create_endpoint("healthcare-tabpfn", "healthcare-tabpfn-config")

    # Wait for both
    print("\nWaiting for endpoints to come online...")
    ag_ok = wait_for_endpoint("healthcare-autogluon")
    tp_ok = wait_for_endpoint("healthcare-tabpfn")

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  AutoGluon: {'✓ InService' if ag_ok else '✗ Failed'}")
    print(f"  TabPFN:    {'✓ InService' if tp_ok else '✗ Failed'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
