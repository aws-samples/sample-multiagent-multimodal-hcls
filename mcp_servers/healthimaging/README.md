# AWS HealthImaging MCP Server

A Model Context Protocol (MCP) server that provides access to AWS HealthImaging services for managing and querying DICOM medical imaging data.

## Overview

This MCP server enables interaction with AWS HealthImaging datastores, allowing you to:
- List and describe imaging datastores
- Search for DICOM image sets using various criteria
- Retrieve detailed image set metadata and properties
- Access individual DICOM image frames

## Features

### Core Operations
- **Datastore Management**: List and describe HealthImaging datastores
- **Image Set Search**: Find DICOM image sets using patient ID, study date, modality, and other DICOM tags
- **Metadata Retrieval**: Extract comprehensive DICOM metadata including patient demographics and study details
- **Frame Access**: Retrieve individual DICOM image frames with pixel data

### Search Capabilities
- Patient-based searches (ID, name, demographics)
- Study-level filtering (date ranges, descriptions, UIDs)
- Series-level queries (modality, acquisition parameters)
- Advanced DICOM tag filtering with multiple operators

## Installation

1. Install required dependencies:
```bash
pip install mcp boto3 pydantic starlette
```

2. Configure AWS credentials with HealthImaging permissions:
```bash
aws configure
```

Required IAM permissions:
- `medical-imaging:ListDatastores`
- `medical-imaging:GetDatastore`
- `medical-imaging:SearchImageSets`
- `medical-imaging:GetImageSet`
- `medical-imaging:GetImageSetMetadata`
- `medical-imaging:GetImageFrame`

## Usage

### Starting the Server

```bash
python healthimaging_standard.py
```

The server runs on `http://0.0.0.0:8000` by default.

### Available Tools

#### 1. list_datastores
List all HealthImaging datastores in your AWS account.

```python
# List all datastores
list_datastores()

# Filter by name
list_datastores(datastore_name="my-imaging-datastore")

# Limit results
list_datastores(max_results=5)
```

#### 2. describe_datastore
Get detailed information about a specific datastore.

```python
describe_datastore("ff065a6b17494ed3b3f33da4dfc60a7a")
```

#### 3. search_image_sets
Search for DICOM image sets using various criteria.

```python
# Basic search
args = {
    "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
    "max_results": 10
}
search_image_sets(args)

# Search by patient ID
args = {
    "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
    "search_criteria": {
        "filters": [{
            "values": [{"DICOMPatientId": "SUBJECT00901"}],
            "operator": "EQUAL"
        }]
    }
}
search_image_sets(args)

# Search by study date range
args = {
    "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
    "search_criteria": {
        "filters": [{
            "values": [
                {"DICOMStudyDate": "20080101"},
                {"DICOMStudyDate": "20081231"}
            ],
            "operator": "BETWEEN"
        }]
    }
}
search_image_sets(args)
```

#### 4. get_image_set
Retrieve detailed properties of a specific image set.

```python
args = {
    "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
    "image_set_id": "3660db84e44321533b5f61590f06b18e"
}
get_image_set(args)
```

#### 5. get_image_set_metadata
Extract comprehensive DICOM metadata from an image set.

```python
args = {
    "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
    "image_set_id": "3660db84e44321533b5f61590f06b18e"
}
get_image_set_metadata(args)
```

#### 6. get_image_frame
Retrieve pixel data for a specific DICOM image frame.

```python
args = {
    "datastore_id": "ff065a6b17494ed3b3f33da4dfc60a7a",
    "image_set_id": "3660db84e44321533b5f61590f06b18e",
    "image_frame_information": {
        "imageFrameId": "1.2.840.99999999.frame.1"
    }
}
get_image_frame(args)
```

## Search Operators

The `search_image_sets` function supports various operators for filtering:

- `EQUAL`: Exact match
- `NOT_EQUAL`: Not equal to
- `GREATER_THAN`: Greater than (for dates/numbers)
- `GREATER_THAN_OR_EQUAL`: Greater than or equal
- `LESS_THAN`: Less than
- `LESS_THAN_OR_EQUAL`: Less than or equal
- `BETWEEN`: Between two values (inclusive)

## Common DICOM Tags

Frequently used DICOM tags for searching:

- `DICOMPatientId`: Patient identifier
- `DICOMPatientName`: Patient name
- `DICOMPatientBirthDate`: Patient birth date (YYYYMMDD)
- `DICOMPatientSex`: Patient sex (M/F/O)
- `DICOMStudyDate`: Study date (YYYYMMDD)
- `DICOMStudyTime`: Study time (HHMMSS)
- `DICOMStudyInstanceUID`: Unique study identifier
- `DICOMSeriesModality`: Imaging modality (CT, MR, US, etc.)
- `DICOMAccessionNumber`: Accession number

## Error Handling

The server includes comprehensive error handling for:
- Invalid datastore or image set IDs
- Insufficient AWS permissions
- Malformed search criteria
- Network connectivity issues

All errors are returned as structured JSON responses with descriptive messages.

## Security

- Uses AWS IAM for authentication and authorization
- Supports AWS credential profiles and roles
- Follows AWS security best practices
- No sensitive data is logged or exposed

## Limitations

- Binary image frame data is not directly displayed in text responses
- Large metadata responses may be truncated for readability
- Search results are limited by AWS API pagination limits
- Requires appropriate AWS HealthImaging service availability in your region