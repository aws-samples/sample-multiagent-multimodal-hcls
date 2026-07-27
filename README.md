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

## Installation

```bash
pip install -r requirements.txt
# or: uv sync
```

## Running

Deploy the agents/MCP servers to Amazon Bedrock AgentCore using the `deploy*.py` scripts, then
start the frontend:

```bash
cd frontend
npm install
npm run dev
```

See the per-directory READMEs (e.g. `agents/model-inference-agent/README.md`)
for component-specific instructions.

## Security

All account IDs, Cognito identifiers, resource ARNs, and passwords in this
repository are placeholders. Replace them with your own values, and never
commit real secrets. Use AWS Secrets Manager or environment variables for
sensitive configuration.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
