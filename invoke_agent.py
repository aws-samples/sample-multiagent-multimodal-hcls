import boto3
from dotenv import load_dotenv
import os
import json

load_dotenv("env")

agent_arn = "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/multimodal_agent-EXAMPLE"

agentcore_client = boto3.client(
    'bedrock-agentcore',
    region_name="us-west-2"
)

boto3_response = agentcore_client.invoke_agent_runtime(
    agentRuntimeArn=agent_arn,
    qualifier="DEFAULT",
    payload=json.dumps({"prompt": "What are the tools you can access?"})
)
if "text/event-stream" in boto3_response.get("contentType", ""):
    content = []
    for line in boto3_response["response"].iter_lines(chunk_size=1):
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                line = line[6:]
                logger.info(line)
                content.append(line)
    print("\n".join(content))
else:
    try:
        events = []
        for event in boto3_response.get("response", []):
            events.append(event)
    except Exception as e:
        events = [f"Error reading EventStream: {e}"]
    print(events[0].decode("utf-8"))