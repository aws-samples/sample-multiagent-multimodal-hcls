from bedrock_agentcore.tools.browser_client import browser_session
from nova_act import NovaAct
from rich.console import Console
import os
import argparse
import json
from strands import Agent, tool

console = Console()

from boto3.session import Session

boto_session = Session()
region = boto_session.region_name
nova_act_key = os.environ.get("NOVA_ACT_API_KEY", "")

@tool
def browser_with_nova_act(prompt, starting_url: str):
    """
    Automates browser tasks starting from a given URL based on natural language instructions.
    Supports parallel execution and can handle moderately complex tasks with some reasoning.

    Args:
        starting_url (str): The initial URL to open in the browser.
        instr (str): A natural language instruction describing the task to be automated.

    Returns:
        str: The result of the action performed in the browser.
    """
    result = None
    with browser_session(region) as client:
        ws_url, headers = client.generate_ws_headers()
        try:
            with NovaAct(
                cdp_endpoint_url=ws_url,
                cdp_headers=headers,
                preview={"playwright_actuation": True},
                nova_act_api_key=nova_act_key,
                starting_page=starting_url,
            ) as nova_act:
                result = nova_act.act(prompt)
        except Exception as e:
            console.print(f"NovaAct error: {e}")
        finally:
            return result


if __name__ == "__main__":

    supervisor_agent = Agent(tools=[browser_with_nova_act])

    message = """
    I have the following tasks. Feel free to run them in parallel if it improves performance. 

    Get details of insulin receptor from proteinatlas.org    
    """
    supervisor_agent(message)




# import random
# from strands import Agent, tool
# from bedrock_agentcore.tools.browser_client import browser_session
# from nova_act import NovaAct
# from browser_viewer import BrowserViewerServer

# Constants
# NOVA_ACT_API_KEY = "YOUR_NOVA_ACT_API_KEY"

# @tool
# def browser_automation_tool(instr: str) -> str:
#     """
#     Automates browser tasks starting from a given URL based on natural language instructions.
#     Supports parallel execution and can handle moderately complex tasks with some reasoning.

#     Args:
#         starting_url (str): The initial URL to open in the browser.
#         instr (str): A natural language instruction describing the task to be automated.

#     Returns:
#         str: The result of the action performed in the browser.
#     """
#     with browser_session('us-west-2') as client:

#         # Retrieve CDP WebSocket URL and headers for control
#         ws_url, headers = client.generate_ws_headers()

#         # Use a random port to avoid conflicts
#         port = random.randint(8000, 9000)

#         # Start the browser viewer server (optional GUI)
#         viewer = BrowserViewerServer(client, port=port)
#         viewer_url = viewer.start(open_browser=True)
#         print(f"Viewer started at: {viewer_url}")

#         try:
#             with NovaAct(
#                 cdp_endpoint_url=ws_url,
#                 cdp_headers=headers,
#                 preview={"playwright_actuation": True},
#                 nova_act_api_key="YOUR_NOVA_ACT_API_KEY",
#                 # starting_page=starting_url,
#             ) as nova_act:
#                 result = nova_act.act(instr)
#                 return result

#         except Exception as e:
#             print(f"[ERROR] Failed to perform browser automation: {e}")
#             raise



