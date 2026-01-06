from typing import Optional, List
from loguru import logger
from mcp.server.fastmcp import Context
from difflib import get_close_matches

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
async def list_groups(
    query: Optional[str] = None,
    limit: int = 100,
    ctx: Context | None = None
) -> dict:
    """List Okta groups (requires groups.read scope)."""
    caller = get_caller_email(ctx)

    if query in ("null", None):
        query = None

    logger.info(f"[caller={caller}] listing groups query={query}, limit={limit}")

    client = get_client()
    params = {"limit": limit}
    if query:
        params["q"] = query

    try:
        groups = await client.get("/api/v1/groups", params=params)
        logger.info(f"[caller={caller}] Found {len(groups)} groups")
        return {
            "groups": groups,
            "count": len(groups),
            "query": query
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing groups: {str(e)}")
        raise

@mcp.tool()
async def search_groups_fuzzy(
    search_term: str,
    limit: int = 200,
    ctx: Context | None = None
) -> dict:
    """Fuzzy search Okta groups by name (handles typos and partial names).

    This is more forgiving than list_groups:
        - "disciplew dev" can match "Disciples-dev"
        - Case-insensitive
        - Also tries substring matches
    """
    caller = get_caller_email(ctx)

    if search_term in ("null", None):
        search_term = ""

    logger.info(f"[caller={caller}] Fuzzy searching groups: {search_term} limit={limit}")

    client = get_client()

    try:
        groups = await client.get("/api/v1/groups", params={"limit": limit})

        if not search_term:
            logger.info(f"[caller={caller}] Empty search term, returning all {len(groups)} groups")
            return {
                "groups": groups,
                "count": len(groups),
                "search_term": search_term,
                "matched_names": [g["profile"]["name"] for g in groups],
                "search_type": "all"
            }

        names = [g["profile"]["name"] for g in groups]

        # Fuzzy matches
        fuzzy_names = get_close_matches(search_term, names, n=10, cutoff=0.4)

        # Substring matches
        search_lower = search_term.lower()
        substring_names = [name for name in names if search_lower in name.lower() and name not in fuzzy_names]

        all_match_names = (fuzzy_names + substring_names)[:10]
        matched = [g for g in groups if g["profile"]["name"] in all_match_names]

        logger.info(f"[caller={caller}] Fuzzy group search found {len(matched)} matches for: {search_term}")

        return {
            "groups": matched,
            "count": len(matched),
            "search_term": search_term,
            "matched_names": all_match_names,
            "search_type": "fuzzy"
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied in fuzzy group search: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error in fuzzy group search: {str(e)}")
        raise

@mcp.tool()
async def get_group(group_id: str, ctx: Context | None = None) -> dict:
    """Get details for a specific group (requires groups.read scope)."""
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Getting group: {group_id}")

    client = get_client()

    try:
        group = await client.get(f"/api/v1/groups/{group_id}")
        logger.info(f"[caller={caller}] Retrieved group: {group.get('profile', {}).get('name')}")
        return group
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error getting group: {str(e)}")
        raise

@mcp.tool()
async def list_group_users(
    group_id: str,
    limit: int = 100,
    ctx: Context | None = None
) -> dict:
    """List users in a group (requires groups.read scope)."""
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Listing users in group: {group_id}")

    client = get_client()
    params = {"limit": limit}

    try:
        users = await client.get(f"/api/v1/groups/{group_id}/users", params=params)
        logger.info(f"[caller={caller}] Found {len(users)} users in group")
        return {
            "users": users,
            "count": len(users),
            "group_id": group_id
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing group users: {str(e)}")
        raise

@mcp.tool()
async def create_group(
    name: str,
    description: Optional[str] = None,
    ctx: Context | None = None
) -> dict:
    """Create a new Okta group (requires okta.groups.manage scope)."""
    caller = get_caller_email(ctx)

    if description in ("null", None):
        description = None

    logger.info(f"[caller={caller}] Creating group: {name}")

    client = get_client()
    profile = {"name": name}
    if description:
        profile["description"] = description

    try:
        group = await client.post("/api/v1/groups", data={"profile": profile})
        logger.info(f"[caller={caller}] Created group: {group.get('id')}")
        return group
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error creating group: {str(e)}")
        raise

@mcp.tool()
async def delete_group(group_id: str, ctx: Context | None = None) -> dict:
    """Delete an Okta group (requires okta.groups.manage scope)."""
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Deleting group: {group_id}")

    client = get_client()

    try:
        await client.delete(f"/api/v1/groups/{group_id}")
        logger.info(f"[caller={caller}] Deleted group: {group_id}")
        return {"message": f"Group {group_id} deleted successfully"}
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error deleting group: {str(e)}")
        raise

@mcp.tool()
async def add_user_to_group(
    group_id: str,
    user_id: str,
    ctx: Context | None = None
) -> dict:
    """Add a user to a group (requires okta.groups.manage scope)."""
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Adding user {user_id} to group {group_id}")

    client = get_client()

    try:
        await client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
        logger.info(f"[caller={caller}] Added user {user_id} to group {group_id}")
        logger.info(f"tool=add_user_to_group group_id={group_id} user_id={user_id} result=success")
        return {"message": "User added to group successfully"}
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        logger.error(f"tool=add_user_to_group group_id={group_id} user_id={user_id} result=error error={str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error adding user to group: {str(e)}")
        logger.error(f"tool=add_user_to_group group_id={group_id} user_id={user_id} result=error error={str(e)}")
        raise

@mcp.tool()
async def remove_user_from_group(
    group_id: str,
    user_id: str,
    ctx: Context | None = None
) -> dict:
    """Remove a user from a group (requires okta.groups.manage scope)."""
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Removing user {user_id} from group {group_id}")

    client = get_client()

    try:
        await client.delete(f"/api/v1/groups/{group_id}/users/{user_id}")
        logger.info(f"[caller={caller}] Removed user {user_id} from group {group_id}")
        return {"message": "User removed from group successfully"}
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error removing user from group: {str(e)}")
        raise

@mcp.tool()
async def remove_users_from_group(
    group_id: str,
    user_ids: List[str],
    ctx: Context | None = None
) -> dict:
    """Remove multiple users from a group in a single operation.

    Args:
        group_id: The Okta group ID
        user_ids: List of Okta user IDs to remove from the group

    Returns:
        Dictionary with removed count and results
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Batch removing {len(user_ids)} users from group {group_id}")

    client = get_client()
    results = []
    failed = []

    for user_id in user_ids:
        try:
            await client.delete(f"/api/v1/groups/{group_id}/users/{user_id}")
            results.append({"user_id": user_id, "status": "removed"})
            logger.info(f"[caller={caller}] Removed user {user_id} from group {group_id}")
            logger.info(f"tool=remove_users_from_group group_id={group_id} user_id={user_id} result=success")
        except Exception as e:
            failed.append({"user_id": user_id, "error": str(e)})
            logger.error(f"[caller={caller}] Failed to remove user {user_id}: {str(e)}")
            logger.error(f"tool=remove_users_from_group group_id={group_id} user_id={user_id} result=error error={str(e)}")

    return {
        "success": True,
        "total": len(user_ids),
        "removed": len(results),
        "failed": len(failed),
        "results": results,
        "failures": failed if failed else None
    }