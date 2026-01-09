from typing import Optional
from loguru import logger
from mcp.server.fastmcp import Context
from difflib import get_close_matches

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client
from okta_mcp_server.context import get_caller_email


# ---------------------------
# Helpers
# ---------------------------

def _make_key(u: dict) -> str:
    """Build a searchable string for a user."""
    profile = u.get("profile", {})
    return " ".join(filter(None, [
        profile.get("firstName", ""),
        profile.get("lastName", ""),
        profile.get("email", ""),
        profile.get("login", "")
    ]))


def _normalize_user(u: dict) -> dict:
    """Return a safe, compact user representation for MCP."""
    profile = u.get("profile", {})
    return {
        "id": u.get("id"),
        "status": u.get("status"),
        "email": profile.get("email"),
        "login": profile.get("login"),
        "first_name": profile.get("firstName"),
        "last_name": profile.get("lastName"),
        "display_name": profile.get("displayName"),
    }


# ---------------------------
# Tools
# ---------------------------

@mcp.tool()
async def list_users(
    query: Optional[str] = None,
    limit: int = 100,
    ctx: Context | None = None
) -> dict:
    """List Okta users (requires users.read scope)."""
    caller = get_caller_email()

    if query in ("null", None):
        query = None

    logger.info(f"[caller={caller}] listing users query={query}, limit={limit}")

    params = {"limit": limit}
    if query:
        params["search"] = query

    client = get_client()
    users = await client.get("/api/v1/users", params=params)

    normalized = [_normalize_user(u) for u in users]

    logger.info(f"[caller={caller}] Found {len(normalized)} users")

    return {
        "users": normalized,
        "count": len(normalized),
        "query": query
    }


@mcp.tool()
async def find_user(identifier: str, ctx: Context | None = None) -> dict:
    """Universal user lookup with exact + fuzzy fallback."""
    caller = get_caller_email()

    if not identifier or identifier == "null":
        raise ValueError("identifier cannot be empty")

    logger.info(f"[caller={caller}] Finding user: {identifier}")

    if "@" not in identifier and not identifier.startswith("00u"):
        identifier = f"{identifier}@kaltura.com"

    client = get_client()

    # Exact match
    try:
        user = await client.get(f"/api/v1/users/{identifier}")
        logger.info(f"[caller={caller}] Exact match found: {user['profile'].get('email')}")
        return {
            "user": _normalize_user(user),
            "match_type": "exact",
            "identifier_used": identifier
        }
    except Exception:
        logger.info(f"[caller={caller}] Exact match failed, falling back to fuzzy search")

    # Fuzzy fallback
    search_term = identifier.replace("@kaltura.com", "").replace("@", " ")
    fuzzy = await search_users_fuzzy(search_term, limit=200, ctx=ctx)

    if fuzzy["count"] == 0:
        raise ValueError(f"No users found matching {identifier}")

    best = fuzzy["users"][0]

    return {
        "user": best,
        "match_type": "fuzzy",
        "match_count": fuzzy["count"],
        "search_term": search_term
    }


@mcp.tool()
async def get_user(user_id: str, ctx: Context | None = None) -> dict:
    """Get user by exact Okta ID or login."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting user: {user_id}")

    client = get_client()
    user = await client.get(f"/api/v1/users/{user_id}")

    return _normalize_user(user)


@mcp.tool()
async def search_users(
    search: str,
    limit: int = 50,
    ctx: Context | None = None
) -> dict:
    """Search users using Okta search syntax."""
    caller = get_caller_email()

    if not search or search == "null":
        search = ""

    logger.info(f"[caller={caller}] Searching users: {search}")

    client = get_client()

    if not search:
        users = await client.get("/api/v1/users", params={"limit": limit})
    else:
        search_query = (
            f'profile.firstName sw "{search}" or '
            f'profile.lastName sw "{search}" or '
            f'profile.email sw "{search}"'
        )
        users = await client.get(
            "/api/v1/users",
            params={"search": search_query, "limit": limit}
        )

    normalized = [_normalize_user(u) for u in users]

    return {
        "users": normalized,
        "count": len(normalized),
        "search_term": search
    }


@mcp.tool()
async def search_users_fuzzy(
    search_term: str,
    limit: int = 200,
    ctx: Context | None = None
) -> dict:
    """Fuzzy search users by name/email."""
    caller = get_caller_email()

    if not search_term or search_term == "null":
        search_term = ""

    logger.info(f"[caller={caller}] Fuzzy searching users: {search_term}")

    client = get_client()
    users = await client.get("/api/v1/users", params={"limit": limit})

    if not search_term:
        normalized = [_normalize_user(u) for u in users]
        return {
            "users": normalized,
            "count": len(normalized),
            "search_term": "",
            "search_type": "all"
        }

    keys = [_make_key(u) for u in users]
    fuzzy_keys = get_close_matches(search_term, keys, n=20, cutoff=0.4)

    search_lower = search_term.lower()
    substring_keys = [
        k for k in keys
        if search_lower in k.lower() and k not in fuzzy_keys
    ]

    matched_keys = (fuzzy_keys + substring_keys)[:20]

    matched_users = [
        _normalize_user(u)
        for u, k in zip(users, keys)
        if k in matched_keys
    ]

    logger.info(f"[caller={caller}] Fuzzy matches: {len(matched_users)}")

    return {
        "users": matched_users,
        "count": len(matched_users),
        "search_term": search_term,
        "search_type": "fuzzy"
    }


@mcp.tool()
async def get_user_groups(user_id: str, ctx: Context | None = None) -> dict:
    """Get groups a user belongs to."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting groups for user: {user_id}")

    client = get_client()
    groups = await client.get(f"/api/v1/users/{user_id}/groups")

    return {
        "groups": [
            {
                "id": g.get("id"),
                "name": g.get("profile", {}).get("name"),
                "description": g.get("profile", {}).get("description"),
            }
            for g in groups
        ],
        "count": len(groups),
        "user_id": user_id
    }


@mcp.tool()
async def check_permissions(ctx: Context | None = None) -> dict:
    """Return granted OAuth scopes and capability flags."""
    client = get_client()
    scopes = client.get_granted_scopes()
    token_info = client.get_token_info()

    return {
        "granted_scopes": scopes,
        "can_read_users": "okta.users.read" in scopes,
        "can_write_users": "okta.users.manage" in scopes,
        "can_read_groups": "okta.groups.read" in scopes,
        "can_write_groups": "okta.groups.manage" in scopes,
        "token_type": token_info.get("token_type"),
        "expires_in_seconds": token_info.get("expires_in"),
        "is_read_only": not any(s.endswith(".manage") for s in scopes)
    }
