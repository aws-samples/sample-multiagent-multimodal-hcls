"""
MCP client for AgentCore Gateway.

Handles OAuth2 token retrieval and provides a configured
StreamableHTTP MCP client for the Gateway endpoint.
"""

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

# Token cache
_token_cache = {"token": None, "expires_at": 0}


def get_oauth_token() -> str:
    """Retrieve OAuth2 token for Gateway authentication with caching."""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]

    token_endpoint = os.environ.get("AGENTCORE_TOKEN_ENDPOINT", "")
    client_id = os.environ.get("AGENTCORE_CLIENT_ID", "")
    client_secret = os.environ.get("AGENTCORE_CLIENT_SECRET", "")
    scope = os.environ.get("AGENTCORE_SCOPE", "")

    if not all([token_endpoint, client_id, client_secret]):
        raise RuntimeError(
            "Missing OAuth2 config. Set AGENTCORE_TOKEN_ENDPOINT, "
            "AGENTCORE_CLIENT_ID, AGENTCORE_CLIENT_SECRET env vars."
        )

    resp = requests.post(
        token_endpoint,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    data = resp.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)

    logger.info("OAuth2 token refreshed")
    return _token_cache["token"]


def get_streamable_http_mcp_client():
    """Return an MCP client configured for the AgentCore Gateway.

    Uses the StreamableHTTP transport from the strands-agents MCP
    integration. The client connects to the Gateway URL and
    authenticates with an OAuth2 bearer token.
    """
    from strands.tools.mcp import MCPClient
    from strands.tools.mcp.mcp_client import StreamableHTTPTransport

    gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL", "")
    if not gateway_url:
        raise RuntimeError(
            "Missing AGENTCORE_GATEWAY_URL environment variable."
        )

    token = get_oauth_token()

    transport = StreamableHTTPTransport(
        url=gateway_url,
        headers={"Authorization": f"Bearer {token}"},
    )

    return MCPClient(transport)
