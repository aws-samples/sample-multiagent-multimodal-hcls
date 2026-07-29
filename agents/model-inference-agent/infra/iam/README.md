# Model Inference Agent — IAM Policy

This directory holds the least-privilege IAM policy that extends the shared
`agentcore-workshop-role` so the Model Inference Agent runtime can call its
two SageMaker endpoints and read Synthea preprocessing data from S3.

## Files

- `model-inference-agent-access-policy.json` — the policy document. It is
  attached as an inline policy named `ModelInferenceAgentAccessPolicy` on
  `agentcore-workshop-role` (task 2.2).
- `validate_policy.py` — a guard that fails the deploy if the policy
  overgrants. Importable (`from validate_policy import validate`) and
  runnable as a CLI (`python validate_policy.py path/to/policy.json`).

## What the policy grants

| Sid                               | Action                   | Resource                                                                                                                              |
| --------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `InvokeSageMakerEndpointsOnly`    | `sagemaker:InvokeEndpoint` | `arn:aws:sagemaker:us-west-2:123456789012:endpoint/healthcare-autogluon` and `.../healthcare-tabpfn` (exact ARNs, no wildcards)       |
| `GetSyntheaPreprocessingObjects`  | `s3:GetObject`           | `arn:aws:s3:::synthea-coherent-data-multimodal/preprocessing/*`                                                                        |
| `ListSyntheaPreprocessingPrefix`  | `s3:ListBucket`          | `arn:aws:s3:::synthea-coherent-data-multimodal` with `StringLike` `s3:prefix` = `preprocessing/*`                                      |

## What the validator rejects

`validate_policy.py` returns a non-empty violation list (and a non-zero CLI
exit code) on any of the following:

- Wrong `Version` (anything other than `2012-10-17`).
- Missing or empty `Statement`.
- Any wildcard action — `*`, `s3:*`, or `sagemaker:*`.
- Any action whose service prefix is not `s3` or `sagemaker`.
- Any SageMaker resource that is not one of the two allow-listed endpoint
  ARNs, or any SageMaker resource containing a wildcard.
- Any S3 resource outside `synthea-coherent-data-multimodal`, or any
  object-level S3 resource outside `preprocessing/*`.
- `s3:ListBucket` without an `s3:prefix` condition, or with an `s3:prefix`
  that is not scoped to `preprocessing/*`.

## Requirements coverage

The policy and validator together enforce:

- **Req 5.1** — `sagemaker:InvokeEndpoint` scoped to the two endpoint ARNs only.
- **Req 5.2** — `s3:GetObject` on `preprocessing/*` only.
- **Req 5.3** — `s3:ListBucket` with a `preprocessing/*` prefix condition.
- **Req 5.6** — deploy must fail if `sagemaker:InvokeEndpoint` is granted on `*`.
- **Req 5.7** — no `s3:*` on any bucket other than `synthea-coherent-data-multimodal`.

## TODO (task 2.2)

Task 2.2 wires `validate_policy.py` into `infra/deploy.sh` as a pre-attach
guard: the deploy script will call the validator against
`model-inference-agent-access-policy.json` and refuse to attach the policy
to `agentcore-workshop-role` if the validator reports any violations. This
README will be updated with the exact `deploy.sh` snippet once that task is
implemented.
