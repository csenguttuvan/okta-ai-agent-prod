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


# Import context variables and helpers from separate module
from okta_mcp_server.context import (
    caller_email_var,
    caller_groups_var,
    get_caller_email,
    get_caller_groups
)


# ✅ CRITICAL: Import mcp instance
from okta_mcp_server.mcp_instance import mcp


# ✅ CRITICAL: Initialize OAuth client BEFORE importing tools
logger.info("Step 2: Initializing OAuth client...")
from okta_mcp_server.oauth_jwt_client import init_okta_client
try:
    init_okta_client()
    logger.info("✅ OAuth client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize OAuth client: {e}")
    raise


# Import ALL tools at MODULE LEVEL - this registers them with mcp
logger.info("Step 3: Importing tools...")


# Always import read-only tools
logger.info("  Importing users (read-only)...")
from okta_mcp_server.tools.users import users
logger.info("  Importing groups (read-only)...")
from okta_mcp_server.tools.groups import groups
logger.info("  Importing applications (read-only)...")
from okta_mcp_server.tools.applications import applications
logger.info("  Importing policies (read-only)...")
from okta_mcp_server.tools.policies import policies
logger.info("  Importing system_logs...")
from okta_mcp_server.tools.system_logs import system_logs


# Check OAuth scopes to determine access level
okta_scopes = os.getenv("OKTA_SCOPES", "")
logger.info(f"  Detected scopes: {okta_scopes}")


has_manage_scope = (
    "okta.users.manage" in okta_scopes or 
    "okta.groups.manage" in okta_scopes or 
    "okta.apps.manage" in okta_scopes
)


if has_manage_scope:
    logger.info("  🔓 ADMIN MODE: Importing admin tools...")
    logger.info("  Importing users_admin...")
    from okta_mcp_server.tools.users import users_admin
    logger.info("  Importing groups_admin...")
    from okta_mcp_server.tools.groups import groups_admin
    logger.info("  Importing applications_admin...")
    from okta_mcp_server.tools.applications import applications_admin
    logger.info("  Importing policies_admin...")
    from okta_mcp_server.tools.policies import policies_admin
    logger.info(f"  ✅ Registered ~44 tools (ADMIN mode)")
else:
    logger.info("  🔒 READ-ONLY MODE: Skipping admin tools...")
    logger.info(f"  ✅ Registered ~20 tools (READ-ONLY mode)")


logger.info("Step 3 complete: Tools imported based on OAuth scopes")


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

        # Check if running in gateway mode
        if os.getenv("INTERNAL_AUTH_TOKEN"):
            logger.info("🔒 Running in GATEWAY MODE - auth required from gateway")
        else:
            logger.info("⚠️ Running in DIRECT MODE - no gateway auth required")

        # Create the SSE app
        import uvicorn

        # ✅ FIXED: Context middleware with proper header extraction
        class CallerContextMiddleware:
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    # Extract headers from scope - properly convert list of tuples to dict
                    headers_raw = scope.get("headers", [])
                    headers = {
                        key.decode('latin1').lower(): value.decode('latin1')
                        for key, value in headers_raw
                    }
                    
                    # Debug: Log what headers we received
                    logger.debug(f"🔍 Received headers: {list(headers.keys())}")
                    
                    # Get user email from possible header names
                    email = (
                        headers.get("x-user-email") or 
                        headers.get("x-forwarded-user") or
                        "unknown"
                    )
                    
                    # Get user groups
                    groups_str = headers.get("x-user-groups", "")
                    groups = [g.strip() for g in groups_str.split(",") if g.strip()]

                    logger.info(f"📥 Incoming request: email={email}, groups={groups}")

                    # ✅ Set context variables with tokens
                    token_email = caller_email_var.set(email)
                    token_groups = caller_groups_var.set(groups)

                    try:
                        # ✅ FIXED: Complete async call
                        await self.app(scope, receive, send)
                    finally:
                        # ✅ Reset context after request completes
                        caller_email_var.reset(token_email)
                        caller_groups_var.reset(token_groups)
                else:
                    # Non-HTTP requests (websocket, lifespan)
                    await self.app(scope, receive, send)

        # Wrap the SSE app with our middleware
        starlette_app = mcp.sse_app()
        app_with_middleware = CallerContextMiddleware(starlette_app)

        config = uvicorn.Config(
            app_with_middleware,
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
