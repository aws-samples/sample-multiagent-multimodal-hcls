from mcp import stdio_client, StdioServerParameters
from strands import Agent, tool
from strands.tools.mcp import MCPClient

s3_table_mcp_client = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="npx",
        args=["-y", "@aws/s3-tables-mcp-server"]
    )
))


@tool
def genomics_agent(query: str) -> str:
    """Query S3 Table for variant and annotation data"""
    with s3_table_mcp_client:
        tools = s3_table_mcp_client.list_tools_sync()
        agent = Agent(tools=tools)
        response = agent(query)
        return response

if __name__ == "__main__":
    result = genomics_agent("List all S3 table buckets")
    print(result)