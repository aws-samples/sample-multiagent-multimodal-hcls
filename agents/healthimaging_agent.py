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
import sys

load_dotenv("env")

# Try to get MCP server ARN from environment, fallback to local server
healthimaging_mcp_server_arn = os.environ.get("HEALTHIMAGING_MCP_ARN")
healthimaging_agent_id = f"healthimaging-user-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

HEALTHIMAGING_PROMPT = """
You are a specialized medical imaging and DICOM data assistant. 
You have access to AWS HealthImaging services and can help with:
- Listing and managing medical imaging datastores
- Retrieving DICOM image sets and metadata
- Analyzing medical imaging data
- Processing healthcare imaging workflows
- Extracting clinical information from imaging studies

Use the available tools to help users with medical imaging queries and provide accurate, 
well-sourced information about imaging data and DICOM resources.
"""

@tool
def healthimaging_agent(query: str) -> str:
    """
    Specialized agent for medical imaging and DICOM data analysis.
    Can access AWS HealthImaging datastores, image sets, and metadata.
    
    Args:
        query (str): User query related to medical imaging, DICOM data, or imaging workflows
        
    Returns:
        str: Response with imaging data analysis and information
    """
    try:
        # Set up memory hook for conversation context
        healthimaging_memory_hook = ShortTermMemoryHook(
            memory_id=os.environ.get("MEMORY_ID", "default-memory"),
            memory_client=MemoryClient(region_name=Session().region_name),
            actor_id=healthimaging_agent_id,
            session_id=os.environ.get("session_id", "default-session")
        )

        # Try to connect to remote MCP server first
        if healthimaging_mcp_server_arn:
            logger.info("Connecting to remote HealthImaging MCP server...")
            bearer_token = get_bearer_token(
                os.environ.get("CLIENT_ID"), 
                os.environ.get("USERNAME"), 
                os.environ.get("PASSWORD")
            )
            mcp_client = get_mcp_client(healthimaging_mcp_server_arn, bearer_token)
            
            with mcp_client as client:
                mcp_tools = client.list_tools_sync()
                logger.info(f"Remote MCP tools: {[tool.tool_name for tool in mcp_tools]}")
                
                imaging_agent = Agent(
                    hooks=[healthimaging_memory_hook], 
                    system_prompt=HEALTHIMAGING_PROMPT, 
                    tools=mcp_tools
                )
                response = imaging_agent(query)
                return response
        
        else:
            # Fallback to local MCP server or direct function calls
            logger.info("Using local HealthImaging MCP server...")
            
            # Try to import and use local healthimaging functions
            try:
                sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_servers', 'healthimaging'))
                import healthImaging
                
                # Create a simple agent with direct function access
                from strands.models import BedrockModel
                
                bedrock_model = BedrockModel(
                    model_config={
                        "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                        "max_tokens": 2048,
                        "temperature": 0.5,
                    },
                )
                
                # Create tools from healthimaging functions
                @tool
                def list_datastores(max_results: int = None) -> str:
                    """List all AWS HealthImaging datastores"""
                    return healthImaging.list_datastores(max_results)
                
                @tool
                def get_datastore(datastore_id: str) -> str:
                    """Get detailed information about a specific datastore"""
                    return healthImaging.get_datastore(datastore_id)
                
                @tool
                def list_image_sets(datastore_id: str, max_results: int = None) -> str:
                    """List DICOM image sets in a datastore"""
                    return healthImaging.list_image_sets(datastore_id, max_results)
                
                @tool
                def get_image_set(datastore_id: str, image_set_id: str) -> str:
                    """Get details of a specific DICOM image set"""
                    return healthImaging.get_image_set(datastore_id, image_set_id)
                
                @tool
                def get_image_set_metadata(datastore_id: str, image_set_id: str) -> str:
                    """Get DICOM metadata from an image set"""
                    return healthImaging.get_image_set_metadata(datastore_id, image_set_id)
                
                # Create agent with local tools
                imaging_agent = Agent(
                    hooks=[healthimaging_memory_hook],
                    system_prompt=HEALTHIMAGING_PROMPT,
                    tools=[list_datastores, get_datastore, list_image_sets, get_image_set, get_image_set_metadata],
                    model=bedrock_model
                )
                
                response = imaging_agent(query)
                return response.message['content'][0]['text'] if hasattr(response, 'message') else str(response)
                
            except Exception as local_error:
                logger.error(f"Local HealthImaging MCP error: {local_error}")
                
                # Final fallback - return informative message
                return f"""I'm a HealthImaging specialist agent, but I'm currently unable to connect to the imaging services.
                
Query received: {query}

I would normally help you with:
- Listing medical imaging datastores
- Retrieving DICOM image sets
- Analyzing imaging metadata
- Processing healthcare imaging workflows

Please ensure the HealthImaging MCP server is running or AWS credentials are properly configured."""

    except Exception as e:
        logger.error(f"HealthImaging agent error: {e}")
        return f"I encountered an error while processing your imaging query: {str(e)}"


# Standalone function for direct use
def create_healthimaging_agent():
    """Create a standalone HealthImaging agent instance"""
    try:
        from strands.models import BedrockModel
        
        bedrock_model = BedrockModel(
            model_config={
                "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "max_tokens": 2048,
                "temperature": 0.5,
            },
        )
        
        # Import local healthimaging functions
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_servers', 'healthimaging'))
        import healthImaging
        
        # Create tools
        @tool
        def list_datastores(max_results: int = None) -> str:
            """List all AWS HealthImaging datastores with their basic properties"""
            return healthImaging.list_datastores(max_results)
        
        @tool
        def get_datastore(datastore_id: str) -> str:
            """Retrieve detailed information about a specific HealthImaging datastore"""
            return healthImaging.get_datastore(datastore_id)
        
        @tool
        def list_image_sets(datastore_id: str, max_results: int = None) -> str:
            """List all DICOM image sets stored within a specific datastore"""
            return healthImaging.list_image_sets(datastore_id, max_results)
        
        @tool
        def get_image_set(datastore_id: str, image_set_id: str) -> str:
            """Retrieve comprehensive details of a specific DICOM image set"""
            return healthImaging.get_image_set(datastore_id, image_set_id)
        
        @tool
        def get_image_set_metadata(datastore_id: str, image_set_id: str) -> str:
            """Extract DICOM metadata from an image set including patient and study information"""
            return healthImaging.get_image_set_metadata(datastore_id, image_set_id)
        
        # Create and return agent
        return Agent(
            system_prompt=HEALTHIMAGING_PROMPT,
            tools=[list_datastores, get_datastore, list_image_sets, get_image_set, get_image_set_metadata],
            model=bedrock_model
        )
        
    except Exception as e:
        logger.error(f"Failed to create HealthImaging agent: {e}")
        return None


if __name__ == "__main__":
    # Test the agent
    test_query = "List all available medical imaging datastores and show me details about the first one"
    result = healthimaging_agent(test_query)
    print("HealthImaging Agent Response:")
    print(result)