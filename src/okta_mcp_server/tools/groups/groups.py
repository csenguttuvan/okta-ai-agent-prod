from typing import Optional, List
from loguru import logger
from mcp.server.fastmcp import Context
from difflib import get_close_matches

from okta_mcp_server.context import get_caller_email, get_caller_groups
from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client


@mcp.tool()
def list_groups( 
    limit: int = 100,
    query: Optional[str] = None,
    ctx: Context | None = None
) -> str:  # ✅ Simple string return
    """List Okta groups (requires groups.read scope)."""
    caller = get_caller_email()

    # Normalize query
    if query in ("null", "", None):
        query = None

    # Normalize limit
    try:
        limit_int = int(limit) if isinstance(limit, (str, int)) else 100
    except (TypeError, ValueError):
        limit_int = 100

    logger.info(f"[caller={caller}] listing groups query={query}, limit={limit_int}")

    try:
        client = get_client()
        params = {"limit": limit_int}
        if query:
            params["q"] = query

        groups = client.get("/api/v1/groups", params=params)
        logger.info(f"[caller={caller}] Found {len(groups)} groups")

        if not groups:
            return "No groups found."

        # Format as readable string
        lines = [f"Found {len(groups)} groups:\n"]
        
        for g in groups:
            profile = g.get("profile") or {}
            lines.append(
                f"• {profile.get('name', 'N/A')} "
                f"(ID: {g.get('id', 'N/A')}, "
                f"Type: {g.get('type', 'N/A')})"
            )
            if profile.get("description"):
                lines.append(f"  Description: {profile.get('description')}")

        return "\n".join(lines)

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error listing groups: {str(e)}"



@mcp.tool()
def search_groups_fuzzy(
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
    caller = get_caller_email()

    if search_term in ("null", None):
        search_term = ""

    logger.info(f"[caller={caller}] Fuzzy searching groups: {search_term} limit={limit}")

    client = get_client()
    try:
        groups = client.get("/api/v1/groups", params={"limit": limit})

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
def get_group(group_id: str, ctx: Context | None = None) -> dict:
    """Get details for a specific group (requires groups.read scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting group: {group_id}")

    client = get_client()
    try:
        group = client.get(f"/api/v1/groups/{group_id}")
        logger.info(f"[caller={caller}] Retrieved group: {group.get('profile', {}).get('name')}")
        return group

    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error getting group: {str(e)}")
        raise


@mcp.tool()
def list_group_users(
    group_id: str,
    limit: int = 100,
    ctx: Context | None = None
) -> dict:
    """List users in a group (requires groups.read scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing users in group: {group_id}")

    client = get_client()
    params = {"limit": limit}

    try:
        users = client.get(f"/api/v1/groups/{group_id}/users", params=params)
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