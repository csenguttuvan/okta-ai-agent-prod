import os
from pathlib import Path


# Load .env file automatically
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✅ Loaded .env from {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed")

import sys
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level=os.getenv("OKTA_LOG_LEVEL", "DEBUG")  # Changed to DEBUG
)

# Import the shared mcp instance
logger.info("Step 1: Importing mcp_instance...")
from okta_mcp_server.mcp_instance import mcp
logger.info(f"Step 1 complete: mcp = {mcp}")

# Initialize OAuth client at MODULE LEVEL (before tool imports)
logger.info("Step 2: Initializing OAuth client...")
from okta_mcp_server.oauth_jwt_client import init_okta_client
init_okta_client()
logger.info("Step 2 complete: OAuth initialized")

# Import ALL tools at MODULE LEVEL - this registers them with mcp
logger.info("Step 3: Importing tools...")
logger.info("  Importing users...")
from okta_mcp_server.tools import users
logger.info("  Importing groups...")
from okta_mcp_server.tools import groups
logger.info("  Importing applications...")
from okta_mcp_server.tools import applications
logger.info("  Importing system_logs...")
from okta_mcp_server.tools import system_logs
logger.info("  Importing admin user privileges..")
from okta_mcp_server.tools.users import users_admin
logger.info("Step 3 complete: All tools imported")



async def main():
    """Run the Okta MCP server with OAuth authentication."""
    logger.info("Starting Okta MCP Server with OAuth 2.0")
    logger.info("✅ OAuth client initialized successfully")
    
    # Log registered tools
    tools = await mcp.list_tools()
    logger.info(f"✅ Registered {len(tools)} MCP tools:")
    for tool in tools:
        logger.info(f"  - {tool.name}")
    
    if len(tools) == 0:
        logger.error("❌ No tools registered!")
        logger.error(f"Debug: mcp object = {mcp}")
        logger.error(f"Debug: users module = {users}")
        logger.error(f"Debug: dir(users) = {[x for x in dir(users) if not x.startswith('_')]}")
        raise RuntimeError("No MCP tools available")
    
    logger.info("MCP Server ready - OAuth mode enabled")
    await mcp.run_stdio_async()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
