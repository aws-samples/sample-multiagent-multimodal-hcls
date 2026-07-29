import datetime
import os

from bedrock_agentcore.memory import MemoryClient
from boto3.session import Session
from dotenv import load_dotenv
from strands import Agent, tool

from memory.memory_hook import ShortTermMemoryHook
from utils import get_mcp_client, get_bearer_token

load_dotenv("env")
mcp_server_arn = os.environ["PUBMED_MCP_ARN"]
pubmed_agent_id = f"pubmed-user-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
PUBMED_PROMPT = """
You are a specialized healthcare and life science research assistant. 
You will use pubmed to find articles relevant to users query and provide factual, well-sourced information for the questions.
"""

@tool
def pubmed_agent(query: str) -> str:
    """
    Search PubMed for biomedical literature, research papers, and scientific articles.
    
    Use this tool for:
    - Finding published research papers and scientific studies
    - Understanding disease mechanisms and pathophysiology
    - Reviewing scientific evidence for treatments
    - Exploring molecular biology and biochemistry topics
    - Literature reviews and meta-analyses
    
    Args:
        query: The search query for PubMed literature
        
    Returns:
        Relevant research articles and scientific information
    """
    pubmed_memory_hook = ShortTermMemoryHook(
        memory_id=os.environ["MEMORY_ID"],
        memory_client=MemoryClient(region_name=Session().region_name),
        actor_id=pubmed_agent_id,
        session_id="dummy"
    )

    bearer_token = get_bearer_token(os.environ["CLIENT_ID"], os.environ["USERNAME"], os.environ["PASSWORD"])
    mcp_client = get_mcp_client(mcp_server_arn, bearer_token)
    
    with mcp_client as client:
        mcp_tools = client.list_tools_sync()
        print(mcp_tools)
        pubmed_agent = Agent(hooks=[pubmed_memory_hook], system_prompt=PUBMED_PROMPT, tools=mcp_tools)
        response = pubmed_agent(query)
        return response
    
