# Multi-Agent, Multi-Modal Healthcare & Life Sciences Sample

A sample project demonstrating a multi-agent, multi-modal architecture for
healthcare and life sciences (HCLS) use cases, built on
[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/),
[Strands Agents](https://strandsagents.com/), and the
[Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

An orchestrator agent routes user requests to specialist agents that query
biomedical data sources (PubMed, ClinicalTrials.gov, AWS HealthLake,
HealthImaging, HealthOmics) and invoke AI model endpoints for predictive analytics.

> **Note**: This is sample/educational code. It is not intended for production
> use without further security, reliability, and compliance review.

## Business context

### The problem: multimodal HCLS data is siloed and hard to question

Healthcare and life sciences organizations accumulate data across fundamentally
different modalities — structured clinical records (FHIR), medical imaging
(DICOM), genomic variants, peer-reviewed literature, and clinical-trial
registries. Each modality lives in its own purpose-built store, speaks its own
vocabulary, and traditionally requires its own domain expert to query. The
pipelines that stitch them together are rigid: adding a new question ("do this
patient's genomic variants change how I read their imaging findings?")
typically means new integration code, and ad-hoc cross-modality analysis is out
of reach for most clinicians and researchers.

### The approach: a fleet of specialized agents behind one conversation

This sample answers that with a multi-agent architecture. Each data modality
gets its own specialized agent with domain-scoped prompts and tools, connected
to its data store through MCP servers. A supervisor (orchestrator) agent is the
single entry point: it interprets the user's intent, routes each question to
the right specialists — in parallel when a question spans sources — and
synthesizes their outputs into one coherent answer.

| Agent | Data source | What it answers |
|-------|-------------|-----------------|
| Clinical | AWS HealthLake (FHIR R4) | Medication history, active diagnoses, encounters, observations |
| Imaging | AWS HealthImaging (DICOM) | Image-set search, DICOM metadata, imaging findings |
| Genomic | Amazon S3 Tables (Apache Iceberg) | Variant lookups, ClinVar gene–disease associations |
| PubMed | NCBI E-utilities via AgentCore Gateway | Peer-reviewed literature evidence (38M+ citations) |
| Clinical trials | ClinicalTrials.gov v2 API via AgentCore Gateway | Recruiting studies, eligibility criteria, outcomes |
| Model inference | Amazon SageMaker AI endpoints | Disease-risk prediction from multimodal features |

The payoff is that a clinician or researcher can ask natural-language questions
across all of these silos from a single chat interface — cohort exploration,
literature grounding, trial matching, and risk assessment — without knowing
FHIR search syntax, DICOM tags, or SQL over Iceberg tables. Retrieval agents
answer "what does the data say?"; the model inference agent extends the system
into predictive analytics — "what is likely to happen?" — supporting workflows
such as risk stratification, interpretable triage, evidence-grounded findings,
and trial recruitment.

All data is the Synthea Coherent synthetic multimodal cohort. It contains no
PHI, and predictions are **not for clinical use** — this is a demonstration of
the architecture, not a medical device.

## Repository layout

| Path | Description |
|------|-------------|
| `main_agent.py` | Orchestrator agent that routes requests to specialist agents |
| `agents/` | Specialist agents (PubMed, ClinicalTrials, HealthLake, HealthImaging, HealthOmics, browser automation, model inference) |
| `mcp_servers/` | MCP servers exposing biomedical data-source tools |
| `mcp_clients/` | MCP client helpers |
| `frontend/` | React + Vite web UI (Amplify-hosted) |
| `notebooks/` | Data preprocessing and model-training notebooks |
| `deploy*.py` | Deployment scripts for AgentCore runtimes |
| `utils/` | Shared utilities (auth token helpers, etc.) |

## Prerequisites

- Python 3.11+
- An AWS account with access to Amazon Bedrock AgentCore
- Node.js 18+ (for the frontend)
- [`uv`](https://github.com/astral-sh/uv) (optional, for dependency management)

## Configuration

This project reads runtime configuration from an `env` file (loaded via
`python-dotenv`) and the frontend reads from `frontend/.env`. Neither file is
committed. Copy the provided templates and fill in your own account-specific
values:

```bash
cp env.example env
cp frontend/.env.example frontend/.env
```

Then edit `env` and `frontend/.env` to point at your own AWS account ID, Cognito
user pool / client, and AgentCore runtime ARNs. The browser automation agent
additionally expects a `NOVA_ACT_API_KEY` environment variable.

**Do not commit real credentials, API keys, or account-specific ARNs.**

## How to run

### 1. Install

```bash
pip install -r requirements.txt
# or: uv sync
```

Or use the Makefile, which creates a `uv` virtual environment and installs the
package:

```bash
make setup install
```

### 2. Deploy the agents

Deploy the agents and MCP servers to Amazon Bedrock AgentCore:

```bash
python deploy.py            # or: make deploy
```

This packages each agent with the `bedrock-agentcore-starter-toolkit`, creates
its AgentCore Memory resource, and deploys it as an AgentCore runtime (A2A
protocol for specialist agents, MCP for tool servers) fronted by a Cognito JWT
authorizer. Container images are built with AWS CodeBuild, so no local Docker
daemon is required. Additional scripts cover partial redeploys
(`deploy_orchestrator_only.py`, `deploy_clinicaltrials.py`), and the model
inference agent's SageMaker endpoints are provisioned from its own directory —
see `agents/model-inference-agent/README.md`.

### 3. Start the frontend

```bash
cd frontend
npm install
./setup-env.sh   # writes frontend/.env
npm run dev
```

The chat application is available at `http://localhost:5173`.

## How to interact with the agents

Sign in through Amazon Cognito (Amplify Authenticator), then ask
natural-language questions in the chat. Responses stream over Server-Sent
Events, tool invocations are shown inline with expandable inputs and results,
and an Agent Architecture view visualizes how your question is decomposed
across agents. A session ID maintains multi-turn continuity, so follow-up
questions build on earlier answers.

The orchestrator decides which specialist handles each question. Example
prompts and their routing:

- *"Search ClinicalTrials.gov for common side effects reported for the newest
  versions of blood thinners (like Eliquis or Xarelto)."* → **clinical trials
  agent**, which queries the ClinicalTrials.gov v2 API through AgentCore
  Gateway and reasons over study titles, sponsors, eligibility criteria, and
  outcomes.
- *"Are there any recent studies on PubMed about taking statins at night versus
  in the morning for better cholesterol control?"* → **PubMed agent**, which
  searches NCBI E-utilities and returns titles, publication dates, abstracts,
  and links to the source articles.
- *"What is the likelihood of patient `182c006c` having coronary heart
  disease?"* → **model inference agent**, which runs its prediction pipeline
  against SageMaker endpoints and returns the probability, confidence band,
  cross-model consistency, contributing factors, and a synthetic-data
  disclaimer.

Questions that span sources ("predict this patient's stroke risk and cite
supporting literature") are decomposed by the orchestrator: the model inference
agent produces the prediction, the PubMed agent supplies the evidence, and the
orchestrator synthesizes both into one answer.

You can also invoke a deployed runtime directly for smoke-testing — see
`invoke_agent.py` for a minimal example using
`bedrock-agentcore.invoke_agent_runtime` with an SSE-streamed response.

## Security

All account IDs, Cognito identifiers, resource ARNs, and passwords in this
repository are placeholders. Replace them with your own values, and never
commit real secrets. Use AWS Secrets Manager or environment variables for
sensitive configuration.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
