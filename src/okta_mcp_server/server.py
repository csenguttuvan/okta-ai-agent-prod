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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

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

# Define auth validation middleware as a class
class AuthValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        """Validate requests from auth gateway and extract user identity"""
        # Allow health checks without auth
        if request.url.path in ["/health", "/healthz"]:
            return await call_next(request)
        
        # Verify internal auth token from gateway
        auth_token = request.headers.get("X-Internal-Auth")
        expected = os.getenv("INTERNAL_AUTH_TOKEN")
        
        # Only enforce if INTERNAL_AUTH_TOKEN is set (for gateway mode)
        if expected and auth_token != expected:
            logger.warning(f"Unauthorized request from {request.client.host}")
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid internal auth"}
            )
        
        # Extract user info and attach to request state
        request.state.user_email = request.headers.get("X-User-Email", "unknown")
        request.state.user_id = request.headers.get("X-User-ID", "unknown")
        request.state.user_groups = request.headers.get("X-User-Groups", "").split(",")
        request.state.access_level = request.headers.get("X-Access-Level", "unknown")
        
        if request.state.user_email != "unknown":
            logger.info(f"Request from authenticated user: {request.state.user_email} ({request.state.access_level})")
        
        return await call_next(request)

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
logger.info("  Importing policies...")
from okta_mcp_server.tools import policies
logger.info("  Importing admin user privileges...")
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
        
        # Check if running in gateway mode
        if os.getenv("INTERNAL_AUTH_TOKEN"):
            logger.info("🔒 Running in GATEWAY MODE - 
