from typing import Optional
from loguru import logger
from mcp.server.fastmcp import Context
from difflib import get_close_matches
from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client


@mcp.tool()
async def list_users(
    query: Optional[str] = None,  # ✅ Moved ctx to end, added Optional
    limit: int = 100,
    ctx: Context = None  # ✅ Context last
) -> dict:
    """
    List Okta users (requires users.read scope).
    
    Args:
        query: Optional search query (e.g., 'status eq "ACTIVE"')
        limit: Maximum number of users to return (default 100)
    
    Returns:
        Dict with users list and metadata
    """
    # ✅ Handle string "null" from MCP clients
    if query in ("null", "None", ""):
        query = None
    
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
async def find_user(identifier: str, ctx: Context = None) -> dict:
    """
    **PRIMARY TOOL for user lookup** - Universal user finder for Kaltura Okta.
    Finds users by ANY identifier with smart fallback to fuzzy search.
    
    Accepts:
    - Okta UUID (e.g., "00u1a2b3c4d5e6f7g8h9")
    - Full email (e.g., "chris.sengu@kaltura.com")
    - Username only (e.g., "chris.sengu" - auto-appends @kaltura.com)
    - Partial name (e.g., "chris", "sengu" - uses fuzzy search)
    
    Automatically:
    - Fixes @example.com to @kaltura.com
    - Tries exact match first, then fuzzy search
    - Handles typos and case variations
    
    Args:
        identifier: Any user identifier (UUID, email, username, or partial name)
    
    Returns:
        Dict with user object, match type, and all matches if fuzzy search was used
    """
    # ✅ Handle null/empty identifier
    if identifier in ("null", "None", ""):
        raise ValueError("identifier cannot be empty")
    
    logger.info(f"Finding user with identifier: {identifier}")
    
    # Fix Roo's sanitization of email domains
    if '@example.com' in identifier:
        original = identifier
        identifier = identifier.replace('@example.com', '@kaltura.com')
        logger.info(f"Fixed sanitized domain: {original} → {identifier}")
    
    # Auto-append @kaltura.com if it's a bare username (has no @ and not a UUID)
    if '@' not in identifier and not identifier.startswith('00u'):
        identifier = f"{identifier}@kaltura.com"
        logger.info(f"Appended domain: {identifier}")
    
    client = get_client()
    
    # Try exact match first (for UUIDs and full emails)
    try:
        user = await client.get(f"/api/v1/users/{identifier}")
        logger.info(f"✅ Found user by exact match: {user.get('profile', {}).get('email')}")
        return {
            "user": user,
            "match_type": "exact",
            "identifier_used": identifier
        }
    except Exception as e:
        logger.info(f"Exact match failed for '{identifier}': {str(e)}")
        logger.info("Falling back to fuzzy search...")
    
    # Fallback to fuzzy search
    # Extract search term (remove @kaltura.com if present for better fuzzy matching)
    search_term = identifier.replace('@kaltura.com', '').replace('@', '')
    
    try:
        fuzzy_result = await search_users_fuzzy(search_term, limit=200, ctx=ctx)
        
        if fuzzy_result['count'] == 0:
            raise Exception(
                f"No users found matching '{identifier}'. "
                f"Tried exact match and fuzzy search for '{search_term}'."
            )
        
        best_match = fuzzy_result['users'][0]
        logger.info(
            f"✅ Found {fuzzy_result['count']} fuzzy matches, "
            f"best match: {best_match.get('profile', {}).get('email')}"
        )
        
        return {
            "user": best_match,
            "match_type": "fuzzy",
            "match_count": fuzzy_result['count'],
            "all_matches": fuzzy_result['users'][:5],  # Return top 5
            "search_term": search_term,
            "original_identifier": identifier
        }
    except PermissionError as e:
        logger.error(f"❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error finding user: {str(e)}")
        raise


@mcp.tool()
async def get_user(user_id: str, ctx: Context = None) -> dict:
    """
    Get user by EXACT Okta user ID or email (requires users.read scope).
    
    ⚠️ For most lookups, use find_user instead - it's smarter and handles fuzzy matching.
    Only use this if you have the exact UUID or confirmed email address.
    
    Args:
        user_id: Exact Okta user ID (UUID) or exact login email
    
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
async def search_users(
    search: str,
    limit: int = 50,
    ctx: Context = None  # ✅ Already correct position
) -> dict:
    """
    Search for users by name or email (requires users.read scope).
    
    Args:
        search: Search term (matches firstName, lastName, email)
        limit: Maximum results to return
    
    Returns:
        Dict with matching users
    """
    # ✅ Handle empty/null search
    if search in ("null", "None"):
        search = ""
    
    logger.info(f"Searching users: {search}")
    
    # ✅ Handle empty search - return all users
    if not search:
        try:
            client = get_client()
            users = await client.get("/api/v1/users", params={"limit": limit})
            logger.info(f"✅ Empty search, returning all {len(users)} users")
            return {
                "users": users,
                "count": len(users),
                "search_term": ""
            }
        except PermissionError as e:
            logger.error(f"❌ Permission denied: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Error listing users: {str(e)}")
            raise
    
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
async def search_users_fuzzy(
    search_term: str,
    limit: int = 200,
    ctx: Context = None  # ✅ Already correct position
) -> dict:
    """Fuzzy search Okta users by name or email.
    
    More forgiving than search_users:
    - Handles typos in email / first / last name
    - Case-insensitive
    - Combines fuzzy and substring matching
    """
    # ✅ Handle empty/null search
    if search_term in ("null", "None"):
        search_term = ""
    
    logger.info(f"Fuzzy searching users: {search_term} (limit={limit})")
    client = get_client()
    
    try:
        # Start from a broad user list (you can narrow later if needed)
        users = await client.get("/api/v1/users", params={"limit": limit})
        
        # ✅ Handle empty search - return all users
        if not search_term:
            logger.info(f"✅ Empty search term, returning all {len(users)} users")
            return {
                "users": users,
                "count": len(users),
                "search_term": "",
                "matched_keys": [make_key(u) for u in users],
                "search_type": "all",
            }
        
        # Build display strings to match against (email + name)
        def make_key(u: dict) -> str:
            profile = u.get("profile", {})
            return " ".join(filter(None, [
                profile.get("firstName", ""),
                profile.get("lastName", ""),
                profile.get("email", ""),
                profile.get("login", ""),
            ]))
        
        keys = [make_key(u) for u in users]
        
        fuzzy_keys = get_close_matches(
            search_term,
            keys,
            n=20,
            cutoff=0.4,
        )
        
        search_lower = search_term.lower()
        substring_keys = [
            k for k in keys
            if search_lower in k.lower() and k not in fuzzy_keys
        ]
        
        all_match_keys = fuzzy_keys + substring_keys[:20]
        
        matched_users = [
            u for u, k in zip(users, keys)
            if k in all_match_keys
        ]
        
        logger.info(f"✅ Fuzzy user search found {len(matched_users)} matches for '{search_term}'")
        
        return {
            "users": matched_users,
            "count": len(matched_users),
            "search_term": search_term,
            "matched_keys": all_match_keys,
            "search_type": "fuzzy",
        }
    
    except PermissionError as e:
        logger.error(f"❌ Permission denied in fuzzy user search: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error in fuzzy user search: {str(e)}")
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
