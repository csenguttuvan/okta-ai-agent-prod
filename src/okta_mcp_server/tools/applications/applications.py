from typing import Optional
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.server import mcp
from okta_mcp_server.oauth_jwt_client import get_client

@mcp.tool()
async def list_applications(
    ctx: Context = None,
    query: str = None,
    limit: int = 100
) -> dict:
    """
    List Okta applications (requires apps.read scope).
    
    Args:
        query: Optional search query
        limit: Maximum number of apps to return
    
    Returns:
        Dict with applications list and metadata
    """
    logger.info(f"Listing applications (query={query}, limit={limit})")
    
    params = {"limit": limit}
    if query:
        params["q"] = query
    
    try:
        apps = await get_client().get("/api/v1/apps", params=params)
        logger.info(f"✅ Found {len(apps)} applications")
        return {
            "applications": apps,
            "count": len(apps),
            "query": query
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error listing applications: {str(e)}")
        raise

@mcp.tool()
async def get_application(app_id: str, ctx: Context = None) -> dict:
    """
    Get details for a specific application (requires apps.read scope).
    
    Args:
        app_id: Okta application ID
    
    Returns:
        Application object with full details
    """
    logger.info(f"Getting application: {app_id}")
    
    try:
        app = await get_client().get(f"/api/v1/apps/{app_id}")
        logger.info(f"✅ Retrieved application: {app.get('label', app_id)}")
        return app
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting application: {str(e)}")
        raise

@mcp.tool()
async def list_application_users(app_id: str, limit: int = 100, ctx: Context = None) -> dict:
    """
    List users assigned to an application (requires apps.read scope).
    
    Args:
        app_id: Okta application ID
        limit: Maximum number of users to return
    
    Returns:
        Dict with users assigned to the app
    """
    logger.info(f"Listing users for application: {app_id}")
    
    params = {"limit": limit}
    
    try:
        users = await get_client().get(f"/api/v1/apps/{app_id}/users", params=params)
        logger.info(f"✅ Found {len(users)} users assigned to app")
        return {
            "users": users,
            "count": len(users),
            "app_id": app_id
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error listing application users: {str(e)}")
        raise

@mcp.tool()
async def list_application_groups(app_id: str, limit: int = 100, ctx: Context = None) -> dict:
    """
    List groups assigned to an application (requires apps.read scope).
    
    Args:
        app_id: Okta application ID
        limit: Maximum number of groups to return
    
    Returns:
        Dict with groups assigned to the app
    """
    logger.info(f"Listing groups for application: {app_id}")
    
    params = {"limit": limit}
    
    try:
        groups = await get_client().get(f"/api/v1/apps/{app_id}/groups", params=params)
        logger.info(f"✅ Found {len(groups)} groups assigned to app")
        return {
            "groups": groups,
            "count": len(groups),
            "app_id": app_id
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error listing application groups: {str(e)}")
        raise