"""MCP client verification script.

Tests connection and tool discovery on stateless Streamable HTTP MCP endpoints:
    venv/bin/python tests/mcp_client_check.py <mcp_url> <token>

If arguments are omitted, defaults to the configured WorkWeek endpoint and token.
"""
import asyncio
import os
import sys
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = os.getenv(
    "MCP_WORKWEEK_URL",
    "https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/",
)
DEFAULT_TOKEN = os.getenv(
    "MCP_SERVER_TOKEN",
    "mcp_w7e9kli_R2CJUChBjPBaNzHWhAKtbnLrRqx1JNlMo3Q",
)


async def check_mcp_server(mcp_url: str, token: str):
    print(f"Connecting to MCP endpoint: {mcp_url}")
    print(f"Using X-MCP-Token: {token[:8]}...{token[-4:]}")

    headers = {"X-MCP-Token": token}

    async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
        async with streamable_http_client(mcp_url, http_client=client) as (read, write, get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✓ MCP Session initialized successfully!")

                # List tools
                tools_response = await session.list_tools()
                print(f"\nDiscovered {len(tools_response.tools)} tool(s):")
                for tool in tools_response.tools:
                    print(f"  - {tool.name}: {tool.description or 'No description'}")

                # Smoke test
                tool_names = [t.name for t in tools_response.tools]
                if "get_current_employee_id" in tool_names:
                    res = await session.call_tool("get_current_employee_id", {})
                    emp_id = res.content[0].text if res.content else "Unknown"
                    print(f"\n✓ Verification: resolved current employee ID -> {emp_id}")
                elif "list_tickets" in tool_names:
                    res = await session.call_tool("list_tickets", {"employee_id": "EMP-687"})
                    print(f"\n✓ Verification: listed tickets successfully")


def main():
    mcp_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    token = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TOKEN
    asyncio.run(check_mcp_server(mcp_url, token))


if __name__ == "__main__":
    main()
