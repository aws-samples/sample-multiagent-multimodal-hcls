import asyncio
import json
import logging
import os
from uuid import uuid4

import boto3
import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart
from bedrock_agentcore import RequestContext
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from boto3.session import Session
from dotenv import load_dotenv
from fastapi import HTTPException
from strands import Agent, tool
from urllib.parse import quote

from utils import get_bearer_token

load_dotenv("env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app = BedrockAgentCoreApp()

# ── Agent Registry ────────────────────────────────────────────────────────────
REGISTRY_NAME = "healthcare-agents"
REGION = os.environ.get("AWS_DEFAULT_REGION", Session().region_name or "us-west-2")


def load_agents_from_registry() -> dict:
    """
    Discover all agents registered in the Agent Registry.
    Returns a dict: agent_name -> {arn, protocol, description, keywords}
    Falls back to hardcoded values if registry is unavailable.
    """
    try:
        control = boto3.client("bedrock-agentcore-control", region_name=REGION)

        regs = control.list_registries()
        registry = next(
            (r for r in regs.get("registries", []) if r["name"] == REGISTRY_NAME),
            None,
        )
        if not registry:
            raise ValueError(f"Registry '{REGISTRY_NAME}' not found")

        registry_id = registry["registryId"]
        logger.info(f"Loading agents from registry: {registry_id}")

        records = control.list_registry_records(registryId=registry_id)
        agents = {}
        for record in records.get("registryRecords", []):
            name = record["name"]
            full = control.get_registry_record(
                registryId=registry_id, recordId=record["recordId"]
            )
            descriptor = full.get("descriptors", {}).get("custom", {})
            content = json.loads(descriptor.get("inlineContent", "{}"))
            agents[name] = {
                "arn": content.get("agentRuntimeArn"),
                "protocol": content.get("protocol", "A2A"),
                "description": record.get("description", ""),
                "keywords": content.get("keywords", []),
            }
            logger.info(f"Discovered agent: {name} ({agents[name]['protocol']}) -> {agents[name]['arn']}")

        return agents

    except Exception as e:
        logger.warning(f"Registry load failed ({e}), using fallback config")
        return {
            "pubmed": {
                "arn": os.environ.get("PUBMED_AGENT_ARN", "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/pubmed_agent_a2a-EXAMPLE"),
                "protocol": "A2A",
                "description": "Search PubMed for biomedical literature and research papers",
                "keywords": ["research", "paper", "literature", "pubmed", "mechanism"],
            },
            "clinicaltrials": {
                "arn": os.environ.get("CLINICAL_TRIALS_MCP_ARN", "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/clinicaltrials-EXAMPLE"),
                "protocol": "MCP",
                "description": "Search ClinicalTrials.gov for clinical trials",
                "keywords": ["clinical trial", "trial", "recruiting", "enrollment", "phase"],
            },
        }


REGISTERED_AGENTS = load_agents_from_registry()
logger.info(f"Loaded {len(REGISTERED_AGENTS)} agents from registry: {list(REGISTERED_AGENTS.keys())}")

# ── HTTP / A2A helpers ────────────────────────────────────────────────────────

def create_message(text: str, role: Role = Role.user) -> Message:
    return Message(
        kind="message",
        role=role,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
    )


def format_agent_response(response) -> str:
    try:
        if isinstance(response, Message):
            if response.parts:
                part = response.parts[0]
                if hasattr(part, "text"):
                    return part.text
                if hasattr(part, "root") and hasattr(part.root, "text"):
                    return part.root.text

        if hasattr(response, "artifacts") and response.artifacts:
            artifact = response.artifacts[0]
            if hasattr(artifact, "parts") and artifact.parts:
                p = artifact.parts[0]
                if hasattr(p, "root") and hasattr(p.root, "text"):
                    return p.root.text

        if hasattr(response, "history") and response.history:
            texts = []
            for msg in response.history:
                if (
                    hasattr(msg, "role")
                    and hasattr(msg.role, "value")
                    and msg.role.value == "agent"
                    and hasattr(msg, "parts")
                    and msg.parts
                ):
                    p = msg.parts[0]
                    if hasattr(p, "root") and hasattr(p.root, "text"):
                        texts.append(p.root.text)
                    elif hasattr(p, "text"):
                        texts.append(p.text)
            if texts:
                return "".join(texts)

        if hasattr(response, "parts") and response.parts:
            for p in response.parts:
                if hasattr(p, "text"):
                    return p.text
                if hasattr(p, "root") and hasattr(p.root, "text"):
                    return p.root.text

        return str(response)
    except Exception as e:
        logger.error(f"Error formatting response: {e}")
        return str(response)


MCP_PROMPT = "You are a helpful assistant. Use the available tools to answer the user's query accurately."


def send_mcp_agent_message(message: str, agent_arn: str) -> str:
    """Call an MCP agent synchronously."""
    from strands.tools.mcp import MCPClient
    from mcp.client.streamable_http import streamablehttp_client
    from strands import Agent as StrandsAgent

    bearer_token = get_bearer_token(
        os.environ["CLIENT_ID"], os.environ["USERNAME"], os.environ["PASSWORD"]
    )
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    headers = {"authorization": f"Bearer {bearer_token}", "Content-Type": "application/json"}

    mcp_client = MCPClient(lambda: streamablehttp_client(mcp_url, headers=headers))
    with mcp_client as client:
        mcp_tools = client.list_tools_sync()
        mcp_agent = StrandsAgent(system_prompt=MCP_PROMPT, tools=mcp_tools)
        response = mcp_agent(message)
        return str(response)


async def send_agent_message(message: str, agent_name: str) -> str:
    """Send a message to a registered agent, routing by protocol (MCP or A2A)."""
    agent_info = REGISTERED_AGENTS.get(agent_name)
    if not agent_info:
        return f"Error: agent '{agent_name}' not found in registry"

    agent_arn = agent_info["arn"]
    protocol = agent_info.get("protocol", "A2A")

    try:
        if protocol == "MCP":
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, send_mcp_agent_message, message, agent_arn)

        # A2A protocol
        bearer_token = get_bearer_token(
            os.environ["CLIENT_ID"], os.environ["USERNAME"], os.environ["PASSWORD"]
        )
        escaped_arn = quote(agent_arn, safe="")
        runtime_url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{escaped_arn}/invocations/"
        session_id = str(uuid4())
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        }

        async with httpx.AsyncClient(timeout=300, headers=headers) as httpx_client:
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=runtime_url)
            agent_card = await resolver.get_agent_card()
            client = ClientFactory(ClientConfig(httpx_client=httpx_client, streaming=False)).create(agent_card)
            msg = create_message(text=message)
            async for event in client.send_message(msg):
                if isinstance(event, Message):
                    return format_agent_response(event)
                elif isinstance(event, tuple) and len(event) == 2:
                    task, _ = event
                    return format_agent_response(task)
                else:
                    return format_agent_response(event)

        return "No response received"
    except Exception as e:
        logger.error(f"Error calling agent '{agent_name}': {e}")
        return f"Error: {str(e)}"


# ── Auto-generate tools for every registered agent ────────────────────────────

def make_agent_tool(name: str, info: dict):
    """Dynamically create a @tool function for a registered agent."""
    description = info["description"]
    keywords = ", ".join(info.get("keywords", []))

    async def _agent_tool(message: str) -> str:
        return await send_agent_message(message, name)

    _agent_tool.__name__ = f"send_{name}_message"
    _agent_tool.__doc__ = (
        f"{description}\n\nKeywords: {keywords}\n\nArgs:\n    message: The query to send."
    )
    return tool(_agent_tool)


agent_tools = [make_agent_tool(name, info) for name, info in REGISTERED_AGENTS.items()]
logger.info(f"Auto-generated tools: {[f'send_{n}_message' for n in REGISTERED_AGENTS]}")

# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    rules = []
    for i, (name, info) in enumerate(REGISTERED_AGENTS.items(), 1):
        kw = ", ".join(f'"{k}"' for k in info.get("keywords", []))
        rules.append(
            f"{i}. Use send_{name}_message for: {info['description']}.\n"
            f"   Keywords: {kw}"
        )
    rules_text = "\n\n".join(rules)

    return f"""You are a healthcare life science orchestrator that routes queries to specialized agents.

REGISTERED AGENTS AND ROUTING RULES:
{rules_text}

GUIDELINES:
- Route queries accurately based on the keywords above
- If a query spans multiple agents, call them in parallel
- Keep responses concise and actionable
- When in doubt about clinical trials, use send_clinicaltrials_message
"""


# ── Entrypoint ────────────────────────────────────────────────────────────────

@app.entrypoint
async def main(payload, context: RequestContext):
    orchestrator_agent = Agent(
        system_prompt=build_system_prompt(),
        tools=agent_tools,
        name="Orchestration Agent",
        description="An agent to orchestrate sub-agents discovered from the Agent Registry",
    )
    user_input = payload.get("prompt", "")
    if not user_input:
        raise HTTPException(status_code=400, detail="No prompt provided")
    logger.info(f"Query: {user_input[:100]}...")
    async for event in orchestrator_agent.stream_async(user_input):
        yield event


if __name__ == "__main__":
    app.run()
