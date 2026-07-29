# Model Inference Agent

The Model Inference Agent is the predictive-analytics specialist in the multi-agent
multimodal data analysis system. Where the other specialized agents retrieve and reason
over clinical, imaging, genomic, literature, and clinical-trial data, this agent turns a
patient's multimodal features into a disease-likelihood prediction. It is built with the
Strands Agents SDK, deployed as an Amazon Bedrock AgentCore runtime, and exposed over the
Agent-to-Agent (A2A) protocol so the supervisor agent can discover and invoke it at
runtime.

Supported diseases: Hypertension, Stroke, Coronary Heart Disease, and Alzheimer's.

## Business context

Healthcare and life sciences (HCLS) data keeps growing across modalities — clinical
records, medical imaging, and genomics — but the pipelines that analyze it are usually
rigid, hard to adapt to ad-hoc cross-modality questions, and require domain expertise for
each modality in isolation. This project addresses that with a multi-agent architecture:
a specialized AI agent for each data modality, each carrying its own domain knowledge and
tools, coordinated by a supervisor agent that decides which agents to invoke and how to
synthesize their outputs based on the user's question.

Retrieval alone answers "what does the data say?" The Model Inference Agent extends the
system into **predictive analytics** — "what is likely to happen?" — by identifying
patients at elevated risk for a specific disease. It is trained on combined clinical,
imaging, and genomic features, following the finding from Part 1 of this series that
combining modalities improves predictive performance over any single modality alone. Given
a disease and a patient ID, it assembles that patient's multimodal feature vector, invokes
a trained model served on Amazon SageMaker AI, and returns the predicted probability, the
top contributing features, and a disclaimer. Because the risk estimate is returned
alongside the features driving it, a clinician or researcher can interpret the prediction
in the context of the same patient's clinical, imaging, and genomic data surfaced by the
other agents — supporting use cases such as risk stratification, cohort triage, and trial
recruitment.

The data is the Synthea Coherent synthetic multimodal cohort. It contains no PHI, and the
predictions use synthetic data and are **not for clinical use** — this is a demonstration
of the architecture and modeling approach.

## How it fits into the multi-agent system

The supervisor agent is the entry point for end users. It interprets intent, routes each
question to the appropriate specialized agents, and synthesizes their outputs into a
single coherent answer. When a user asks about a patient's disease risk, the supervisor
delegates to the Model Inference Agent over A2A. The agent runs its prediction pipeline
against trained models served on Amazon SageMaker AI and returns a structured result —
probability, confidence, model consistency, contributing factors, and a disclaimer.

The agent focuses on prediction and nothing else. When a prediction should be grounded in
peer-reviewed evidence, it does not search the literature itself; instead it calls the
PubMed agent over A2A (via the `send_pubmed_query` tool), keeping responsibilities cleanly
separated across the fleet of single-purpose agents.

## How it works

- **In-container tools.** The prediction pipeline (`parse_query`, `load_patient_data`,
  `select_model`, `run_inference`, `format_response`) is implemented as Strands `@tool`
  functions that run inside the agent container. There are no separate Lambda functions.
  A single `predict_disease` tool chains all five steps for a natural-language query.
- **Dual-model inference.** `run_inference` calls two SageMaker real-time endpoints —
  AutoGluon and TabPFN — and returns both a primary and a secondary prediction so the
  agent can report how consistent the two models are.
- **Grounded explanations.** For literature-backed answers, the agent delegates to the
  PubMed agent rather than duplicating any PubMed tooling.
- **Session context.** Short-term session state is held in Amazon Bedrock AgentCore
  Memory so follow-up questions stay grounded in prior turns.
- **Secure by default.** Every invocation is authenticated with an Amazon Cognito-issued
  JWT, and traces and logs flow to Amazon CloudWatch through AgentCore observability.
  Following least privilege, the agent's IAM role grants `sagemaker:InvokeEndpoint` only
  on the deployed endpoint ARNs and read-only access to the preprocessed feature data.

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

## How to run (deploy the agent)

The agent is packaged and deployed with the `bedrock-agentcore-starter-toolkit`. All
container images are built with AWS CodeBuild, so **no local Docker daemon is required**.

### Prerequisites

- AWS CLI configured with credentials for account `524256002118` in `us-west-2`.
- Python 3.12 and the AgentCore CLI (`pip install bedrock-agentcore`).
- The PubMed A2A agent already deployed (its runtime ARN is the default in
  `src/config.py`; override with the `PUBMED_AGENT_ARN` environment variable if needed).

### Deployment sequence

Run from the agent directory (`source/agents/model-inference-agent/`):

```bash
# 1. Build the two SageMaker serving containers via CodeBuild (no local Docker).
python infra/build_sagemaker_containers.py

# 2. Create the SageMaker Model / EndpointConfig / Endpoint for each model and
#    wait for both to reach InService (~5–8 min each).
python infra/create_endpoints.py

# 3. Build the agent container image via CodeBuild, deploy the AgentCore runtime
#    (A2A, PUBLIC, Cognito JWT authorizer, observability on), create the Memory
#    resource, and publish the runtime ARN to SSM at /agents/model-inference-agent.
agentcore launch
```

This sequence:

1. Builds the two SageMaker container images (`healthcare-autogluon`, `healthcare-tabpfn`)
   via AWS CodeBuild.
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

## How to interact with the agent (post-deployment)

End users normally reach this agent through the **React chat application** (hosted on AWS
Amplify) and the supervisor agent's routing — not by calling this runtime directly. Users
authenticate with Amazon Cognito, ask a natural-language question, and watch the
supervisor delegate to the specialized agents in real time (responses stream over
Server-Sent Events, with tool invocations shown inline).

The supervisor decides which agent handles each question. Some examples span multiple
agents:

- *"Search ClinicalTrials.gov for common side effects reported for the newest versions of
  blood thinners (like Eliquis or Xarelto)."* → routed to the **clinical trials agent**.
- *"Are there any recent studies on PubMed about taking statins at night versus in the
  morning for better cholesterol control?"* → routed to the **PubMed agent**.
- *"What is the likelihood of patient `182c006c` having coronary heart disease?"* → routed
  to **this Model Inference Agent**, which runs the prediction pipeline and returns the
  probability, confidence, model consistency, contributing factors, and disclaimer.

### Calling this runtime directly (for testing)

You can also invoke the deployed runtime directly with a Cognito-issued bearer token — for
example, to smoke-test the endpoint after deploying. Using the AWS SDK:

```python
import boto3, json

# Look up the deployed runtime ARN published during deploy.
ssm = boto3.client("ssm", region_name="us-west-2")
agent_arn = ssm.get_parameter(Name="/agents/model-inference-agent")["Parameter"]["Value"]

client = boto3.client("bedrock-agentcore", region_name="us-west-2")
resp = client.invoke_agent_runtime(
    agentRuntimeArn=agent_arn,
    qualifier="DEFAULT",
    payload=json.dumps({
        "prompt": "What is the likelihood of patient 182c006c having coronary heart disease?"
    }),
)

# Responses stream as Server-Sent Events (text/event-stream).
if "text/event-stream" in resp.get("contentType", ""):
    for line in resp["response"].iter_lines(chunk_size=1):
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                print(line[6:])
```

Notes:

- Ask disease-risk questions with a **patient ID from the Synthea Coherent cohort** and
  one of the four supported diseases (Hypertension, Stroke, Coronary Heart Disease,
  Alzheimer's). The agent never predicts from text alone — it always runs
  `predict_disease` against the SageMaker endpoints.
- If you want supporting literature, add that to the request (e.g., "…and cite recent
  PubMed studies"). The agent delegates to the PubMed agent via `send_pubmed_query`; it
  never calls PubMed directly.
- Every prediction includes a disclaimer that the results use synthetic data and are not
  for clinical use.

## Repository layout

| Path | Purpose |
|------|---------|
| `Dockerfile` | Agent container build |
| `src/` | In-container Strands `@tool` pipeline and the A2A entrypoint (`src/main.py`) |
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
</content>
