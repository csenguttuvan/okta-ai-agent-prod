"""Shared MCP instance for all tools to import."""
from mcp.server.fastmcp import FastMCP

# Create the global mcp instance
mcp = FastMCP("Okta MCP Server")