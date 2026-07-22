import os
import asyncio
import boto3
import json
import sys
from boto3.session import Session
from logger import logger
import requests
from typing import Optional
from datetime import datetime

import strands
from strands.tools.mcp import MCPClient
from strands import Agent
from strands.models import BedrockModel
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from botocore.exceptions import ClientError
from utils import get_bearer_token
from dotenv import load_dotenv
from agents.pubmed_agent import pubmed_agent
from agents.clinicaltrials_agent import clinicaltrials_agent
from agents.healthimaging_agent import healthimaging_agent

import logging
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()])

load_dotenv("env")
session_id = f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}"
os.environ["session_id"] = session_id

if __name__ == "__main__":

    bedrock_model = BedrockModel(
        model_config={
            "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "max_tokens": 2048,
            "temperature": 0.5,
        },
    )
    
    ORCHESTRATOR_PROMPT = (
        "You are a helpful healthcare life science assistant that can use various tools to answer questions."
        "You can use tools to search pubmed for biomedical literature"
        "You can use tools to search clinicaltrials.gov for clinical trials"
        "You can use tools to access medical imaging data and DICOM files from AWS HealthImaging"
        "Use the tools to perform the task given by user and provide factual information to the user"
    )

    orchestrator_agent = Agent(
        system_prompt=ORCHESTRATOR_PROMPT,
        tools = [pubmed_agent, clinicaltrials_agent, healthimaging_agent],
        model=bedrock_model
    )

    while True:
        user_input = input("\nYour request: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            break
        logger.info("\n🤔 Processing...\n")
        response = orchestrator_agent(user_input)