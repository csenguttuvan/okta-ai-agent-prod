from typing import Optional
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client


@mcp.tool()
async def create_user(
    email: str,
    first_name: str,
    last_name: str,
    activate: bool = True,
    ctx: Context = None
) -> dict:
    """Create a new Okta user (requires okta.users.manage scope)."""
    logger.info(f"Creating user: {email}")
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
        user = await client.post("/api/v1/users", data=body, params=params)
        logger.info(f"✅ Created user: {user.get('id')}")
        return user
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error creating user: {str(e)}")
        raise


@mcp.tool()
async def deactivate_user(user_id: str, ctx: Context = None) -> dict:
    """Deactivate an Okta user (requires okta.users.manage scope)."""
    logger.info(f"Deactivating user: {user_id}")
    client = get_client()

    try:
        await client.post(f"/api/v1/users/{user_id}/lifecycle/deactivate", data={})
        logger.info(f"✅ Deactivated user: {user_id}")
        return {"message": f"User {user_id} deactivated successfully"}
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error deactivating user: {str(e)}")
        raise


@mcp.tool()
async def delete_user(user_id: str, ctx: Context = None) -> dict:
    """Delete an Okta user (requires okta.users.manage scope).
    Note: User must be deactivated first."""
    logger.info(f"Deleting user: {user_id}")
    client = get_client()
    
    try:
        await client.delete(f"/api/v1/users/{user_id}")
        logger.info(f"✅ Deleted user: {user_id}")
        return {"message": f"User {user_id} deleted successfully"}
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting user: {str(e)}")
        raise
