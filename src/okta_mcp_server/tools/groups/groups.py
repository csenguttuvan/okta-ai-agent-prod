from typing import Optional
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client

@mcp.tool()
async def list_groups(
    ctx: Context = None,
    query: Optional[str] = None,
    limit: int = 100
) -> dict:
    """List Okta groups (requires groups.read scope)."""
    logger.info(f"Listing groups (query={query}, limit={limit})")
    client = get_client()

    params = {"limit": limit}
    if query:
        params["q"] = query

    try:
        groups = await client.get("/api/v1/groups", params=params)
        logger.info(f"✅ Found {len(groups)} groups")
        return {
            "groups": groups,
            "count": len(groups),
            "query": query
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error listing groups: {str(e)}")
        raise

@mcp.tool()
async def get_group(group_id: str, ctx: Context = None) -> dict:
    """Get details for a specific group (requires groups.read scope)."""
    logger.info(f"Getting group: {group_id}")
    client = get_client()

    try:
        group = await client.get(f"/api/v1/groups/{group_id}")
        logger.info(f"✅ Retrieved group: {group.get('profile', {}).get('name')}")
        return group
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting group: {str(e)}")
        raise

@mcp.tool()
async def list_group_users(group_id: str, limit: int = 100, ctx: Context = None) -> dict:
    """List users in a group (requires groups.read scope)."""
    logger.info(f"Listing users in group: {group_id}")
    client = get_client()

    params = {"limit": limit}

    try:
        users = await client.get(f"/api/v1/groups/{group_id}/users", params=params)
        logger.info(f"✅ Found {len(users)} users in group")
        return {
            "users": users,
            "count": len(users),
            "group_id": group_id
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error listing group users: {str(e)}")
        raise


@mcp.tool()
async def create_group(
name: str,
description: Optional[str] = None,
ctx: Context = None
) -> dict:
    """Create a new Okta group (requires okta.groups.manage scope)."""
    logger.info(f"Creating group: {name}")
    client = get_client()
    
    profile = {"name": name}
    if description:
        profile["description"] = description
    
    try:
        group = await client.post("/api/v1/groups", data={"profile": profile})
        logger.info(f"✅ Created group: {group.get('id')}")
        return group
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error creating group: {str(e)}")
        raise


@mcp.tool()
async def delete_group(group_id: str, ctx: Context = None) -> dict:
    """Delete an Okta group (requires okta.groups.manage scope)."""
    logger.info(f"Deleting group: {group_id}")
    client = get_client()
    
    try:
        await client.delete(f"/api/v1/groups/{group_id}")
        logger.info(f"✅ Deleted group: {group_id}")
        return {"message": f"Group {group_id} deleted successfully"}
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting group: {str(e)}")
        raise


@mcp.tool()
async def add_user_to_group(
    group_id: str,
    user_id: str,
    ctx: Context = None
) -> dict:
    """Add a user to a group (requires okta.groups.manage scope)."""
    logger.info(f"Adding user {user_id} to group {group_id}")
    client = get_client()
    
    try:
        await client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
        logger.info(f"✅ Added user {user_id} to group {group_id}")
        return {"message": f"User added to group successfully"}
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error adding user to group: {str(e)}")
        raise


@mcp.tool()
async def remove_user_from_group(
    group_id: str,
    user_id: str,
    ctx: Context = None
) -> dict:
    """Remove a user from a group (requires okta.groups.manage scope)."""
    logger.info(f"Removing user {user_id} from group {group_id}")
    client = get_client()
    
    try:
        await client.delete(f"/api/v1/groups/{group_id}/users/{user_id}")
        logger.info(f"✅ Removed user {user_id} from group {group_id}")
        return {"message": f"User removed from group successfully"}
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error removing user from group: {str(e)}")
        raise
