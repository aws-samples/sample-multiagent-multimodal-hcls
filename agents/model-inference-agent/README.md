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

### The problem: multimodal HCLS data is siloed and hard to question

Healthcare and life sciences (HCLS) organizations accumulate data across fundamentally
different modalities — structured clinical records (FHIR), medical imaging (DICOM),
genomic variants, peer-reviewed literature, and clinical-trial registries. Each modality
lives in its own purpose-built store, speaks its own vocabulary, and traditionally
requires its own domain expert to query. The pipelines that stitch them together are
rigid: adding a new question ("do this patient's genomic variants change how I read their
imaging findings?") typically means new integration code, and ad-hoc cross-modality
analysis is out of reach for most clinicians and researchers.

### The approach: a fleet of specialized agents behind one conversation

This system (Part 2 of the *Multi-Agent Multimodal Data Analysis on AWS* series) answers
that with a multi-agent architecture built on Amazon Bedrock AgentCore and the Strands
Agents SDK. Each data modality gets its own specialized agent with domain-scoped prompts
and tools, connected to its data store through Model Context Protocol (MCP) servers. A
supervisor (orchestrator) agent is the single entry point: it interprets the user's
intent, routes each question to the right specialists — in parallel when a question spans
sources — and synthesizes their outputs into one coherent answer.

| Agent | Data source | What it answers |
|-------|-------------|-----------------|
| Clinical | AWS HealthLake (FHIR R4) | Medication history, active diagnoses, encounters, observations |
| Imaging | AWS HealthImaging (DICOM) | Image-set search, DICOM metadata, imaging findings |
| Genomic | Amazon S3 Tables (Apache Iceberg) | Variant lookups, ClinVar gene–disease associations |
| PubMed | NCBI E-utilities via AgentCore Gateway | Peer-reviewed literature evidence (38M+ citations) |
| Clinical trials | ClinicalTrials.gov v2 API via AgentCore Gateway | Recruiting studies, eligibility criteria, outcomes |
| **Model inference (this agent)** | **Amazon SageMaker AI endpoints** | **Disease-risk prediction from multimodal features** |

The business payoff is that a clinician or researcher can ask natural-language questions
across all of these silos from a single chat interface — cohort exploration, literature
grounding, trial matching, and risk assessment — without knowing FHIR search syntax,
DICOM tags, or SQL over Iceberg tables.

### Where this agent fits: from retrieval to prediction

Retrieval answers "what does the data say?" The Model Inference Agent extends the system
into **predictive analytics** — "what is likely to happen?" — by identifying patients at
elevated risk for a specific disease. This supports concrete workflows:

- **Risk stratification** — flag which patients in a cardiovascular cohort are at
  elevated risk of stroke or coronary heart disease, so care teams can prioritize.
- **Interpretable triage** — every prediction returns the top contributing features, so
  the risk estimate can be read alongside the same patient's clinical, imaging, and
  genomic context surfaced by the other agents rather than as an opaque score.
- **Evidence-grounded findings** — the agent can pair a prediction with peer-reviewed
  literature (delegated to the PubMed agent) linking the contributing risk factors to the
  disease.
- **Trial recruitment** — combined with the clinical-trials agent, predicted-risk
  patients can be matched against recruiting studies' eligibility criteria.

The models are trained on **combined clinical, imaging, and genomic features**, following
the finding from Part 1 of this series that combining modalities improves predictive
performance over any single modality alone. The training data is the Synthea Coherent
synthetic multimodal cohort: it contains no PHI, and every prediction carries a
disclaimer that results use synthetic data and are **not for clinical use**. This is a
demonstration of the architecture and modeling approach, not a medical device.

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
separated across the fleet of single-purpose agents. Because the prediction tool is
decoupled from the underlying endpoints, models can be retrained or new disease targets
added without changing the interface the supervisor depends on.

## How it works

### Prediction pipeline

The agent exposes a single high-level `predict_disease` tool that chains five
in-container steps for a natural-language query such as *"What is the likelihood of
patient 182c006c having coronary heart disease?"*:

1. **`parse_query`** — extracts the patient ID and maps disease aliases ("chd", "heart
   disease", "coronary artery disease") to a supported disease target and its SNOMED CT
   code. Unsupported diseases or missing patient IDs return structured errors
   (`DISEASE_NOT_SUPPORTED`, `INVALID_QUERY`) instead of guesses.
2. **`load_patient_data`** — assembles the patient's preprocessed multimodal feature
   vector (clinical + imaging + genomic) from Amazon S3.
3. **`select_model`** — picks the primary and secondary model for the disease based on
   benchmark performance (see table below).
4. **`run_inference`** — invokes both SageMaker real-time endpoints in parallel
   (AutoGluon and TabPFN) and collects both probabilities.
5. **`format_response`** — computes confidence and cross-model consistency, extracts the
   top contributing features, and attaches the synthetic-data disclaimer.

All five steps run as Strands `@tool` functions inside the agent container — there are no
separate Lambda functions to deploy or operate.

### Models and benchmarks

For each disease, two tabular models are trained on the combined-modality feature set:
**AutoGluon** (an AutoML ensemble that stacks classical learners and handles mixed
clinical, imaging, and genomic features without manual tuning) and **TabPFN** (a
transformer-based prior-fitted network suited to small tabular datasets). The
better-performing model per disease is the primary; the other serves as a secondary check.

| Disease | SNOMED CT | Primary model | AutoGluon F1 | TabPFN F1 |
|---------|-----------|---------------|--------------|-----------|
| Hypertension | 59621000 | AutoGluon | 0.909 | 0.833 |
| Stroke | 230690007 | AutoGluon | 1.000 | 1.000 |
| Coronary Heart Disease | 53741008 | AutoGluon | 0.667 | 0.000 |
| Alzheimer's Disease | 26929004 | TabPFN | 0.400 | 0.857 |

*(F1 scores on the combined-modality benchmark from the Part 1 training work; the spread
across diseases is itself a signal the agent surfaces rather than hides.)*

### Structured, calibrated responses

Rather than a bare probability, every prediction reports:

- **Probability** — the primary model's predicted likelihood.
- **Confidence band** — `high` (≥ 0.75), `medium` (≥ 0.50), or `low`, derived from the
  predicted probability.
- **Model consistency** — whether the AutoGluon and TabPFN probabilities agree within a
  0.15 threshold, so users can see when the two models disagree and weigh the result
  accordingly.
- **Contributing factors** — the top features driving the prediction, enabling
  interpretation against the patient's record.
- **Disclaimer** — verbatim notice that predictions use synthetic data and are not for
  clinical use.

### Platform behaviors

- **Literature delegation.** For evidence-backed answers, the agent calls the PubMed
  specialist agent over A2A via `send_pubmed_query` — it never duplicates PubMed tooling
  or searches literature itself.
- **Session context.** Short-term session state is held in Amazon Bedrock AgentCore
  Memory so follow-up questions ("what about stroke for the same patient?") stay grounded
  in prior turns.
- **Secure by default.** Every invocation is authenticated with an Amazon Cognito-issued
  JWT. Following least privilege, the agent's IAM role grants `sagemaker:InvokeEndpoint`
  only on the deployed endpoint ARNs and read-only access to the preprocessed feature
  data in S3.
- **Observable.** Traces and logs flow to Amazon CloudWatch through AgentCore
  observability, with OpenTelemetry support capturing agent reasoning, tool invocations,
  and multi-agent call chains.

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

- AWS CLI configured with credentials for the target account and region.
- Python 3.12 and the AgentCore CLI (`pip install bedrock-agentcore`).
- The PubMed A2A agent already deployed (its runtime ARN is the default in
  `src/config.py`; override with the `PUBMED_AGENT_ARN` environment variable if needed).
- The preprocessed multimodal feature data from Part 1 available in S3.

### Deployment sequence

Run from the agent directory (`agents/model-inference-agent/`):

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

### Through the chat application (normal path)

End users reach this agent through the **React chat application** (hosted on AWS Amplify)
and the supervisor agent's routing — not by calling this runtime directly. Users
authenticate through Amazon Cognito via the Amplify Authenticator, so only authorized
users can access the system. The chat interface streams responses over Server-Sent
Events, rendering incremental text as the supervisor works; tool invocations are surfaced
inline with expandable sections showing which specialized agent was called and with what
inputs, and an Agent Architecture view visualizes the agent hierarchy and data-source
connections. A session ID maintains multi-turn continuity, so follow-up questions build
on earlier answers.

The supervisor decides which agent handles each question. Example prompts and their
routing:

- *"Search ClinicalTrials.gov for common side effects reported for the newest versions of
  blood thinners (like Eliquis or Xarelto)."* → **clinical trials agent**, which queries
  the ClinicalTrials.gov v2 API through AgentCore Gateway and reasons over study titles,
  sponsors, eligibility criteria, and outcomes.
- *"Are there any recent studies on PubMed about taking statins at night versus in the
  morning for better cholesterol control?"* → **PubMed agent**, which searches NCBI
  E-utilities and returns titles, publication dates, abstracts, and links to the source
  articles.
- *"What is the likelihood of patient `182c006c` having coronary heart disease?"* →
  **this Model Inference Agent**, which runs the five-step prediction pipeline against
  the SageMaker endpoints and returns the probability, confidence band, cross-model
  consistency, contributing factors, and disclaimer.

Questions that span sources ("predict this patient's stroke risk and cite supporting
literature") are decomposed by the supervisor: this agent produces the prediction and
delegates the evidence lookup to the PubMed agent, and the supervisor synthesizes both
into one answer.

### Calling this runtime directly (for testing)

You can also invoke the deployed runtime directly — for example, to smoke-test the
endpoint after deploying. Using the AWS SDK:

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
  one of the four supported diseases (common aliases like "high blood pressure", "cva",
  or "chd" are recognized). The agent never predicts from text alone — it always runs
  `predict_disease` against the SageMaker endpoints, and returns a structured error
  (`DISEASE_NOT_SUPPORTED`, `INVALID_QUERY`, `MISSING_FIELD`) rather than a fabricated
  answer when it can't.
- If you want supporting literature, say so in the request (e.g., "…and cite recent
  PubMed studies"). The agent delegates to the PubMed agent via `send_pubmed_query`; it
  never calls PubMed directly.
- Every prediction includes a disclaimer that the results use synthetic data and are not
  for clinical use.

## Repository layout

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
functions, a standalone UI, VPC isolation, and any duplicate PubMed tooling — literature
search is delegated to the PubMed agent. Users reach this agent through the existing chat
application and the supervisor agent's routing, not by calling it directly.
</content>
