# Model Inference Agent

Multimodal disease-prediction agent (formerly internal codename "AEGIS") packaged as a
Bedrock AgentCore Runtime exposing an A2A endpoint. Supported diseases: Hypertension,
Stroke, Coronary Heart Disease, Alzheimer's.

## Spec

The authoritative design, requirements, and task plan for the V1 SMUS integration live at:

- `.kiro/specs/model-inference-agent-smus-integration/` (in the Kiro workspace at the
  root of the developer laptop, not in this repo)

This directory (`model-inference-agent/`) is the source tree committed into the SMUS
project repo `datazone-4leduybk99hj80-dev` per Requirement 10.1.

## Target AWS Resources (V1)

All resources live in account `123456789012`, region `us-west-2`.

- **Runtime**: AgentCore Runtime `model_inference_agent` (A2A, PUBLIC network mode)
- **Execution role**: `arn:aws:iam::123456789012:role/agentcore-workshop-role`
  (shared with the other AgentCore runtimes)
- **Authorizer**: Cognito JWT — pool `us-west-2_EXAMPLE`, app client
  `EXAMPLECLIENTID123`
- **ECR repo (agent image)**:
  `123456789012.dkr.ecr.us-west-2.amazonaws.com/bedrock-agentcore-model_inference_agent`
- **Memory**: AgentCore Memory `model_inference_agent_mem` (STM_ONLY, short-term
  session state)
- **SageMaker endpoints**: `healthcare-autogluon`, `healthcare-tabpfn` (built from
  `sagemaker/autogluon/` and `sagemaker/tabpfn/` via CodeBuild, PUBLIC network mode)
- **Data**: S3 bucket `synthea-coherent-data-multimodal`, prefix `preprocessing/`
- **SSM**: runtime ARN published at `/agents/model-inference-agent`
- **CodeBuild project**: `bedrock-agentcore-model_inference_agent-builder`
- **CodeBuild source bucket**:
  `bedrock-agentcore-codebuild-sources-123456789012-us-west-2`

## Single-Command Deploy (Req 10.5)

The V1 deployment workflow is runnable via a single documented command sequence that:

1. Builds the two SageMaker container images (`healthcare-autogluon`, `healthcare-tabpfn`)
   via AWS CodeBuild — no local Docker daemon required (Req 10.7).
2. Creates the two SageMaker Model / EndpointConfig / Endpoint resources and waits for
   `InService` (Req 3.5–3.7).
3. Builds the agent container image via CodeBuild and pushes to the
   `bedrock-agentcore-model_inference_agent` ECR repo.
4. Creates the AgentCore Memory resource `model_inference_agent_mem` (idempotent).
5. Deploys the AgentCore Runtime `model_inference_agent` (A2A, PUBLIC, JWT authorizer,
   observability enabled) and waits for status `READY`.
6. Writes the deployed runtime ARN to SSM at `/agents/model-inference-agent` (Req 10.9).

Re-running the sequence against an unchanged source tree is idempotent and does not
create duplicate ECR repos, SageMaker models, runtimes, Memory resources, or SSM
parameters (Req 10.8).

The orchestrator redeploy (v16 → v17) lives in a separate bundle
(`Orchestrator_Source_Bundle`) and is not part of this directory — see Req 10.4.

## Contents

- `Dockerfile` — agent container build
- `src/` — in-container Strands `@tool` pipeline and A2A entrypoint
- `sagemaker/` — AutoGluon and TabPFN endpoint Dockerfiles and inference code
- `models/exported/` — model artifacts used by the SageMaker endpoints
- `tests/` — unit and Hypothesis property tests (10 preserved v3 properties + the new
  round-trip property)
- `infra/` — deployment scripts and IAM policy documents
- `.bedrock_agentcore.yaml` — runtime configuration (account, region, ECR, execution
  role, authorizer, memory, codebuild)

## Non-Goals (V1)

Enumerated in requirements Req 12. Of note: no new Lambda functions, no Streamlit UI,
no VPC isolation, no cds-ui source changes, no duplicate PubMed tooling (literature
search is delegated to `pubmed_agent_a2a` via the `send_pubmed_query` tool).
