#!/usr/bin/env python3
"""
Deploy only the orchestrator with updated routing logic
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
logger.info("Deploying Orchestrator with Updated Routing Logic")
logger.info("=" * 80)

# Deploy orchestrator
logger.info("Configuring orchestrator...")
orchestrator_runtime = Runtime()

response = orchestrator_runtime.configure(
    entrypoint="main_agent.py",
    execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role",
    auto_create_ecr=True,
    requirements_file="requirements.txt",
    agent_name="orchestrator",
    region="us-west-2",
    authorizer_configuration={
        "customJWTAuthorizer": {
            "allowedClients": [cognito_config.get("client_id")],
            "discoveryUrl": cognito_config.get("discovery_url"),
        }
    }
)

logger.info(f"Configuration completed: {response}")

logger.info("Launching orchestrator...")
logger.info("This will take 5-10 minutes. Building container and deploying to AgentCore...")

agent_launch_result = orchestrator_runtime.launch(
    auto_update_on_conflict=True,
    env_vars={"OTEL_PYTHON_EXCLUDED_URLS": "/ping,/invocations"}
)

logger.info(f"Launch initiated: {agent_launch_result}")

# Monitor deployment status
logger.info("Monitoring deployment status...")
end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']

while True:
    try:
        status_response = orchestrator_runtime.status()
        status = status_response.endpoint['status']
        
        logger.info(f"Status: {status}")
        
        if status in end_status:
            if status == 'READY':
                logger.info("=" * 80)
                logger.info("✅ Orchestrator deployment SUCCESSFUL!")
                logger.info("=" * 80)
                logger.info(f"Agent ARN: {status_response.endpoint.get('arn', 'N/A')}")
                logger.info("")
                logger.info("🧪 Test with this query:")
                logger.info("   'Search ClinicalTrials.gov for side effects of Eliquis'")
                logger.info("")
                logger.info("Expected: Tool should be 'send_clinicaltrials_message'")
                logger.info("=" * 80)
            else:
                logger.error(f"❌ Deployment failed with status: {status}")
            break
            
        time.sleep(15)
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        time.sleep(15)

logger.info("Deployment complete!")
