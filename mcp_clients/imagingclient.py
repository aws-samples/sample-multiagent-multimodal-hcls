from mcp.client import Client

def connect_to_health_imaging():
    try:
        # Create an MCP client instance
        client = Client("healthimaging")
        return client
    except Exception as e:
        print(f"Error connecting to HealthImaging MCP server: {e}")
        return None

def make_health_imaging_request(client, request_data):
    try:
        # Make a request to the server
        response = client.request(request_data)
        return response
    except Exception as e:
        print(f"Error making request to HealthImaging: {e}")
        return None

def main():
    # Connect to the server
    client = connect_to_health_imaging()
    if not client:
        return

    # Example request data - modify according to your specific needs
    request_data = {
        "method": "list_datastores",
        "params": {
            "study_id": "example_study",
            "series_id": "example_series"
        }
    }

    # Make the request
    response = make_health_imaging_request(client, request_data)
    
    if response:
        print("Response received:", response)
    else:
        print("Failed to get response from server")

if __name__ == "__main__":
    main()