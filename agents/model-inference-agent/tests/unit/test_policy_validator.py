"""Property-based tests for the Model Inference Agent IAM policy validator.

Validates: Requirements 5.1, 5.2, 5.3, 5.6, 5.7
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

# ── Load the validator module without requiring a package install ─────

_IAM_DIR = Path(__file__).resolve().parents[2] / "infra" / "iam"
_POLICY_PATH = _IAM_DIR / "model-inference-agent-access-policy.json"
_VALIDATOR_PATH = _IAM_DIR / "validate_policy.py"

_spec = importlib.util.spec_from_file_location(
    "mia_validate_policy", _VALIDATOR_PATH
)
assert _spec is not None and _spec.loader is not None
validate_policy = importlib.util.module_from_spec(_spec)
sys.modules["mia_validate_policy"] = validate_policy
_spec.loader.exec_module(validate_policy)

validate = validate_policy.validate
ALLOWED_SAGEMAKER_ENDPOINT_ARNS = validate_policy.ALLOWED_SAGEMAKER_ENDPOINT_ARNS
ALLOWED_S3_BUCKET_ARN = validate_policy.ALLOWED_S3_BUCKET_ARN
ALLOWED_S3_OBJECT_RESOURCE = validate_policy.ALLOWED_S3_OBJECT_RESOURCE


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def real_policy() -> dict:
    with open(_POLICY_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Hypothesis strategies ─────────────────────────────────────────────

_WILDCARD_ACTIONS = st.sampled_from(["*", "s3:*", "sagemaker:*", "S3:*", " * "])

_OTHER_S3_BUCKETS = st.sampled_from(
    [
        "arn:aws:s3:::some-other-bucket",
        "arn:aws:s3:::some-other-bucket/key",
        "arn:aws:s3:::my-private-bucket/preprocessing/x",
        "arn:aws:s3:::synthea-coherent-data-multimodal-evil",
        "arn:aws:s3:::synthea-coherent-data-multimodal-evil/preprocessing/x",
    ]
)

_OFFLIST_SAGEMAKER_ARNS = st.sampled_from(
    [
        "arn:aws:sagemaker:us-west-2:123456789012:endpoint/healthcare-other",
        "arn:aws:sagemaker:us-east-1:123456789012:endpoint/healthcare-autogluon",
        "arn:aws:sagemaker:us-west-2:000000000000:endpoint/healthcare-autogluon",
        "arn:aws:sagemaker:us-west-2:123456789012:endpoint/*",
        "arn:aws:sagemaker:us-west-2:123456789012:endpoint/healthcare-*",
        "*",
    ]
)

_NARROW_PREFIX_CONDITIONS = st.sampled_from(
    [
        {"StringLike": {"s3:prefix": ["preprocessing/*"]}},
        {"StringLike": {"s3:prefix": "preprocessing/*"}},
        {"StringLike": {"s3:prefix": ["preprocessing/final_clinical_df.csv"]}},
    ]
)


def _base_policy() -> dict:
    """A freshly-minted, known-good policy clone for mutation in tests."""
    return {
        "Version": "2012-10-17",
        "Id": "ModelInferenceAgentAccessPolicy",
        "Statement": [
            {
                "Sid": "InvokeSageMakerEndpointsOnly",
                "Effect": "Allow",
                "Action": "sagemaker:InvokeEndpoint",
                "Resource": list(ALLOWED_SAGEMAKER_ENDPOINT_ARNS),
            },
            {
                "Sid": "GetSyntheaPreprocessingObjects",
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": ALLOWED_S3_OBJECT_RESOURCE,
            },
            {
                "Sid": "ListSyntheaPreprocessingPrefix",
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": ALLOWED_S3_BUCKET_ARN,
                "Condition": {
                    "StringLike": {"s3:prefix": ["preprocessing/*"]}
                },
            },
        ],
    }


# ── Example / edge-case tests ─────────────────────────────────────────


def test_real_policy_passes(real_policy):
    """The checked-in policy file must have zero violations."""
    assert validate(real_policy) == []


def test_base_policy_passes():
    assert validate(_base_policy()) == []


@pytest.mark.parametrize(
    "bad_policy",
    [
        None,
        "not a policy",
        42,
        [],
        {},
        {"Version": "2012-10-17"},  # no Statement
        {"Version": "2012-10-17", "Statement": []},  # empty
        {"Version": "2008-10-17", "Statement": _base_policy()["Statement"]},
        {"Statement": _base_policy()["Statement"]},  # missing Version
    ],
)
def test_structurally_invalid_policies_rejected(bad_policy):
    assert validate(bad_policy), f"expected rejection for {bad_policy!r}"


def test_list_bucket_without_prefix_condition_rejected():
    policy = _base_policy()
    # Drop the Condition entirely.
    policy["Statement"][2].pop("Condition", None)
    violations = validate(policy)
    assert any("s3:prefix" in v for v in violations)


def test_list_bucket_with_wrong_prefix_condition_rejected():
    policy = _base_policy()
    policy["Statement"][2]["Condition"] = {
        "StringLike": {"s3:prefix": ["*"]}
    }
    violations = validate(policy)
    assert any("s3:prefix" in v for v in violations)


def test_s3_object_outside_preprocessing_rejected():
    policy = _base_policy()
    policy["Statement"][1]["Resource"] = (
        "arn:aws:s3:::synthea-coherent-data-multimodal/other/key"
    )
    violations = validate(policy)
    assert any("preprocessing" in v for v in violations)


# ── Determinism ───────────────────────────────────────────────────────


@settings(max_examples=100)
@given(
    policy=st.one_of(
        st.just(_base_policy()),
        st.just({"Version": "2012-10-17", "Statement": []}),
        st.just({"Version": "WRONG", "Statement": _base_policy()["Statement"]}),
    )
)
def test_validate_is_deterministic(policy):
    """Same input must produce identical violation lists every time."""
    snapshot = copy.deepcopy(policy)
    first = validate(copy.deepcopy(policy))
    second = validate(copy.deepcopy(policy))
    assert first == second
    # The validator must not mutate its input.
    assert policy == snapshot


# ── Wildcard action rejection ─────────────────────────────────────────


@settings(max_examples=100)
@given(bad_action=_WILDCARD_ACTIONS)
def test_wildcard_action_always_rejected(bad_action):
    """Any wildcard action makes the whole policy fail."""
    policy = _base_policy()
    policy["Statement"][0]["Action"] = bad_action
    # Keep the resource a valid SageMaker endpoint so the only reason to
    # reject is the wildcard action itself.
    violations = validate(policy)
    assert violations, f"expected rejection for action {bad_action!r}"


@settings(max_examples=100)
@given(bad_action=_WILDCARD_ACTIONS)
def test_wildcard_action_in_list_rejected(bad_action):
    """Wildcards rejected even when mixed with a legitimate action."""
    policy = _base_policy()
    policy["Statement"][0]["Action"] = ["sagemaker:InvokeEndpoint", bad_action]
    violations = validate(policy)
    assert violations


# ── S3 resource outside the allowed bucket ────────────────────────────


@settings(max_examples=100)
@given(bad_resource=_OTHER_S3_BUCKETS)
def test_s3_resource_outside_allowed_bucket_rejected(bad_resource):
    policy = _base_policy()
    # Put the off-bucket resource on a legitimate S3 action.
    policy["Statement"][1]["Resource"] = bad_resource
    violations = validate(policy)
    assert violations, f"expected rejection for S3 resource {bad_resource!r}"


# ── SageMaker wildcard or off-list ARN ────────────────────────────────


@settings(max_examples=100)
@given(bad_arn=_OFFLIST_SAGEMAKER_ARNS)
def test_sagemaker_wildcard_or_offlist_arn_rejected(bad_arn):
    policy = _base_policy()
    policy["Statement"][0]["Resource"] = bad_arn
    violations = validate(policy)
    assert violations, f"expected rejection for SageMaker resource {bad_arn!r}"


# ── Narrow statements pass ────────────────────────────────────────────


@settings(max_examples=100)
@given(
    endpoint=st.sampled_from(ALLOWED_SAGEMAKER_ENDPOINT_ARNS),
    condition=_NARROW_PREFIX_CONDITIONS,
)
def test_narrow_correctly_scoped_statements_pass(endpoint, condition):
    """If every resource, action, and condition is in-bounds, no violations."""
    policy = {
        "Version": "2012-10-17",
        "Id": "ModelInferenceAgentAccessPolicy",
        "Statement": [
            {
                "Sid": "InvokeSageMakerEndpointsOnly",
                "Effect": "Allow",
                "Action": "sagemaker:InvokeEndpoint",
                "Resource": endpoint,
            },
            {
                "Sid": "GetSyntheaPreprocessingObjects",
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": ALLOWED_S3_OBJECT_RESOURCE,
            },
            {
                "Sid": "ListSyntheaPreprocessingPrefix",
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": ALLOWED_S3_BUCKET_ARN,
                "Condition": condition,
            },
        ],
    }
    assert validate(policy) == []
