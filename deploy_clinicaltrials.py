#!/usr/bin/env python3
"""
Deploy Clinical Trials MCP Server with API fixes
"""
import time
from bedrock_agentcore_starter_toolkit import Runtime
from logger import logger

# Cognito configuration
cognito_config = {
    'pool_id': "us-west-2_EXAMPLE",
    'client_id': "EXAMPLECLIENTID123",
    'discovery_url': "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_EXAMPLE/.well-known/openid-configuration"
}

logger.info("=" * 80)
logger.info("Deploying Clinical Trials MCP Server with API Fixes")
logger.info("=" * 80)

# Deploy Clinical Trials MCP
logger.info("Configuring Clinical Trials MCP server...")
ct_runtime = Runtime()

response = ct_runtime.configure(
    entrypoint="mcp_servers/clinicaltrials/clinicaltrials.py",
    execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role",
    auto_create_ecr=True,
    requirements_file="requirements.txt",
    region="us-west-2",
    agent_name="clinicaltrials",
    authorizer_configuration={
        "customJWTAuthorizer": {
            "allowedClients": [cognito_config.get("client_id")],
            "discoveryUrl": cognito_config.get("discovery_url"),
        }
    },
    protocol="MCP"
)

logger.info(f"Configuration completed: {response}")

logger.info("Launching Clinical Trials MCP server...")
logger.info("This will take 5-10 minutes...")

launch_result = ct_runtime.launch(
    auto_update_on_conflict=True,
    env_vars={"OTEL_PYTHON_EXCLUDED_URLS": "/ping,/invocations"}
)

logger.info(f"Launch initiated: {launch_result}")

# Monitor deployment status
logger.info("Monitoring deployment status...")
end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']

while True:
    try:
        status_response = ct_runtime.status()
        status = status_response.endpoint['status']
        
        logger.info(f"Status: {status}")
        
        if status in end_status:
            if status == 'READY':
                logger.info("=" * 80)
                logger.info("✅ Clinical Trials MCP deployment SUCCESSFUL!")
                logger.info("=" * 80)
                logger.info(f"Agent ARN: {status_response.endpoint.get('arn', 'N/A')}")
            else:
                logger.error(f"❌ Deployment failed with status: {status}")
            break
            
        time.sleep(15)
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        time.sleep(15)

logger.info("Deployment complete!")
