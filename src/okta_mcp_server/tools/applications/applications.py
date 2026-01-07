from typing import Optional, Dict, Any
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client
from okta_mcp_server.context import get_caller_email, get_caller_groups



@mcp.tool()
async def list_applications(
    ctx: Context | None = None,
    limit: int = 20,
    after: Optional[str] = None,
    filter: Optional[str] = None
) -> Dict[str, Any]:
    """List all applications in the Okta organization.

    Args:
        limit: Maximum number of applications to return (default 20)
        after: Pagination cursor for next page
        filter: Filter expression (e.g., 'status eq "ACTIVE"')

    Returns:
        Dict containing list of applications
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing applications limit={limit}")

    params = {"limit": limit}
    if after:
        params["after"] = after
    if filter:
        params["filter"] = filter

    try:
        client = get_client()
        apps = await client.get("/api/v1/apps", params=params)
        logger.info(f"[caller={caller}] Found {len(apps)} applications")
        return {
            "applications": apps,
            "count": len(apps)
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing applications: {str(e)}")
        raise

@mcp.tool()
async def get_application(
    ctx: Context | None = None,
    app_id: str = ""
) -> Optional[Dict[str, Any]]:
    """Get details of a specific application by ID.

    Args:
        app_id: The Okta application ID

    Returns:
        Dict containing application details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting application: {app_id}")

    if not app_id:
        logger.error(f"[caller={caller}] app_id is required")
        raise ValueError("app_id is required")

    try:
        client = get_client()
        app = await client.get(f"/api/v1/apps/{app_id}")
        logger.info(f"[caller={caller}] Retrieved application: {app.get('label', 'N/A')}")
        return app
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error getting application: {str(e)}")
        raise

@mcp.tool()
async def list_application_users(
    ctx: Context | None = None,
    app_id: str = "",
    limit: int = 50
) -> Dict[str, Any]:
    """List users assigned to an application.

    Args:
        app_id: The Okta application ID
        limit: Maximum number of users to return

    Returns:
        Dict containing list of assigned users
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing users for application: {app_id}")

    if not app_id:
        logger.error(f"[caller={caller}] app_id is required")
        raise ValueError("app_id is required")

    params = {"limit": limit}

    try:
        client = get_client()
        users = await client.get(f"/api/v1/apps/{app_id}/users", params=params)
        logger.info(f"[caller={caller}] Found {len(users)} users for application {app_id}")
        return {
            "users": users,
            "count": len(users),
            "app_id": app_id
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing application users: {str(e)}")
        raise

@mcp.tool()
async def list_application_groups(
    ctx: Context | None = None,
    app_id: str = "",
    limit: int = 50
) -> Dict[str, Any]:
    """List groups assigned to an application.

    Args:
        app_id: The Okta application ID
        limit: Maximum number of groups to return

    Returns:
        Dict containing list of assigned groups
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing groups for application: {app_id}")

    if not app_id:
        logger.error(f"[caller={caller}] app_id is required")
        raise ValueError("app_id is required")

    params = {"limit": limit}

    try:
        client = get_client()
        groups = await client.get(f"/api/v1/apps/{app_id}/groups", params=params)
        logger.info(f"[caller={caller}] Found {len(groups)} groups for application {app_id}")
        return {
            "groups": groups,
            "count": len(groups),
            "app_id": app_id
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing application groups: {str(e)}")
        raise

@mcp.tool()
async def assign_user_to_application(
    ctx: Context | None = None,
    app_id: str = "",
    user_id: str = ""
) -> Dict[str, Any]:
    """Assign a user to an application.

    Args:
        app_id: The Okta application ID
        user_id: The Okta user ID

    Returns:
        Dict with assignment details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Assigning user {user_id} to application {app_id}")

    if not app_id or not user_id:
        logger.error(f"[caller={caller}] app_id and user_id are required")
        raise ValueError("app_id and user_id are required")

    try:
        client = get_client()
        assignment = await client.post(
            f"/api/v1/apps/{app_id}/users",
            data={"id": user_id}
        )
        logger.info(f"[caller={caller}] Assigned user {user_id} to application {app_id}")
        return assignment
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error assigning user to application: {str(e)}")
        raise

@mcp.tool()
async def assign_group_to_application(
    ctx: Context | None = None,
    app_id: str = "",
    group_id: str = ""
) -> Dict[str, Any]:
    """Assign a group to an application.

    Args:
        app_id: The Okta application ID
        group_id: The Okta group ID

    Returns:
        Dict with assignment details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Assigning group {group_id} to application {app_id}")

    if not app_id or not group_id:
        logger.error(f"[caller={caller}] app_id and group_id are required")
        raise ValueError("app_id and group_id are required")

    try:
        client = get_client()
        assignment = await client.put(
            f"/api/v1/apps/{app_id}/groups/{group_id}",
            data={}
        )
        logger.info(f"[caller={caller}] Assigned group {group_id} to application {app_id}")
        return assignment
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error assigning group to application: {str(e)}")
        raise