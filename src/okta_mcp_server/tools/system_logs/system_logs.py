from typing import Optional
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client

def get_caller_email(ctx: Context | None) -> str:
    """Extract user email from context metadata"""
    if not ctx:
        return "unknown"

    if hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'meta'):
        meta = ctx.request_context.meta
        if isinstance(meta, dict):
            return meta.get('user_email', 'unknown')

    import os
    return os.getenv('USER_EMAIL', 'unknown')

@mcp.tool()
async def get_logs(
    ctx: Context | None = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    filter: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 100
) -> dict:
    """Retrieve system logs from Okta (requires logs.read scope)."""
    caller = get_caller_email(ctx)

    logger.info(f"[caller={caller}] Retrieving system logs since={since}, until={until}, limit={limit}")

    params = {"limit": limit}
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    if filter:
        params["filter"] = filter
    if query:
        params["q"] = query

    try:
        logs = await get_client().get("/api/v1/logs", params=params)
        logger.info(f"[caller={caller}] Retrieved {len(logs)} log entries")
        return {
            "logs": logs,
            "count": len(logs),
            "since": since,
            "until": until
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error retrieving logs: {str(e)}")
        raise