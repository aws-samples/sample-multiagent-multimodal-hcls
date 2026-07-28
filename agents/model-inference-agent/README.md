# Model Inference Agent

The Model Inference Agent is the predictive-analytics specialist in the multi-agent
multimodal data analysis use case. Where the other specialized agents retrieve and reason
over clinical, imaging, genomic, literature, and clinical-trial data, this agent turns a
patient's multimodal features into a disease-likelihood prediction. It is built with the
Strands Agents SDK, deployed as an Amazon Bedrock AgentCore runtime, and exposed over the
Agent-to-Agent (A2A) protocol so the supervisor agent can discover and invoke it at
runtime.

Supported diseases: Hypertension, Stroke, Coronary Heart Disease, and Alzheimer's.

## How it fits into the multi-agent system

The supervisor agent is the entry point for end users. It interprets intent, routes each
question to the appropriate specialized agents, and synthesizes their outputs into a
single coherent answer. When a user asks about a patient's disease risk, the supervisor
delegates to the Model Inference Agent over A2A. The agent runs its prediction pipeline
against trained models served on Amazon SageMaker AI and returns a structured result —
probability, confidence, model consistency, contributing factors, and a disclaimer.

The agent focuses on predicting the likelihood of patients experiencing certain outcomes 
(e.g. hypertension, stroke, coronary heart disease, and alzheimer's). When a prediction should be grounded in
peer-reviewed evidence, it does not search the literature itself; instead it calls the
PubMed agent over A2A (via the `send_pubmed_query` tool), keeping responsibilities cleanly
separated across the fleet of single-purpose agents.

## How it works

- **In-container tools.** The prediction pipeline (`parse_query`, `load_patient_data`,
  `select_model`, `run_inference`, `format_response`) is implemented as Strands `@tool`
  functions that run inside the agent container. There are no separate Lambda functions.
- **Dual-model inference.** `run_inference` calls two SageMaker real-time endpoints —
  AutoGluon and TabPFN — and returns both a primary and a secondary prediction so the
  agent can report how consistent the two models are.
- **Grounded explanations.** For literature-backed answers, the agent delegates to the
  PubMed agent rather than duplicating any PubMed tooling.
- **Session context.** Short-term session state is held in Amazon Bedrock AgentCore
  Memory so follow-up questions stay grounded in prior turns.
- **Secure by default.** Every invocation is authenticated with an Amazon Cognito-issued
  JWT, and traces and logs flow to Amazon CloudWatch through AgentCore observability.

The data is the Synthea Coherent synthetic multimodal cohort (clinical, genomic, and
imaging features). It contains no PHI and is intended for demonstration only.

## Deployed AWS resources

All resources live in account `524256002118`, region `us-west-2`.

| Resource | Value |
|----------|-------|
| AgentCore runtime | `model_inference_agent` (A2A, PUBLIC network mode) |
| Execution role | `arn:aws:iam::524256002118:role/agentcore-workshop-role` (shared with the other runtimes) |
| Authorizer | Amazon Cognito JWT — pool `us-west-2_fsfWygjJr`, app client `46js50p9pols3p6taij2oh4a3n` |
| Agent image (ECR) | `524256002118.dkr.ecr.us-west-2.amazonaws.com/bedrock-agentcore-model_inference_agent` |
| Memory | `model_inference_agent_mem` (short-term session state) |
| SageMaker endpoints | `healthcare-autogluon`, `healthcare-tabpfn` (PUBLIC network mode) |
| Data | S3 bucket `synthea-coherent-data-multimodal`, prefix `preprocessing/` |
| Runtime ARN (SSM) | `/agents/model-inference-agent` |
| CodeBuild project | `bedrock-agentcore-model_inference_agent-builder` |
| CodeBuild source bucket | `bedrock-agentcore-codebuild-sources-524256002118-us-west-2` |

## Deploying the agent

The agent is packaged and deployed with the `bedrock-agentcore-starter-toolkit`. All
container images are built with AWS CodeBuild, so no local Docker daemon is required. A
single deployment sequence:

1. Builds the two SageMaker container images (`healthcare-autogluon`, `healthcare-tabpfn`)
   via CodeBuild.
2. Creates the two SageMaker Model, EndpointConfig, and Endpoint resources and waits for
   each to reach `InService`.
3. Builds the agent container image via CodeBuild and pushes it to the agent ECR
   repository.
4. Creates the AgentCore Memory resource `model_inference_agent_mem`.
5. Deploys the `model_inference_agent` runtime (A2A, PUBLIC network mode, Cognito JWT
   authorizer, observability enabled) and waits for status `READY`.
6. Publishes the deployed runtime ARN to SSM at `/agents/model-inference-agent`.

The sequence is idempotent: re-running it against an unchanged source tree does not
create duplicate ECR repositories, SageMaker models, runtimes, Memory resources, or SSM
parameters.

To make the supervisor route disease-prediction questions to this agent, register a tool
on the supervisor that points to the runtime ARN above and update the supervisor's system
prompt. That change is delivered separately from this directory as part of the supervisor
(orchestrator) source bundle.

## Repository layout

| Path | Purpose |
|------|---------|
| `Dockerfile` | Agent container build |
| `src/` | In-container Strands `@tool` pipeline and the A2A entrypoint |
| `sagemaker/` | AutoGluon and TabPFN endpoint Dockerfiles and inference code |
| `models/exported/` | Model artifacts served by the SageMaker endpoints |
| `tests/` | Unit tests and Hypothesis property-based tests |
| `infra/` | Deployment scripts and IAM policy documents |
| `.bedrock_agentcore.yaml` | Runtime configuration (account, region, ECR, execution role, authorizer, memory, CodeBuild) |

## Scope

To keep the agent single-purpose, the integration deliberately avoids new Lambda
functions, a standalone UI, VPC isolation, and any duplicate PubMed tooling — literature
search is delegated to the PubMed agent. Users reach this agent through the existing chat
application and the supervisor agent's routing, not by calling it directly.
