# server.py
import os
import sys
from loguru import logger
from mcp.server.fastmcp import FastMCP

# Validate environment variables on startup
logger.info(f"Env OKTA_API_BASE_URL: {os.environ.get('OKTA_API_BASE_URL')}")
logger.info(f"Env OKTA_API_TOKEN is set: {'OKTA_API_TOKEN' in os.environ}")

LOG_FILE = os.environ.get("OKTA_LOG_FILE")

# Simple MCP server without authentication lifecycle
mcp = FastMCP("Okta IDaaS MCP Server")

async def main():
    """Run the Okta MCP server."""
    logger.remove()

    if LOG_FILE:
        logger.add(
            LOG_FILE,
            mode="w",
            level=os.environ.get("OKTA_LOG_LEVEL", "INFO"),
            retention="5 days",
            enqueue=True,
            serialize=True,
        )

    logger.add(
        sys.stderr, 
        level=os.environ.get("OKTA_LOG_LEVEL", "INFO"), 
        format="{time} {level} {message}", 
        serialize=True
    )

    logger.info("Starting Okta MCP Server")
    
    # Validate required environment variables
    if not os.environ.get("OKTA_API_TOKEN"):
        logger.error("OKTA_API_TOKEN is required")
        sys.exit(1)
    
    if not os.environ.get("OKTA_API_BASE_URL"):
        logger.error("OKTA_API_BASE_URL is required")
        sys.exit(1)
    
    # Import tools (they will be registered automatically)
    from okta_mcp_server.tools.applications import applications  # noqa: F401
    from okta_mcp_server.tools.groups import groups  # noqa: F401
    from okta_mcp_server.tools.policies import policies  # noqa: F401
    from okta_mcp_server.tools.system_logs import system_logs  # noqa: F401
    from okta_mcp_server.tools.users import users  # noqa: F401

    logger.info("Okta MCP Server started successfully")
    await mcp.run_stdio_async()
