import json
import os
import time
from typing import List, Dict

import boto3
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from logger import logger
from utils import setup_env

load_dotenv("env")

class MemoryManager:
    def __init__(self, 
    memory_name: str, 
    description: str = "agent memory", 
    strategies: List[str] = [],
    memory_expiration: int = 7,
    region: str = None):
        self.log = logger
        self.boto_session = Session()
        self.region = region or self.boto_session.region_name
        self.log.info(f"Region: {self.region}")
        self.memory_client = MemoryClient(region_name=self.region)
        self.memory_name = memory_name
        self.description = description
        self.strategies = strategies
        self.memory_expiration = memory_expiration
        self.memory_id = None

    def create_shortterm_memory(self) -> [str, None]:
        try:
            self.log.info("Creating short term memory...")
            memory = self.memory_client.create_memory_and_wait(
                name=self.memory_name,
                description=self.description,
                strategies=self.strategies,
                event_expiry_days=self.memory_expiration,
                max_wait=300,
                poll_interval=10
            )
            self.memory_id = memory['id']
            self.log.info(f"Memory ID: {self.memory_id}")
            setup_env({
                    "key": "MEMORY_ID",
                    "value": self.memory_id
                })
            return self.memory_id
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException' and "already exists" in str(e):
                memories = self.memory_client.list_memories()
                self.memory_id = next((m['id'] for m in memories if m['id'].startswith(self.memory_name)), None)
                self.log.info(f"Memory already exists. Using existing memory ID: {self.memory_id}")
                setup_env({
                    "key": "MEMORY_ID",
                    "value": self.memory_id
                })
                return self.memory_id
        except Exception as e:
            self.log.error("Failed to create memory")
            import traceback
            traceback.print_exc()

            if self.memory_id:
                try:
                    self.memory_client.delete_memory_and_wait(memory_id=self.memory_id)
                    self.log.info(f"Cleaned up memory: {self.memory_id}")
                except Exception as cleanup_error:
                    self.log.info(f"Failed to clean up memory: {cleanup_error}")

            return None
        

class MCPServerManager:
    def __init__(self, region: str = None):
        self.log = logger
        self.boto_session = Session()
        self.region = region or self.boto_session.region_name
        self.log.info(f"Region: {self.region}")
        self.ssm_client = boto3.client("ssm", region_name=self.region)
        self.secrets_client = boto3.client("secretsmanager", region_name=self.region)
        self.agentcore_runtime = Runtime()

    def store_cognito_config(self, cognito_config: Dict, secret_name: str = 'mcp_server/cognito/credentials') -> bool:
        """
        Stores or updates Cognito configuration in AWS Secrets Manager.
        
        Args:
            cognito_config (Dict): Cognito configuration dictionary
            secret_name (str): Name of the secret in Secrets Manager
        """
        try:
            self.secrets_client.create_secret(
                Name=secret_name,
                Description='Cognito credentials for MCP server',
                SecretString=json.dumps(cognito_config)
            )
            self.log.info("Cognito credentials stored in Secrets Manager")
        except self.secrets_client.exceptions.ResourceExistsException:
            self.secrets_client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(cognito_config)
            )
            self.log.info("Cognito credentials updated in Secrets Manager")
        return True

    def store_parameter(self, value: str, parameter_name: str) -> bool:
        """
        Stores a parameter in AWS Systems Manager Parameter Store.
        
        Args:
            value (str): The value to be stored
            parameter_name (str): The name of the parameter
        """
        self.ssm_client.put_parameter(
            Name=parameter_name,
            Value=value,
            Type='String',
            Description='MCP server',
            Overwrite=True
        )
        self.log.info("Parameter stored in Parameter Store")
        return True

    def setup_mcp_server(
        self, 
        tool_name: str, 
        files: List[str], 
        cognito_config: Dict,
        execution_role: str,
        auto_create_ecr: bool = True
    ) -> str:
        """
        Sets up and launches an MCP server using AgentCore Runtime.
        
        Args:
            tool_name (str): The name of the agent/tool to be deployed
            files (List[str]): List of required file paths
            cognito_config (Dict): Cognito configuration
            execution_role (str): IAM execution role ARN
            auto_create_ecr (bool): Whether to auto-create ECR repository
        """
        
        # Validate required files
        for file in files:
            if not os.path.exists(file):
                raise FileNotFoundError(f"Required file {file} not found.")
        self.log.info("All required files found.")
        
        # Prepare auth configuration
        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [cognito_config['client_id']],
                "discoveryUrl": cognito_config['discovery_url']
            }
        }

        # Configure runtime
        self.log.info("Configuring AgentCore Runtime...")
        response = self.agentcore_runtime.configure(
            entrypoint=f"mcp_servers/{tool_name}/{tool_name}.py",
            execution_role=execution_role,
            auto_create_ecr=auto_create_ecr,
            requirements_file="requirements.txt",
            region=self.region,
            authorizer_configuration=auth_config,
            protocol="MCP",
            agent_name=tool_name
        )

        # Launch server
        self.log.info("Launching MCP server...")
        launch_result = self.agentcore_runtime.launch(
            auto_update_on_conflict=True
        )
        
        # Monitor status
        self._wait_for_server_status()
        
        return launch_result

    def _wait_for_server_status(self):
        """
        Waits for MCP Server to reach a final status.
        """
        self.log.info("Waiting for MCP Server to be active...")
        end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        
        while True:
            status_response = self.agentcore_runtime.status()
            status = status_response.endpoint['status']
            
            if status in end_status:
                if status == 'READY':
                    self.log.info("MCP server is READY!")
                else:
                    self.log.error(f"MCP server status: {status}")
                break
                
            self.log.info(f"Status: {status} - waiting...")
            time.sleep(10)


if __name__ == "__main__":
    
    logger.info("Creating cognito user pool")
    # setup_cognito_user_pool(pool_name="WorkshopPool", client_name="WorkshopClient", username="testuser", temp_password="Password123!", permanent_password="P@ssword123!")
    logger.info("Deploying MCP servers")
    mcp_manager = MCPServerManager()

    # TODO: Get these values from Cloudformation
    cognito_config = {
        'pool_id': "us-west-2_EXAMPLE",
        'client_id': "EXAMPLECLIENTID123",
        'discovery_url': "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_EXAMPLE/.well-known/openid-configuration"
    }

    # mcp_manager.store_cognito_config(cognito_config)

    logger.info("Deploying clinicaltrials MCP server")
    clinicaltrials_launch_result = mcp_manager.setup_mcp_server(
        tool_name="clinicaltrials",
        files=["mcp_servers/clinicaltrials/clinicaltrials.py", "requirements.txt"],
        cognito_config=cognito_config,
        execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role"
    )

    logger.info("Deploying pubmed MCP server")
    # pubmed_launch_result = mcp_manager.setup_mcp_server(
    #     tool_name="pubmed",
    #     files=["mcp_servers/pubmed/pubmed.py", "mcp_servers/pubmed/xmltodict.py", "requirements.txt"],
    #     cognito_config=cognito_config,
    #     execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role"
    # )

    logger.info("Deploying healthlake MCP server")
    # healthlake_launch_result = mcp_manager.setup_mcp_server(
    #     tool_name="healthlake",
    #     files=["mcp_servers/healthlake/healthlake.py", "requirements.txt"],
    #     cognito_config=cognito_config,
    #     execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role"
    # )

    # mcp_manager.store_parameter(clinicaltrials_launch_result.agent_arn, "/mcp/clinicaltrials")
    # mcp_manager.store_parameter(pubmed_launch_result.agent_arn, "/mcp/pubmed")
    # mcp_manager.store_parameter(healthlake_launch_result.agent_arn, "/mcp/healthlake")
    # setup_env({
    #     "key": "CLINICAL_TRIALS_MCP_ARN",
    #     "value": clinicaltrials_launch_result.agent_arn
    # })
    # setup_env({
    #     "key": "PUBMED_MCP_ARN",
    #     "value": pubmed_launch_result.agent_arn
    # })
    # setup_env({
    #     "key": "HEALTHLAKE_MCP_ARN",
    #     "value": healthlake_launch_result.agent_arn
    # })

    logger.info("Creating memory...")
    # memory_manager = MemoryManager(memory_name="agentcore_workshop_memory")
    # memory_manager.create_shortterm_memory()

    logger.info("Deploying main agent...")
    # agentcore_runtime = Runtime()

    # response = agentcore_runtime.configure(
    #     entrypoint="main_agent.py",
    #     execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role",
    #     auto_create_ecr=True,
    #     requirements_file="requirements.txt",
    #     agent_name="multimodal_agent"
    # )


    # agent_launch_result = agentcore_runtime.launch(
    #     auto_update_on_conflict=True,
    #         env_vars={"OTEL_PYTHON_EXCLUDED_URLS": "/ping,/invocations"}
    # )
    
    # status_response = agentcore_runtime.status()
    # status = status_response.endpoint['status']
    # end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
    # while status not in end_status:
    #     time.sleep(10)
    #     status_response = agentcore_runtime.status()
    #     status = status_response.endpoint['status']
    #     print(status)
    
    # setup_env({
    #     "key": "AGENT_ARN",
    #     "value": agent_launch_result.agent_arn
    # })

    ### Deploying pubmed agent with A2A
    agentcore_runtime = Runtime()
    aws_pubmed_agent_name = "pubmed_agent_a2a"
    
    # Configure the deployment
    response_aws_docs_agent = agentcore_runtime.configure(
        entrypoint="agents/pubmed_agent_a2a.py",
        execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role",
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region="us-west-2",
        agent_name=aws_pubmed_agent_name,
        authorizer_configuration={
            "customJWTAuthorizer": {
                "allowedClients": [cognito_config.get("client_id")],
                "discoveryUrl": cognito_config.get("discovery_url"),
            }
        },
        protocol="A2A",
    )
    
    print("Configuration completed:", response_aws_docs_agent)
    
    launch_result_pubmed_a2_ = agentcore_runtime.launch(
        auto_update_on_conflict=True,
        env_vars={"OTEL_PYTHON_EXCLUDED_URLS": "/ping,/invocations"}
    )

    logger.info("Deploying main agent...")
    main_agent_runtime = Runtime()
    
    response = main_agent_runtime.configure(
        entrypoint="main_agent.py",
        execution_role="arn:aws:iam::123456789012:role/agentcore-workshop-role",
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        agent_name="main_agent",
        authorizer_configuration={
            "customJWTAuthorizer": {
                "allowedClients": [cognito_config.get("client_id")],
                "discoveryUrl": cognito_config.get("discovery_url"),
            }
        }
    )

    agent_launch_result = main_agent_runtime.launch(
        auto_update_on_conflict=True,
        env_vars={"OTEL_PYTHON_EXCLUDED_URLS": "/ping,/invocations"}
    )