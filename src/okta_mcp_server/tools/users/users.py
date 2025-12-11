from typing import Optional
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client


@mcp.tool()
async def list_users(
    ctx: Context = None,
    query: str = None,
    limit: int = 100
) -> dict:
    """
    List Okta users (requires users.read scope).
    
    Args:
        query: Optional search query (e.g., 'status eq "ACTIVE"')
        limit: Maximum number of users to return (default 100)
    
    Returns:
        Dict with users list and metadata
    """
    logger.info(f"Listing users (query={query}, limit={limit})")
    params = {"limit": limit}
    if query:
        params["search"] = query
    
    try:
        client = get_client()
        users = await client.get("/api/v1/users", params=params)
        logger.info(f"✅ Found {len(users)} users")
        return {
            "users": users,
            "count": len(users),
            "query": query
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error listing users: {str(e)}")
        raise


@mcp.tool()
async def get_user(user_id: str, ctx: Context = None) -> dict:
    """
    Get details for a specific user (requires users.read scope).
    
    Args:
        user_id: Okta user ID or login email
    
    Returns:
        User object with full details
    """
    logger.info(f"Getting user: {user_id}")
    try:
        client = get_client()
        user = await client.get(f"/api/v1/users/{user_id}")
        logger.info(f"✅ Retrieved user: {user.get('profile', {}).get('email')}")
        return user
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting user: {str(e)}")
        raise


@mcp.tool()
async def search_users(search: str, limit: int = 50, ctx: Context = None) -> dict:
    """
    Search for users by name or email (requires users.read scope).
    
    Args:
        search: Search term (matches firstName, lastName, email)
        limit: Maximum results to return
    
    Returns:
        Dict with matching users
    """
    logger.info(f"Searching users: {search}")
    search_query = f'profile.firstName sw "{search}" or profile.lastName sw "{search}" or profile.email sw "{search}"'
    params = {
        "search": search_query,
        "limit": limit
    }
    
    try:
        client = get_client()
        users = await client.get("/api/v1/users", params=params)
        logger.info(f"✅ Search found {len(users)} users")
        return {
            "users": users,
            "count": len(users),
            "search_term": search
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error searching users: {str(e)}")
        raise


@mcp.tool()
async def get_user_groups(user_id: str, ctx: Context = None) -> dict:
    """
    Get groups that a user belongs to (requires users.read + groups.read scopes).
    
    Args:
        user_id: Okta user ID or login email
    
    Returns:
        Dict with user's groups
    """
    logger.info(f"Getting groups for user: {user_id}")
    try:
        client = get_client()
        groups = await client.get(f"/api/v1/users/{user_id}/groups")
        logger.info(f"✅ User belongs to {len(groups)} groups")
        return {
            "groups": groups,
            "count": len(groups),
            "user_id": user_id
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting user groups: {str(e)}")
        raise


@mcp.tool()
async def check_permissions(ctx: Context = None) -> dict:
    """
    Check what OAuth scopes are currently granted.
    
    Returns:
        Dict with scope information and capability flags
    """
    client = get_client()
    scopes = client.get_granted_scopes()
    token_info = client.get_token_info()
    
    return {
        "granted_scopes": scopes,
        "can_read_users": "okta.users.read" in scopes,
        "can_write_users": "okta.users.manage" in scopes,
        "can_read_groups": "okta.groups.read" in scopes,
        "can_write_groups": "okta.groups.manage" in scopes,
        "can_read_apps": "okta.apps.read" in scopes,
        "can_read_logs": "okta.logs.read" in scopes,
        "token_type": token_info.get("token_type"),
        "expires_in_seconds": token_info.get("expires_in"),
        "is_read_only": not any(s.endswith(".manage") for s in scopes)
    }
