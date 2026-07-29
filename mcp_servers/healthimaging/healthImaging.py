import asyncio
import json
from typing import Any, Dict, List, Optional
import boto3
from datetime import datetime
from pydantic import BaseModel

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from mcp.types import TextContent

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

session = boto3.Session()
region = session.region_name or 'us-east-1'
client = boto3.client('medical-imaging', region_name=region)

def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

@mcp.tool()
def list_datastores(datastore_name: Optional[str] = None, max_results: Optional[int] = None) -> List[TextContent]:
    """
    List all AWS HealthImaging datastores in the current region.
    
    This function retrieves information about AWS HealthImaging datastores that store
    DICOM medical imaging data. It can list all datastores or filter by name.
    
    Args:
        datastore_name (str, optional): The name of a specific datastore to filter by.
                                       If provided, only datastores matching this name will be returned.
                                       If None, all datastores in the account will be listed.
        max_results (int, optional): Maximum number of datastores to return.
                                    If not specified, returns all available datastores.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          from the AWS HealthImaging API. The response includes datastore metadata
                          such as datastore ID, name, status, ARN, and creation timestamps.
    
    Raises:
        ClientError: If there's an error communicating with the AWS HealthImaging service,
                    such as insufficient permissions or invalid parameters.
        
    Example:
        # List all datastores
        all_datastores = list_datastores()
        
        # List datastores with specific name
        filtered_datastores = list_datastores(datastore_name="my-imaging-datastore")
        
        # Limit results
        limited_datastores = list_datastores(max_results=5)
    """
    kwargs = {}
    if max_results:
        kwargs["maxResults"] = max_results
    
    response = client.list_datastores(**kwargs)
    datastores = response.get("datastoreSummaries", [])
    
    # Filter by name if specified
    if datastore_name:
        datastores = [ds for ds in datastores if ds.get("datastoreName") == datastore_name]
    
    return [TextContent(type="text", text=json.dumps(datastores, indent=2, default=json_serializer))]

@mcp.tool()
def describe_datastore(datastore_id: str) -> List[TextContent]:
    """
    Retrieve detailed information about a specific HealthImaging datastore.
    
    This function fetches comprehensive metadata and configuration details for a specific
    AWS HealthImaging datastore using its unique identifier.
    
    Args:
        datastore_id (str): The unique identifier of the HealthImaging datastore to describe.
                           This is typically a UUID-like string assigned by AWS when
                           the datastore was created.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          containing detailed datastore information including:
                          - Datastore properties (name, status, ARN)
                          - Creation and modification timestamps
                          - Datastore configuration details
    
    Raises:
        ClientError: If the datastore ID is invalid, doesn't exist, or if there are
                    insufficient permissions to access the datastore information.
        
    Example:
        datastore_info = describe_datastore("ff065a6b17494ed3b3f33da4dfc60a7a")
    """
    response = client.get_datastore(datastoreId=datastore_id)
    return [TextContent(type="text", text=json.dumps(response.get("datastoreProperties", {}), indent=2, default=json_serializer))]

@mcp.tool()
def search_image_sets(args: Dict[str, Any]) -> List[TextContent]:
    """
    Search for DICOM image sets in a HealthImaging datastore using search criteria.
    
    This function performs searches against a HealthImaging datastore to find DICOM
    image sets that match specified criteria such as patient ID, study date, or modality.
    
    Args:
        args (Dict[str, Any]): A dictionary containing search configuration:
            - datastore_id (str): Required. The unique identifier of the datastore to search within.
            - search_criteria (Dict, optional): DICOM search parameters including:
                - filters: List of filter objects with values and operators
                - sort: Sorting configuration for results
            - max_results (int, optional): Maximum number of results to return (default: 50)
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          containing the search results with DICOM image set metadata including:
                          - Image set IDs and versions
                          - DICOM tags (patient info, study details, series data)
                          - Creation and update timestamps
    
    Raises:
        ClientError: If there's an error with the datastore access, invalid search criteria,
                    or insufficient permissions.
        
    Example:
        args = {
            "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
            "search_criteria": {
                "filters": [{
                    "values": [{"DICOMPatientId": "SUBJECT00901"}],
                    "operator": "EQUAL"
                }]
            },
            "max_results": 10
        }
        image_sets = search_image_sets(args)
    """
    kwargs = {"datastoreId": args["datastore_id"]}
    
    if "search_criteria" in args:
        kwargs["searchCriteria"] = args["search_criteria"]
    
    if "max_results" in args:
        kwargs["maxResults"] = args["max_results"]
    else:
        kwargs["maxResults"] = 50
    
    response = client.search_image_sets(**kwargs)
    return [TextContent(type="text", text=json.dumps(response.get("imageSetsMetadataSummaries", []), indent=2, default=json_serializer))]

@mcp.tool()
def get_image_set(args: Dict[str, Any]) -> List[TextContent]:
    """
    Retrieve comprehensive details of a specific DICOM image set.
    
    This function fetches detailed information about a specific DICOM image set
    including version information, creation date, and update history.
    
    Args:
        args (Dict[str, Any]): A dictionary containing image set identification:
            - datastore_id (str): Required. The unique identifier of the datastore.
            - image_set_id (str): Required. The unique identifier of the image set.
            - version_id (str, optional): Specific version of the image set to retrieve.
                                        If not provided, returns the latest version.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          containing detailed image set properties including:
                          - Image set metadata and version information
                          - Creation and modification timestamps
                          - DICOM study and series information
    
    Raises:
        ClientError: If the datastore ID or image set ID is invalid, doesn't exist,
                    or if there are insufficient permissions.
        
    Example:
        args = {
            "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
            "image_set_id": "3660db84e44321533b5f61590f06b18e"
        }
        image_set_details = get_image_set(args)
    """
    kwargs = {
        "datastoreId": args["datastore_id"],
        "imageSetId": args["image_set_id"]
    }
    
    if "version_id" in args:
        kwargs["versionId"] = args["version_id"]
    
    response = client.get_image_set(**kwargs)
    return [TextContent(type="text", text=json.dumps(response.get("imageSetProperties", {}), indent=2, default=json_serializer))]

@mcp.tool()
def get_image_set_metadata(args: Dict[str, Any]) -> List[TextContent]:
    """
    Extract comprehensive DICOM metadata from an image set.
    
    This function retrieves detailed DICOM metadata including patient information,
    study details, series data, and imaging parameters for a specific image set.
    
    Args:
        args (Dict[str, Any]): A dictionary containing metadata request parameters:
            - datastore_id (str): Required. The unique identifier of the datastore.
            - image_set_id (str): Required. The unique identifier of the image set.
            - version_id (str, optional): Specific version of the image set metadata.
                                        If not provided, returns metadata for the latest version.
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with the JSON response
                          containing comprehensive DICOM metadata including:
                          - Patient demographics and identifiers
                          - Study information (dates, descriptions, UIDs)
                          - Series details (modality, acquisition parameters)
                          - Instance-level metadata
    
    Raises:
        ClientError: If the datastore ID or image set ID is invalid, doesn't exist,
                    or if there are insufficient permissions to access the metadata.
        
    Example:
        args = {
            "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
            "image_set_id": "3660db84e44321533b5f61590f06b18e"
        }
        dicom_metadata = get_image_set_metadata(args)
    """
    kwargs = {
        "datastoreId": args["datastore_id"],
        "imageSetId": args["image_set_id"]
    }
    
    if "version_id" in args:
        kwargs["versionId"] = args["version_id"]
    
    response = client.get_image_set_metadata(**kwargs)
    return [TextContent(type="text", text=json.dumps(response.get("imageSetMetadataBlob", {}), indent=2, default=json_serializer))]

@mcp.tool()
def get_image_frame(args: Dict[str, Any]) -> List[TextContent]:
    """
    Retrieve pixel data for a specific DICOM image frame.
    
    This function fetches the actual pixel data for a specific frame within a DICOM image set.
    The response contains the binary image data that can be processed or displayed.
    
    Args:
        args (Dict[str, Any]): A dictionary containing frame request parameters:
            - datastore_id (str): Required. The unique identifier of the datastore.
            - image_set_id (str): Required. The unique identifier of the image set.
            - image_frame_information (Dict): Required. Frame identification including:
                - imageFrameId (str): The unique identifier of the specific frame
    
    Returns:
        List[TextContent]: A list containing a single TextContent object with information
                          about the retrieved image frame, including content type and size.
                          Note: The actual binary pixel data is available in the response
                          but not included in the text representation for readability.
    
    Raises:
        ClientError: If the datastore ID, image set ID, or frame ID is invalid,
                    doesn't exist, or if there are insufficient permissions.
        
    Example:
        args = {
            "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
            "image_set_id": "3660db84e44321533b5f61590f06b18e",
            "image_frame_information": {
                "imageFrameId": "1.2.840.99999999.frame.1"
            }
        }
        frame_data = get_image_frame(args)
    """
    response = client.get_image_frame(
        datastoreId=args["datastore_id"],
        imageSetId=args["image_set_id"],
        imageFrameInformation=args["image_frame_information"]
    )
    
    # Return metadata about the frame instead of binary data
    frame_info = {
        "contentType": response.get("contentType"),
        "imageFrameBlob": f"<Binary data - {len(response.get('imageFrameBlob', b''))} bytes>"
    }
    
    return [TextContent(type="text", text=json.dumps(frame_info, indent=2))]

if __name__ == "__main__":
    mcp.run(transport="streamable-http")