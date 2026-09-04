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


def _build_mcp_headers(token: Optional[str]) -> dict[str, str]:
    """Construct HTTP headers for MCP endpoint requests, warning if token is absent."""
    if not token:
        logger.warning(
            "MCP authentication token is not configured. Enterprise SaaS MCP calls may fail authentication."
        )
        return {}
    return {"X-MCP-Token": token}


def get_workweek_mcp_toolset(
    url: Optional[str] = None,
    token: Optional[str] = None,
) -> McpToolset:
    """Return McpToolset for the WorkWeek employee & leave management server."""
    endpoint = url or config.MCP_WORKWEEK_URL
    auth_token = token or config.MCP_SERVER_TOKEN
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=endpoint,
            headers=_build_mcp_headers(auth_token),
            timeout=15.0,
        )
    )


def get_serviceimmediately_mcp_toolset(
    url: Optional[str] = None,
    token: Optional[str] = None,
) -> McpToolset:
    """Return McpToolset for the ServiceImmediately ITMS/HRSD ticket tracking server."""
    endpoint = url or config.MCP_SERVICEIMMEDIATELY_URL
    auth_token = token or config.MCP_SERVER_TOKEN
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=endpoint,
            headers=_build_mcp_headers(auth_token),
            timeout=15.0,
        )
    )


def get_mcp_toolsets(
    token: Optional[str] = None,
) -> list[McpToolset]:
    """Return both enterprise MCP toolsets (WorkWeek and ServiceImmediately)."""
    return [
        get_workweek_mcp_toolset(token=token),
        get_serviceimmediately_mcp_toolset(token=token),
    ]


def get_mcp_toolset(
    transport: str = "streamable_http",
    url: Optional[str] = None,
    token: Optional[str] = None,
) -> McpToolset:
    """Backwards-compatible helper returning the WorkWeek toolset or specified endpoint."""
    target_url = url or config.MCP_WORKWEEK_URL
    auth_token = token or config.MCP_SERVER_TOKEN
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=target_url,
            headers=_build_mcp_headers(auth_token),
            timeout=15.0,
        )
    )

