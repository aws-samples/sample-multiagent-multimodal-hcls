"""Validator for the Model Inference Agent IAM policy.

Rejects overly broad grants that would violate Requirements 5.1, 5.2, 5.3,
5.6, and 5.7 of the `model-inference-agent-smus-integration` spec.

Usage
-----
Importable:

    from validate_policy import validate
    violations = validate(policy_dict)   # -> list[str]; empty means OK

CLI:

    python validate_policy.py path/to/policy.json
    # exit code 0 → no violations
    # exit code 1 → violations printed to stderr, one per line

Scope
-----
The validator is intentionally specific to this agent's policy document.
It does not try to be a general IAM linter — it enforces the narrow
least-privilege rules called out in the spec.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable

# ── Module constants exposed for tests and external callers ───────────

ALLOWED_POLICY_VERSION: str = "2012-10-17"
"""The only IAM policy version we accept."""

ALLOWED_SAGEMAKER_ENDPOINT_ARNS: tuple[str, ...] = (
    "arn:aws:sagemaker:us-west-2:123456789012:endpoint/healthcare-autogluon",
    "arn:aws:sagemaker:us-west-2:123456789012:endpoint/healthcare-tabpfn",
)
"""The exact SageMaker endpoint ARNs the agent may invoke. Req 5.1."""

ALLOWED_S3_BUCKET_ARN: str = "arn:aws:s3:::synthea-coherent-data-multimodal"
"""The single S3 bucket ARN the policy may reference. Req 5.2, 5.3, 5.7."""

ALLOWED_S3_OBJECT_RESOURCE: str = (
    "arn:aws:s3:::synthea-coherent-data-multimodal/preprocessing/*"
)
"""The only object-level S3 resource the policy may reference. Req 5.2."""

ALLOWED_SERVICES: frozenset[str] = frozenset({"s3", "sagemaker"})
"""The only AWS service action prefixes allowed in the policy."""

_WILDCARD_ACTIONS: frozenset[str] = frozenset({"*", "s3:*", "sagemaker:*"})
"""Actions we reject outright — they always over-grant."""


# ── Internal helpers ──────────────────────────────────────────────────


def _as_list(value: Any) -> list[Any]:
    """Normalize an IAM field that may be a scalar or a list into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _service_of(action: str) -> str | None:
    """Extract the service prefix of an IAM action like `s3:GetObject`."""
    if not isinstance(action, str) or ":" not in action:
        return None
    return action.split(":", 1)[0].lower()


def _is_wildcard_action(action: str) -> bool:
    if not isinstance(action, str):
        return False
    if action in _WILDCARD_ACTIONS:
        return True
    # Defend against whitespace / casing tricks, e.g. " S3:* ".
    return action.strip().lower() in _WILDCARD_ACTIONS


def _s3_bucket_of(resource: str) -> str | None:
    """Return the bucket ARN prefix of an `arn:aws:s3:::bucket[/key]` resource."""
    if not isinstance(resource, str) or not resource.startswith("arn:aws:s3:::"):
        return None
    # arn:aws:s3:::bucket or arn:aws:s3:::bucket/key
    tail = resource[len("arn:aws:s3:::") :]
    bucket = tail.split("/", 1)[0]
    return f"arn:aws:s3:::{bucket}"


def _is_sagemaker_wildcard_resource(resource: str) -> bool:
    if not isinstance(resource, str):
        return False
    if resource == "*":
        return True
    # Any SageMaker resource ARN containing a wildcard is rejected.
    return resource.startswith("arn:aws:sagemaker:") and "*" in resource


# ── Core validator ────────────────────────────────────────────────────


def _validate_statement(
    stmt: Any,
    index: int,
    violations: list[str],
) -> None:
    prefix = f"Statement[{index}]"

    if not isinstance(stmt, dict):
        violations.append(f"{prefix}: must be an object")
        return

    effect = stmt.get("Effect")
    if effect != "Allow":
        # We only grant permissions in this policy — Deny statements are
        # out of scope for the agent policy and would be suspicious here.
        violations.append(f"{prefix}: Effect must be 'Allow' (got {effect!r})")
        return

    actions = _as_list(stmt.get("Action"))
    resources = _as_list(stmt.get("Resource"))
    condition = stmt.get("Condition") or {}

    if not actions:
        violations.append(f"{prefix}: missing Action")
    if not resources:
        violations.append(f"{prefix}: missing Resource")

    # Service + wildcard checks on every action.
    services_in_stmt: set[str] = set()
    for action in actions:
        if _is_wildcard_action(action):
            violations.append(
                f"{prefix}: wildcard action {action!r} is not allowed"
            )
            continue
        service = _service_of(action)
        if service is None:
            violations.append(
                f"{prefix}: malformed action {action!r} (expected 'service:Operation')"
            )
            continue
        if service not in ALLOWED_SERVICES:
            violations.append(
                f"{prefix}: action {action!r} uses disallowed service {service!r}"
            )
            continue
        services_in_stmt.add(service)

    # Per-service resource scoping.
    if "sagemaker" in services_in_stmt:
        for resource in resources:
            if _is_sagemaker_wildcard_resource(resource):
                violations.append(
                    f"{prefix}: SageMaker resource {resource!r} uses a wildcard"
                )
                continue
            if resource not in ALLOWED_SAGEMAKER_ENDPOINT_ARNS:
                violations.append(
                    f"{prefix}: SageMaker resource {resource!r} is not on the allow-list"
                )

    if "s3" in services_in_stmt:
        for resource in resources:
            if resource == "*":
                violations.append(f"{prefix}: S3 resource '*' is not allowed")
                continue
            bucket_arn = _s3_bucket_of(resource)
            if bucket_arn is None:
                violations.append(
                    f"{prefix}: malformed S3 resource {resource!r}"
                )
                continue
            if bucket_arn != ALLOWED_S3_BUCKET_ARN:
                violations.append(
                    f"{prefix}: S3 resource {resource!r} is outside the allowed bucket"
                )
                continue
            # Resource is in the allowed bucket. Object-level resources must
            # point at the preprocessing prefix only.
            if "/" in resource[len("arn:aws:s3:::") :]:
                if resource != ALLOWED_S3_OBJECT_RESOURCE:
                    violations.append(
                        f"{prefix}: S3 object resource {resource!r} is outside "
                        "preprocessing/*"
                    )

        # ListBucket must carry an s3:prefix condition (Req 5.3).
        if any(a == "s3:ListBucket" for a in actions if isinstance(a, str)):
            prefixes = _collect_list_bucket_prefixes(condition)
            if not prefixes:
                violations.append(
                    f"{prefix}: s3:ListBucket requires an s3:prefix condition"
                )
            else:
                for p in prefixes:
                    if not (isinstance(p, str) and p.startswith("preprocessing/")):
                        violations.append(
                            f"{prefix}: s3:prefix {p!r} is not scoped to preprocessing/*"
                        )


def _collect_list_bucket_prefixes(condition: Any) -> list[Any]:
    """Return every value seen under any operator's `s3:prefix` key."""
    if not isinstance(condition, dict):
        return []
    found: list[Any] = []
    for op_value in condition.values():
        if not isinstance(op_value, dict):
            continue
        if "s3:prefix" in op_value:
            found.extend(_as_list(op_value["s3:prefix"]))
    return found


def validate(policy: Any) -> list[str]:
    """Return a list of violation strings. Empty list means the policy is OK."""
    violations: list[str] = []

    if not isinstance(policy, dict):
        return ["Policy must be a JSON object"]

    version = policy.get("Version")
    if version != ALLOWED_POLICY_VERSION:
        violations.append(
            f"Version must be {ALLOWED_POLICY_VERSION!r} (got {version!r})"
        )

    statements = policy.get("Statement")
    if statements is None:
        violations.append("Policy is missing required 'Statement' field")
        return violations

    stmt_list = _as_list(statements)
    if not stmt_list:
        violations.append("Policy 'Statement' must contain at least one statement")
        return violations

    for i, stmt in enumerate(stmt_list):
        _validate_statement(stmt, i, violations)

    return violations


# ── CLI entry point ───────────────────────────────────────────────────


def _main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Model Inference Agent IAM policy document.",
    )
    parser.add_argument(
        "policy_path",
        help="Path to the IAM policy JSON file to validate.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        with open(args.policy_path, "r", encoding="utf-8") as fh:
            policy = json.load(fh)
    except OSError as exc:
        print(f"error: could not read {args.policy_path}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: {args.policy_path} is not valid JSON: {exc}", file=sys.stderr)
        return 2

    violations = validate(policy)
    if violations:
        print(
            f"Policy {args.policy_path} has {len(violations)} violation(s):",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"Policy {args.policy_path} OK — 0 violations")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_main())
