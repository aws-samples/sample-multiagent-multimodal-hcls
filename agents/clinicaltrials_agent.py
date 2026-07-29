import os
from typing import Dict, Any
from strands import Agent, tool
from boto3.session import Session
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from utils import setup_env, get_mcp_client, get_bearer_token
from dotenv import load_dotenv
from mcp.types import TextContent
from memory.memory_hook import ShortTermMemoryHook
from bedrock_agentcore.memory import MemoryClient
import datetime
from logger import logger
import asyncio
import json


load_dotenv("env")
mcp_server_arn = os.environ["CLINICAL_TRIALS_MCP_ARN"]
clinicaltrials_agent_id = f"clinicaltrials-user-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
CLINICALTRIALS_PROMPT = """
You are a specialized healthcare and life science assistant. 
You will use clinical trials tools to find clinical trials relevant to users query and provide factual, well-sourced information for the questions.
"""

@tool
def clinicaltrials_agent(query: str) -> str:
    """
    Search ClinicalTrials.gov for active and completed clinical trials.
    
    Use this tool for:
    - Finding clinical trials for specific diseases or conditions
    - Checking trial eligibility and enrollment status
    - Locating recruiting studies and research opportunities
    - Exploring experimental treatments and therapies
    - Identifying trial phases, locations, and sponsors
    
    Args:
        query: The search query for clinical trials (e.g., "lung cancer trials", "diabetes phase 3")
        
    Returns:
        Information about relevant clinical trials including status, locations, and eligibility
    """
    clinicaltrials_memory_hook = ShortTermMemoryHook(
        memory_id=os.environ["MEMORY_ID"],
        memory_client=MemoryClient(region_name=Session().region_name),
        actor_id=clinicaltrials_agent_id,
        session_id="dummy"
    )

    bearer_token = get_bearer_token(os.environ["CLIENT_ID"], os.environ["USERNAME"], os.environ["PASSWORD"])
    mcp_client = get_mcp_client(mcp_server_arn, bearer_token)
    
    with mcp_client as client:
        mcp_tools = client.list_tools_sync()
        print(mcp_tools)
        clinicaltrials_agent = Agent(hooks=[clinicaltrials_memory_hook], system_prompt=CLINICALTRIALS_PROMPT, tools=mcp_tools)
        response = clinicaltrials_agent(query)
        return response
    
