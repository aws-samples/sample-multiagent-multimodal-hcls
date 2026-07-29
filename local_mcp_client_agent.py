import strands
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

def main():
    print("\nConnecting to MCP Server...")

    server = MCPClient(lambda: streamablehttp_client("http://localhost:8000/mcp"))
    
    with server:
        agent = Agent(
            system_prompt="""You will perform task and retrieve data"""
        )

        mcp_tools = server.list_tools_sync()
        print(f"Available tools: {[tool.tool_name for tool in mcp_tools]}")
        
        agent.tool_registry.process_tools(mcp_tools)
        
        while True:
            user_input = input("\nYour request: ")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                break
            
            print("\n🤔 Processing...\n")
            agent(user_input)
                    

if __name__ == "__main__":
    main()
