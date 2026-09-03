"""Model Context Protocol (MCP) Toolset integration for the HR Policy Agent.

Uses Google ADK's native `McpToolset` with `SseConnectionParams` / `StreamableHTTPConnectionParams`
to connect to the enterprise MCP server.
"""
import logging
from typing import Optional
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    SseConnectionParams,
    StreamableHTTPConnectionParams,
)

from .. import config

logger = logging.getLogger("mcp_tool")


def get_mcp_toolset(
    transport: str = "sse",
    url: Optional[str] = None,
    token: Optional[str] = None,
) -> McpToolset:
    """Create and return an ADK McpToolset instance configured for the remote MCP server.

    Args:
        transport: 'sse' (Server-Sent Events) or 'streamable_http'.
        url: MCP server base URL (defaults to config.MCP_SERVER_URL).
        token: MCP server auth token (defaults to config.MCP_SERVER_TOKEN).

    Returns:
        google.adk.tools.McpToolset
    """
    server_url = (url or config.MCP_SERVER_URL).rstrip("/")
    server_token = token or config.MCP_SERVER_TOKEN

    headers = {
        "Authorization": f"Bearer {server_token}",
        "X-MCP-Token": server_token,
        "mcp-token": server_token,
    }

    if transport == "streamable_http":
        connection_params = StreamableHTTPConnectionParams(
            url=f"{server_url}/mcp",
            headers=headers,
            timeout=10.0,
        )
    else:
        # Default: Server-Sent Events (SSE) transport
        connection_params = SseConnectionParams(
            url=f"{server_url}/sse",
            headers=headers,
            timeout=10.0,
        )

    return McpToolset(connection_params=connection_params)
