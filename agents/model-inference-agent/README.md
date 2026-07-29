# Model Inference Agent

The predictive-analytics specialist in the multi-agent system: given a patient ID and a
disease, it turns the patient's multimodal features into a disease-likelihood prediction
served from Amazon SageMaker AI endpoints. For the overall architecture, business
context, deployment of the full system, and how to interact with the agents, see the
[root README](../../README.md).

Supported diseases: Hypertension, Stroke, Coronary Heart Disease, and Alzheimer's.
Built with the Strands Agents SDK, deployed as an Amazon Bedrock AgentCore runtime, and
exposed over the Agent-to-Agent (A2A) protocol so the orchestrator can discover and
invoke it.

## Prediction pipeline

The agent exposes a single high-level `predict_disease` tool that chains five
in-container steps for a natural-language query such as *"What is the likelihood of
patient 182c006c having coronary heart disease?"*:

1. **`parse_query`** — extracts the patient ID and maps disease aliases ("chd", "heart
   disease", "coronary artery disease") to a supported disease target and its SNOMED CT
   code. Unsupported diseases or missing patient IDs return structured errors
   (`DISEASE_NOT_SUPPORTED`, `INVALID_QUERY`, `MISSING_FIELD`) instead of guesses.
2. **`load_patient_data`** — assembles the patient's preprocessed multimodal feature
   vector (clinical + imaging + genomic) from Amazon S3.
3. **`select_model`** — picks the primary and secondary model for the disease based on
   benchmark performance (see table below).
4. **`run_inference`** — invokes both SageMaker real-time endpoints in parallel
   (AutoGluon and TabPFN) and collects both probabilities.
5. **`format_response`** — computes confidence and cross-model consistency, extracts the
   top contributing features, and attaches the synthetic-data disclaimer.

All five steps run as Strands `@tool` functions inside the agent container — there are
no separate Lambda functions. For literature-backed answers, the agent delegates to the
PubMed agent over A2A via `send_pubmed_query`; it never calls PubMed directly.

## Models and benchmarks

For each disease, two tabular models are trained on the combined-modality feature set:
**AutoGluon** (an AutoML ensemble that stacks classical learners and handles mixed
clinical, imaging, and genomic features without manual tuning) and **TabPFN** (a
transformer-based prior-fitted network suited to small tabular datasets). The
better-performing model per disease is the primary; the other serves as a secondary
check.

| Disease | SNOMED CT | Primary model | AutoGluon F1 | TabPFN F1 |
|---------|-----------|---------------|--------------|-----------|
| Hypertension | 59621000 | AutoGluon | 0.909 | 0.833 |
| Stroke | 230690007 | AutoGluon | 1.000 | 1.000 |
| Coronary Heart Disease | 53741008 | AutoGluon | 0.667 | 0.000 |
| Alzheimer's Disease | 26929004 | TabPFN | 0.400 | 0.857 |

Every prediction reports the probability, a confidence band (`high` ≥ 0.75, `medium`
≥ 0.50, else `low`), cross-model consistency (agreement within 0.15), the top
contributing features, and a verbatim disclaimer that results use synthetic data and are
not for clinical use. Disease configs, benchmark scores, and thresholds live in
`src/config.py`.

## Deploying this agent

Container images are built with AWS CodeBuild — no local Docker daemon required. Run
from this directory:

```bash
# 1. Build the two SageMaker serving containers via CodeBuild.
python infra/build_sagemaker_containers.py

# 2. Create the SageMaker Model / EndpointConfig / Endpoint for each model and
#    wait for both to reach InService (~5–8 min each).
python infra/create_endpoints.py

# 3. Build the agent image, deploy the AgentCore runtime (A2A, Cognito JWT
#    authorizer, observability on), create the Memory resource, and publish the
#    runtime ARN to SSM at /agents/model-inference-agent.
agentcore launch
```

The sequence is idempotent: re-running it against an unchanged source tree does not
create duplicate ECR repositories, SageMaker models, runtimes, Memory resources, or SSM
parameters. The PubMed A2A agent must already be deployed (override its runtime ARN with
the `PUBMED_AGENT_ARN` environment variable if needed), and the preprocessed feature
data must be available in S3.

To make the orchestrator route disease-prediction questions to this agent, register a
tool on the orchestrator pointing to the deployed runtime ARN and update its system
prompt.

## Directory layout

| Path | Purpose |
|------|---------|
| `Dockerfile` | Agent container build |
| `src/` | In-container Strands `@tool` pipeline and the A2A entrypoint (`src/main.py`) |
| `src/config.py` | Disease configs, SNOMED codes, benchmark F1 scores, confidence/consistency thresholds |
| `sagemaker/` | AutoGluon and TabPFN endpoint Dockerfiles and inference code |
| `models/exported/` | Model artifacts served by the SageMaker endpoints |
| `tests/` | Unit tests and Hypothesis property-based tests |
| `infra/` | Deployment scripts and IAM policy documents |
| `.bedrock_agentcore.yaml` | Runtime configuration (account, region, ECR, execution role, authorizer, memory, CodeBuild) |

## Scope

To keep the agent single-purpose, the integration deliberately avoids new Lambda
functions, a standalone UI, VPC isolation, and any duplicate PubMed tooling. Users reach
this agent through the chat application and the orchestrator's routing, not by calling
it directly.
