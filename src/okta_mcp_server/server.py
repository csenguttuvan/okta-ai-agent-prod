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
    print("⚠️ python-dotenv not installed")

import sys
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
    level=os.getenv("OKTA_LOG_LEVEL", "INFO")
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

def main():
    """Run the Okta MCP server with OAuth authentication."""
    logger.info("Starting Okta MCP Server with OAuth 2.0")
    logger.info("✅ OAuth client initialized successfully")
    logger.info("✅ All MCP tools registered at import time")
    
    # Determine transport mode from environment
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    
    if transport in ("http", "sse"):
        # Get host and port from environment
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8000"))
        
        logger.info("MCP Server ready - OAuth mode enabled")
        logger.info(f"Running in HTTP/SSE transport mode on {host}:{port}")
        
        # Create the SSE app and run with uvicorn directly
        import uvicorn
        starlette_app = mcp.sse_app()  # Get the internal Starlette app
        
        config = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        import asyncio
        asyncio.run(server.serve())
    else:
        logger.info("MCP Server ready - OAuth mode enabled")
        logger.info("Running in stdio transport mode")
        mcp.run(transport="stdio")




if __name__ == "__main__":
    main()
