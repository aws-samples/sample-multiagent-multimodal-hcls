import asyncio
import json
from typing import Any, Dict, List, Optional
import boto3
import requests
from pydantic import BaseModel

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from mcp.types import TextContent

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

session = boto3.Session()
region = session.region_name
client = boto3.client("healthlake", region_name=region)

@mcp.tool()
def list_datastores(datastore_name: str=None) -> List[TextContent]:
    """
    List all FHIR datastores in the current AWS account and region.
    
    This function retrieves information about AWS HealthLake FHIR datastores.
    It can either list all datastores or filter by a specific datastore name.
    
    Args:
        datastore_name (str, optional): The name of a specific datastore to filter by.
                                       If provided, only datastores matching this name will be returned.
                                       If None, all datastores in the account will be listed.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          from the AWS HealthLake API. The response includes datastore metadata
                          such as datastore ID, name, status, creation time, and endpoint information.
    
    Raises:
        ClientError: If there's an error communicating with the AWS HealthLake service,
                    such as insufficient permissions or invalid parameters.
        
    Example:
        # List all datastores
        all_datastores = list_datastores()
        
        # List datastores with specific name
        filtered_datastores = list_datastores(datastore_name="my-fhir-datastore")
    """
    if datastore_name:
        response = client.list_fhir_datastores(
        Filter={
            'DatastoreName': datastore_name,
        })
        return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]
    response = client.list_fhir_datastores()
    return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]

@mcp.tool()
def describe_datastore(datastore_id: str) -> List[TextContent]:
    """
    Retrieve detailed information about a specific FHIR datastore.
    
    This function fetches comprehensive metadata and configuration details for a specific
    AWS HealthLake FHIR datastore using its unique identifier.
    
    Args:
        datastore_id (str): The unique identifier of the FHIR datastore to describe.
                           This is typically a UUID-like string assigned by AWS when
                           the datastore was created.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          containing detailed datastore information including:
                          - Datastore properties (name, status, type version)
                          - Endpoint URL for FHIR API access
                          - Creation and modification timestamps
                          - Preload data configuration (if applicable)
                          - SSE (Server-Side Encryption) configuration
                          - Identity provider configuration
    
    Raises:
        ClientError: If the datastore ID is invalid, doesn't exist, or if there are
                    insufficient permissions to access the datastore information.
        
    Example:
        args = {
            "datastore_id": "12345678-1234-1234-1234-123456789012",
        }
        new_datastore = describe_datastore(args)
    """
    response = client.describe_fhir_datastore(DatastoreId=datastore_id)
    return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]

@mcp.tool()
def create_datastore(args: Dict[str, Any]) -> List[TextContent]:
    """
    Create a new FHIR datastore in AWS HealthLake.
    
    This function creates a new FHIR datastore with the specified configuration.
    The datastore will be used to store and manage FHIR resources according to
    the specified FHIR version standard.
    
    Args:
        args (Dict[str, Any]): A dictionary containing datastore configuration parameters:
            - datastore_name (str): Required. The name for the new datastore.
                                   Must be unique within the AWS account and region.
            - datastore_type_version (str, optional): The FHIR version to use.
                                                     Defaults to "R4" if not specified.
                                                     Supported versions: "R4", "STU3".
            - preload_data_config (Dict, optional): Configuration for preloading
                                                   synthetic data into the datastore.
                                                   Useful for testing and development.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          from the datastore creation operation, including:
                          - Datastore ID (unique identifier for the new datastore)
                          - Datastore ARN (Amazon Resource Name)
                          - Datastore status (typically "CREATING")
                          - Datastore endpoint URL (once creation is complete)
    
    Raises:
        ClientError: If there's an error creating the datastore, such as:
                    - Invalid datastore name or parameters
                    - Insufficient permissions
                    - Account limits exceeded
                    - Invalid preload data configuration
        
    Example:
        args = {
            "datastore_name": "my-fhir-datastore",
            "datastore_type_version": "R4",
            "preload_data_config": {
                "PreloadDataType": "SYNTHEA"
            }
        }
        new_datastore = create_datastore(args)
    """
    params = {
        "DatastoreName": args["datastore_name"],
        "DatastoreTypeVersion": args.get("datastore_type_version", "R4")
    }
    
    if "preload_data_config" in args:
        params["PreloadDataConfig"] = args["preload_data_config"]
    
    response = client.create_fhir_datastore(**params)
    return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]

@mcp.tool()
def start_fhir_import_job(args: Dict[str, Any]) -> List[TextContent]:
    """
    Start a FHIR data import job to load data into a HealthLake datastore.
    
    This function initiates an asynchronous import job that loads FHIR resources
    from an S3 bucket into the specified HealthLake datastore. The import job
    processes FHIR resources in NDJSON format and validates them against the
    FHIR specification before storing them.
    
    Args:
        args (Dict[str, Any]): A dictionary containing import job configuration:
            - datastore_id (str): Required. The unique identifier of the target datastore
                                 where the FHIR data will be imported.
            - input_data_config (Dict): Required. Configuration specifying the source data:
                - S3Uri (str): S3 URI pointing to the FHIR data files (NDJSON format)
                - Additional S3 configuration parameters as needed
            - data_access_role_arn (str): Required. ARN of the IAM role that HealthLake
                                        will assume to access the S3 bucket containing
                                        the source data. The role must have appropriate
                                        S3 read permissions.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          from the import job initiation, including:
                          - Job ID (unique identifier for tracking the import job)
                          - Job status (typically "SUBMITTED" initially)
                          - Datastore ID
                          - Job submission timestamp
    
    Raises:
        ClientError: If there's an error starting the import job, such as:
                    - Invalid datastore ID or datastore not in ACTIVE state
                    - Invalid S3 URI or inaccessible S3 bucket
                    - Invalid or insufficient IAM role permissions
                    - Malformed input data configuration
        
    Example:
        args = {
            "datastore_id": "12345678-1234-1234-1234-123456789012",
            "input_data_config": {
                "S3Uri": "s3://my-bucket/fhir-data/"
            },
            "data_access_role_arn": "arn:aws:iam::123456789012:role/HealthLakeImportRole"
        }
        import_job = start_fhir_import_job(args)
    """
    params = {
        "DatastoreId": args["datastore_id"],
        "InputDataConfig": args["input_data_config"],
        "DataAccessRoleArn": args["data_access_role_arn"]
    }
    
    response = client.start_fhir_import_job(**params)
    return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]

@mcp.tool()
def describe_fhir_import_job(self, args: Dict[str, Any]) -> List[TextContent]:
    """
    Retrieve detailed information about a specific FHIR import job.
    
    This function fetches comprehensive status and metadata information about
    a previously started FHIR import job, including progress, error details,
    and completion statistics.
    
    Args:
        args (Dict[str, Any]): A dictionary containing job identification parameters:
            - datastore_id (str): Required. The unique identifier of the datastore
                                 where the import job is running.
            - job_id (str): Required. The unique identifier of the import job
                           returned when the job was started.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          containing detailed job information including:
                          - Job status (SUBMITTED, IN_PROGRESS, COMPLETED, FAILED, etc.)
                          - Job statistics (records processed, failed, succeeded)
                          - Start and end timestamps
                          - Input data configuration
                          - Error messages and details (if job failed)
                          - Data access role ARN used for the job
    
    Raises:
        ClientError: If there's an error retrieving job information, such as:
                    - Invalid datastore ID or job ID
                    - Job doesn't exist or has been deleted
                    - Insufficient permissions to access job details
        
    Example:
        args = {
            "datastore_id": "12345678-1234-1234-1234-123456789012",
            "job_id": "87654321-4321-4321-4321-210987654321"
        }
        job_status = describe_fhir_import_job(args)
    """
    response = client.describe_fhir_import_job(
        DatastoreId=args["datastore_id"],
        JobId=args["job_id"]
    )
    return [TextContent(type="text", text=json.dumps(response, indent=2, default=str))]

@mcp.tool()
def search_fhir_resources(self, args: Dict[str, Any]) -> List[TextContent]:
    """
    Search for FHIR resources in a HealthLake datastore using FHIR search parameters.
    
    This function performs FHIR-compliant searches against a HealthLake datastore,
    allowing you to query for specific resources using standard FHIR search parameters.
    The search follows FHIR R4 or STU3 specifications depending on the datastore version.
    
    Args:
        args (Dict[str, Any]): A dictionary containing search configuration:
            - datastore_id (str): Required. The unique identifier of the datastore
                                 to search within.
            - resource_type (str): Required. The FHIR resource type to search for
                                  (e.g., "Patient", "Observation", "Encounter").
            - search_params (Dict, optional): FHIR search parameters as key-value pairs.
                                            Common parameters include:
                                            - _count: Number of results to return (default: 10)
                                            - _sort: Sort order for results
                                            - Resource-specific search parameters
                                            - Date ranges, identifiers, etc.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          containing the FHIR Bundle with search results, including:
                          - Bundle metadata (total count, search parameters used)
                          - Entry array with matching FHIR resources
                          - Pagination links (if applicable)
                          - Search result metadata
    
    Raises:
        ClientError: If there's an error with the datastore access or invalid datastore ID.
        HTTPError: If the FHIR search request fails due to:
                  - Invalid search parameters
                  - Malformed resource type
                  - Authentication/authorization issues
                  - Datastore endpoint unavailable
        
    Example:
        args = {
            "datastore_id": "12345678-1234-1234-1234-123456789012",
            "resource_type": "Patient",
            "search_params": {
                "family": "Smith",
                "given": "John",
                "_count": "20",
                "_sort": "family"
            }
        }
        patients = search_fhir_resources(args)
    """
    # Get datastore endpoint
    datastore_response = client.describe_fhir_datastore(DatastoreId=args["datastore_id"])
    endpoint = datastore_response["DatastoreProperties"]["DatastoreEndpoint"]
    
    # Build search URL
    url = f"{endpoint}/{args['resource_type']}"
    
    # Add search parameters
    params = args.get("search_params", {})
    if not params.get("_count"):
        params["_count"] = "10"  # Default limit
    
    # Make FHIR search request
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    return [TextContent(type="text", text=json.dumps(response.json(), indent=2))]

@mcp.tool()
def join_fhir_resources(self, args: Dict[str, Any]) -> List[TextContent]:
    """
    Perform complex joins between FHIR resources across multiple resource types.
    
    This function searches for primary FHIR resources and then finds related resources
    that reference them, effectively performing a "join" operation across different
    FHIR resource types. This is useful for building comprehensive patient records
    or analyzing relationships between different clinical data points.
    
    Args:
        args (Dict[str, Any]): A dictionary containing join configuration:
            - datastore_id (str): Required. The unique identifier of the datastore
                                 to search within.
            - primary_resource (str): Required. The primary FHIR resource type to start with
                                    (e.g., "Patient", "Encounter").
            - primary_params (Dict, optional): Search parameters for the primary resource.
                                             If not provided, defaults to empty dict.
                                             Automatically sets _count to 10 if not specified.
            - related_resources (List[Dict]): Required. List of related resource configurations:
                - resource_type (str): The FHIR resource type to join with
                - reference_field (str): The search parameter that references the primary resource
                - search_params (Dict, optional): Additional search parameters for this resource type
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with joined results:
                          - total: Number of primary resources found
                          - results: Array of joined records, each containing:
                            - primary: The primary resource data
                            - related: Dictionary with related resources grouped by type
    
    Raises:
        ClientError: If there's an error with datastore access or invalid datastore ID.
        HTTPError: If any of the FHIR search requests fail due to:
                  - Invalid search parameters or resource types
                  - Authentication/authorization issues
                  - Datastore endpoint unavailable
        KeyError: If required configuration parameters are missing from the args dictionary.
        
    Example:
        args = {
            "datastore_id": "12345678-1234-1234-1234-123456789012",
            "primary_resource": "Patient",
            "primary_params": {
                "family": "Smith",
                "_count": "5"
            },
            "related_resources": [
                {
                    "resource_type": "Observation",
                    "reference_field": "subject",
                    "search_params": {
                        "category": "vital-signs",
                        "_count": "20"
                    }
                },
                {
                    "resource_type": "Encounter",
                    "reference_field": "subject",
                    "search_params": {
                        "status": "finished"
                    }
                }
            ]
        }
        joined_data = join_fhir_resources(args)
    """
    # Get datastore endpoint
    datastore_response = client.describe_fhir_datastore(DatastoreId=args["datastore_id"])
    endpoint = datastore_response["DatastoreProperties"]["DatastoreEndpoint"]
    
    # Search primary resources
    primary_url = f"{endpoint}/{args['primary_resource']}"
    primary_params = args.get("primary_params", {})
    if not primary_params.get("_count"):
        primary_params["_count"] = "10"
    
    primary_response = requests.get(primary_url, params=primary_params)
    primary_response.raise_for_status()
    primary_data = primary_response.json()
    
    # Join with related resources
    joined_results = []
    for entry in primary_data.get("entry", []):
        primary_resource = entry["resource"]
        result = {"primary": primary_resource, "related": {}}
        
        # For each related resource type
        for related in args["related_resources"]:
            resource_type = related["resource_type"]
            reference_field = related["reference_field"]
            
            # Build reference query
            related_params = related.get("search_params", {})
            related_params[reference_field] = f"{args['primary_resource']}/{primary_resource['id']}"
            related_params["_count"] = related_params.get("_count", "50")
            
            # Search related resources
            related_url = f"{endpoint}/{resource_type}"
            related_response = requests.get(related_url, params=related_params)
            
            if related_response.status_code == 200:
                related_data = related_response.json()
                result["related"][resource_type] = related_data.get("entry", [])
            else:
                result["related"][resource_type] = []
        
        joined_results.append(result)
    
    return [TextContent(type="text", text=json.dumps({
        "total": len(joined_results),
        "results": joined_results
    }, indent=2))]


if __name__=="__main__":
    mcp.run(transport="streamable-http")