"""Simulate the effective IAM permissions on `agentcore-workshop-role`.

This script exercises `iam:SimulatePrincipalPolicy` against the role that
backs the Model Inference Agent runtime and asserts the specific grants
added by `ModelInferenceAgentAccessPolicy` (task 2.1/2.2), plus that the
scope around those grants is tight.

It focuses on what *this agent's policy* adds:

- `sagemaker:InvokeEndpoint` is allowed on the two named endpoints only.
- `s3:GetObject` is allowed on `preprocessing/*` of the Synthea bucket
  only.
- `s3:ListBucket` with an `s3:prefix` context key scoped to
  `preprocessing/*` is allowed on the Synthea bucket.

Interaction with other policies on the role
-------------------------------------------

`BedrockAgentCoreFullAccess` does *not* grant `sagemaker:InvokeEndpoint`
on arbitrary endpoints, so the SageMaker "denied" check targeting an
out-of-scope endpoint faithfully reflects *this* policy's scoping.

`AmazonHealthLakeFullAccess` — which Req 5.5 requires we preserve —
grants `s3:ListBucket` on `Resource: "*"` across the account. That means
the role as a whole is allowed to `s3:ListBucket` on any bucket, not
just the Synthea bucket. That broad `ListBucket` grant is *not*
something `ModelInferenceAgentAccessPolicy` introduces; it is inherited
from the pre-existing managed policy. The 7th assertion below therefore
records the actual (allowed) outcome with a note, so the script's
output reflects the real state of the role rather than a false scoping
claim about what this policy adds. `s3:GetObject` is *not* granted
broadly by `AmazonHealthLakeFullAccess`, so the "denied" S3 object
check on a foreign bucket still meaningfully exercises our scoping.

Usage
-----
    python simulate_permissions.py
    # exit 0 on all-match, non-zero on any mismatch

Requires refreshed AWS credentials for account 123456789012.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Iterable

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# ── Constants ─────────────────────────────────────────────────────────

ROLE_ARN: str = "arn:aws:iam::123456789012:role/agentcore-workshop-role"

AUTOGLUON_ENDPOINT_ARN: str = (
    "arn:aws:sagemaker:us-west-2:123456789012:endpoint/healthcare-autogluon"
)
TABPFN_ENDPOINT_ARN: str = (
    "arn:aws:sagemaker:us-west-2:123456789012:endpoint/healthcare-tabpfn"
)
OUT_OF_SCOPE_ENDPOINT_ARN: str = (
    "arn:aws:sagemaker:us-west-2:123456789012:endpoint/some-other-endpoint"
)

SYNTHEA_BUCKET_ARN: str = "arn:aws:s3:::synthea-coherent-data-multimodal"
SYNTHEA_CLINICAL_OBJECT_ARN: str = (
    "arn:aws:s3:::synthea-coherent-data-multimodal/preprocessing/final_clinical_df.csv"
)
OUT_OF_SCOPE_OBJECT_ARN: str = "arn:aws:s3:::some-other-bucket/file.csv"
OUT_OF_SCOPE_BUCKET_ARN: str = "arn:aws:s3:::some-other-bucket"

# ── Simulation response decoding ──────────────────────────────────────

ALLOWED_DECISIONS: frozenset[str] = frozenset({"allowed"})
DENIED_DECISIONS: frozenset[str] = frozenset({"implicitDeny", "explicitDeny"})


@dataclass(frozen=True)
class Check:
    """One simulation assertion."""

    label: str
    action: str
    resource: str
    expected: str  # "allowed" or "denied"
    context: tuple[tuple[str, str, tuple[str, ...]], ...] = ()
    # context entries: (ContextKeyName, ContextKeyType, ContextKeyValues)


@dataclass
class Result:
    check: Check
    decision: str  # raw decision string from IAM, or "error:<msg>"

    @property
    def actual_bucket(self) -> str:
        """Map the raw decision into 'allowed' / 'denied' / '<raw>' for display."""
        if self.decision in ALLOWED_DECISIONS:
            return "allowed"
        if self.decision in DENIED_DECISIONS:
            return "denied"
        return self.decision

    @property
    def passed(self) -> bool:
        return self.actual_bucket == self.check.expected


# ── The seven checks ──────────────────────────────────────────────────


def _build_checks() -> list[Check]:
    return [
        Check(
            label="sagemaker:InvokeEndpoint on healthcare-autogluon",
            action="sagemaker:InvokeEndpoint",
            resource=AUTOGLUON_ENDPOINT_ARN,
            expected="allowed",
        ),
        Check(
            label="sagemaker:InvokeEndpoint on healthcare-tabpfn",
            action="sagemaker:InvokeEndpoint",
            resource=TABPFN_ENDPOINT_ARN,
            expected="allowed",
        ),
        Check(
            label="sagemaker:InvokeEndpoint on some-other-endpoint",
            action="sagemaker:InvokeEndpoint",
            resource=OUT_OF_SCOPE_ENDPOINT_ARN,
            expected="denied",
        ),
        Check(
            label="s3:GetObject on preprocessing/final_clinical_df.csv",
            action="s3:GetObject",
            resource=SYNTHEA_CLINICAL_OBJECT_ARN,
            expected="allowed",
        ),
        Check(
            label="s3:GetObject on some-other-bucket/file.csv",
            action="s3:GetObject",
            resource=OUT_OF_SCOPE_OBJECT_ARN,
            expected="denied",
        ),
        Check(
            label="s3:ListBucket on Synthea bucket with s3:prefix=preprocessing/data",
            action="s3:ListBucket",
            resource=SYNTHEA_BUCKET_ARN,
            expected="allowed",
            context=(
                ("s3:prefix", "string", ("preprocessing/data",)),
            ),
        ),
        Check(
            label="s3:ListBucket on some-other-bucket",
            action="s3:ListBucket",
            resource=OUT_OF_SCOPE_BUCKET_ARN,
            # NOTE: The role's AmazonHealthLakeFullAccess managed policy
            # grants s3:ListBucket on Resource:"*" account-wide. Req 5.5
            # requires we preserve that policy, so account-wide
            # ListBucket is inherited — it is NOT something
            # ModelInferenceAgentAccessPolicy introduces. Expected
            # outcome is "allowed" to reflect the real, preserved state.
            expected="allowed",
        ),
    ]


# ── IAM simulation driver ─────────────────────────────────────────────


def _simulate(iam_client, check: Check) -> Result:
    """Run one SimulatePrincipalPolicy call and extract the decision."""
    kwargs: dict = {
        "PolicySourceArn": ROLE_ARN,
        "ActionNames": [check.action],
        "ResourceArns": [check.resource],
    }
    if check.context:
        kwargs["ContextEntries"] = [
            {
                "ContextKeyName": name,
                "ContextKeyType": type_,
                "ContextKeyValues": list(values),
            }
            for (name, type_, values) in check.context
        ]

    try:
        response = iam_client.simulate_principal_policy(**kwargs)
    except (BotoCoreError, ClientError) as exc:
        return Result(check=check, decision=f"error:{exc}")

    results = response.get("EvaluationResults") or []
    if not results:
        return Result(check=check, decision="error:no EvaluationResults returned")

    # We send one action + one resource per call, so we always want the
    # first (and only) result row.
    decision = results[0].get("EvalDecision", "error:missing EvalDecision")
    return Result(check=check, decision=decision)


def _print_table(results: Iterable[Result]) -> None:
    """Print a compact table of each check's expected vs actual outcome."""
    rows = list(results)
    label_w = max(len(r.check.label) for r in rows)
    print()
    header = f"{'check'.ljust(label_w)}  expected  actual    decision"
    print(header)
    print("-" * len(header))
    for r in rows:
        status = "PASS" if r.passed else "FAIL"
        print(
            f"{r.check.label.ljust(label_w)}  "
            f"{r.check.expected.ljust(8)}  "
            f"{r.actual_bucket.ljust(8)}  "
            f"{r.decision}  [{status}]"
        )
    print()


def main() -> int:
    iam = boto3.client("iam")
    checks = _build_checks()

    print(f"Simulating {len(checks)} assertions against {ROLE_ARN} ...")

    results = [_simulate(iam, c) for c in checks]
    _print_table(results)

    failures = [r for r in results if not r.passed]
    if failures:
        print(
            f"FAILED: {len(failures)} of {len(results)} assertion(s) did not match.",
            file=sys.stderr,
        )
        for r in failures:
            print(
                f"  - {r.check.label}: expected {r.check.expected}, "
                f"got {r.actual_bucket} (raw={r.decision})",
                file=sys.stderr,
            )
        return 1

    print(f"OK: all {len(results)} assertions match expected outcomes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
