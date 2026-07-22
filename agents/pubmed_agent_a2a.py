import datetime
import os
import logging
import asyncio
import sys

from bedrock_agentcore.memory import MemoryClient
from boto3 import Session
from dotenv import load_dotenv
from strands import Agent
from strands.multiagent.a2a import A2AServer
from fastapi import FastAPI
import uvicorn

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memory.memory_hook import ShortTermMemoryHook
from utils.utils import get_mcp_client, get_bearer_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
runtime_url = os.environ.get('AGENTCORE_RUNTIME_URL', 'http://127.0.0.1:9000/')
host, port = "0.0.0.0", 9000

load_dotenv("env")
mcp_server_arn = os.environ["PUBMED_MCP_ARN"]
pubmed_agent_id = f"pubmed-user-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
PUBMED_PROMPT = """
You are a specialized healthcare and life science research assistant. 
You will use pubmed to find articles relevant to users query and provide factual, well-sourced information for the questions.
"""

def create_agent_with_mcp():
    """Create agent with MCP tools properly integrated"""
    logger.info("Creating agent with MCP client...")
    
    # Get bearer token and MCP client
    bearer_token = get_bearer_token(os.environ["CLIENT_ID"], os.environ["USERNAME"], os.environ["PASSWORD"])
    mcp_client = get_mcp_client(mcp_server_arn, bearer_token)
    
    logger.info(f"MCP client created: {mcp_client}")
    
    # Create memory hook
    pubmed_memory_hook = ShortTermMemoryHook(
        memory_id=os.environ["MEMORY_ID"],
        memory_client=MemoryClient(region_name=Session().region_name),
        actor_id=pubmed_agent_id,
        session_id="dummy"
    )
    
    # Use MCP client within context manager to get tools - following the working pattern
    with mcp_client as client:
        mcp_tools = client.list_tools_sync()
        logger.info(f"MCP tools retrieved: {mcp_tools}")
        logger.info(f"Number of MCP tools: {len(mcp_tools) if mcp_tools else 0}")
        
        # Create agent with the actual MCP tools
        agent = Agent(
            system_prompt=PUBMED_PROMPT,
            hooks=[pubmed_memory_hook],
            tools=mcp_tools,  # Pass the actual tools, not the client
            name="Pubmed agent",
            description="An agent to query biomedical literature from pubmed",
        )
        
        logger.info("Agent created successfully with MCP tools")
        return agent, mcp_client  # Return both agent and client to keep client alive

# Create the agent with MCP client
agent, mcp_client = create_agent_with_mcp()

# Keep the MCP client active by entering its context
active_client = mcp_client.__enter__()

# Create A2A server
a2a_server = A2AServer(
    agent=agent,
    http_url=runtime_url,
    serve_at_root=True
)

@app.get("/ping")
def ping():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    """Initialize A2A server on startup"""
    logger.info("A2A server starting up...")
    # logger.info(f"Agent tools: {len(agent.tools) if agent.tools else 0}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up MCP client on shutdown"""
    try:
        if mcp_client:
            mcp_client.__exit__(None, None, None)
            logger.info("MCP client cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up MCP client: {e}")

app.mount("/", a2a_server.to_fastapi_app())

if __name__ == "__main__":
    uvicorn.run(app, host=host, port=port)