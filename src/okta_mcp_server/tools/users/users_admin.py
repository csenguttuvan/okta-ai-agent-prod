from typing import Optional, List
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client
from okta_mcp_server.server import get_caller_email  # Import from server

@mcp.tool()
async def create_user(
    email: str,
    first_name: str,
    last_name: str,
    activate: bool = True,
    ctx: Context = None
) -> dict:
    """Create a new Okta user (requires okta.users.manage scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Creating user: {email}")
    
    client = get_client()
    profile = {
        "email": email,
        "login": email,
        "firstName": first_name,
        "lastName": last_name
    }
    
    body = {
        "profile": profile
    }
    
    params = {"activate": str(activate).lower()}
    
    try:
        user = await client.post(f"/api/v1/users?activate={str(activate).lower()}", data=body)
        logger.info(f"[caller={caller}] ✅ Created user: {user.get('id')}")
        return user
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error creating user: {str(e)}")
        raise

@mcp.tool()
async def deactivate_user(user_id: str, ctx: Context = None) -> dict:
    """Deactivate an Okta user (requires okta.users.manage scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Deactivating user: {user_id}")
    
    client = get_client()
    
    try:
        await client.post(f"/api/v1/users/{user_id}/lifecycle/deactivate", data={})
        logger.info(f"[caller={caller}] ✅ Deactivated user: {user_id}")
        return {"message": f"User {user_id} deactivated successfully"}
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error deactivating user: {str(e)}")
        raise

@mcp.tool()
async def delete_user(user_id: str, ctx: Context = None) -> dict:
    """Delete an Okta user (requires okta.users.manage scope).
    
    Note: User must be deactivated first."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Deleting user: {user_id}")
    
    client = get_client()
    
    try:
        await client.delete(f"/api/v1/users/{user_id}")
        logger.info(f"[caller={caller}] ✅ Deleted user: {user_id}")
        return {"message": f"User {user_id} deleted successfully"}
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error deleting user: {str(e)}")
        raise

@mcp.tool()
async def add_users_to_group(
    group_id: str,
    user_ids: List[str]
) -> dict:
    """Add multiple users to a group in a single operation
    
    Args:
        group_id: The Okta group ID
        user_ids: List of Okta user IDs to add to the group
        
    Returns:
        Dictionary with added count and results
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Batch adding {len(user_ids)} users to group {group_id}")
    
    try:
        client = get_client()
        results = []
        failed = []
        
        for user_id in user_ids:
            try:
                await client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
                results.append({
                    "user_id": user_id,
                    "status": "added"
                })
                logger.info(f"[caller={caller}] ✅ Added user {user_id} to group {group_id}")
            except Exception as e:
                failed.append({
                    "user_id": user_id,
                    "error": str(e)
                })
                logger.error(f"[caller={caller}] ❌ Failed to add user {user_id}: {str(e)}")
        
        return {
            "success": True,
            "total": len(user_ids),
            "added": len(results),
            "failed": len(failed),
            "results": results,
            "failures": failed if failed else None
        }
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Failed to initialize Okta client: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to initialize Okta client: {str(e)}"
        }
