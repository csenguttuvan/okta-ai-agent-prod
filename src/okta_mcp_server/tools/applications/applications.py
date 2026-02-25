from typing import Optional, Dict, Any
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client
from okta_mcp_server.context import get_caller_email, get_caller_groups



@mcp.tool()
def list_applications(
    ctx: Context | None = None,
    limit: int = 20,
    after: Optional[str] = None,
    filter: Optional[str] = None,
    search: Optional[str] = None,  # ← ADD THIS
) -> str:
    """List all applications in the Okta organization.

    Args:
        limit: Maximum number of applications to return (default 20)
        after: Pagination cursor for next page
        filter: Filter expression (e.g., 'status eq "ACTIVE"')
        search: Search term to filter by app name (case-insensitive substring match)

    Returns:
        String containing formatted list of applications
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing applications limit={limit} search={search}")

    params = {"limit": limit}
    if after:
        params["after"] = after
    if filter:
        params["filter"] = filter
    if search:
        # Okta supports q= for app name search
        params["q"] = search

    try:
        client = get_client()
        apps = client.get("/api/v1/apps", params=params)
        logger.info(f"[caller={caller}] Found {len(apps)} applications")

        if not apps:
            return f"No applications found{f' matching {search!r}' if search else ''}."

        lines = [f"Found {len(apps)} applications:\n"]
        for app in apps:
            lines.append(
                f"• {app.get('label', 'N/A')} (ID: {app.get('id', 'N/A')})\n"
                f"  Status: {app.get('status', 'N/A')}, Sign-on: {app.get('signOnMode', 'N/A')}"
            )
        return "\n".join(lines)

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error listing applications: {str(e)}"


@mcp.tool()
def get_application(
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
        app = client.get(f"/api/v1/apps/{app_id}")
        logger.info(f"[caller={caller}] Retrieved application: {app.get('label', 'N/A')}")
        return app
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error getting application: {str(e)}")
        raise

@mcp.tool()
def find_application(
    ctx: Context | None = None,
    names: list[str] = [],
) -> str:
    """Find one or more applications by name using exact or fuzzy search.

    Args:
        names: List of application names to search for (e.g. ["Outreach - SSO", "Outreach - Stg Prov"])

    Returns:
        String containing matched applications with their IDs
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Finding applications: {names}")

    if not names:
        return "❌ Please provide at least one application name to search for."

    client = get_client()
    results = {}

    for name in names:
        try:
            # Use Okta's q= param for server-side name search
            apps = client.get("/api/v1/apps", params={"q": name, "limit": 10})

            if not apps:
                results[name] = "❌ Not found"
                continue

            # Exact match first, then fuzzy
            name_lower = name.lower()
            exact = [a for a in apps if a.get("label", "").lower() == name_lower]
            matches = exact if exact else apps

            results[name] = [
                {
                    "id": a.get("id"),
                    "label": a.get("label"),
                    "status": a.get("status"),
                    "signOnMode": a.get("signOnMode"),
                }
                for a in matches[:3]  # Return top 3 matches max
            ]

        except Exception as e:
            results[name] = f"❌ Error: {str(e)}"

    # Format output
    lines = []
    for name, matches in results.items():
        lines.append(f"\n🔍 Search: '{name}'")
        if isinstance(matches, str):
            lines.append(f"  {matches}")
        else:
            for m in matches:
                lines.append(
                    f"  • {m['label']} (ID: {m['id']})\n"
                    f"    Status: {m['status']}, Sign-on: {m['signOnMode']}"
                )
    return "\n".join(lines)

@mcp.tool()
def search_applications_fuzzy(query: str, ctx: Context | None = None) -> dict:
    """Fuzzy search for Okta applications by name. Use when you don't know the exact app name.
    Example: { "query": "databricks" }"""
    caller = get_caller_email()
    log_tool_call("search_applications_fuzzy", {"query": query}, caller)
    
    try:
        apps = okta_client.list_applications()
        query_lower = query.lower()
        
        matches = [
            app for app in apps
            if query_lower in app.get("label", "").lower()
            or query_lower in app.get("name", "").lower()
        ]
        
        if not matches:
            return {"found": False, "message": f"No applications found matching '{query}'"}
        
        return {
            "found": True,
            "count": len(matches),
            "applications": [
                {
                    "id": app.get("id"),
                    "label": app.get("label"),
                    "name": app.get("name"),
                    "status": app.get("status"),
                }
                for app in matches
            ]
        }
    except Exception as e:
        return handle_okta_error(e, "search_applications_fuzzy")


@mcp.tool()
def list_application_users(
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
        users = client.get(f"/api/v1/apps/{app_id}/users", params=params)
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
def list_application_groups(
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
        groups = client.get(f"/api/v1/apps/{app_id}/groups", params=params)
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