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
    profile = u.get("profile", {})
    return " ".join(filter(None, [
        profile.get("firstName", ""),
        profile.get("lastName", ""),
        profile.get("email", ""),
        profile.get("login", "")
    ]))


def _normalize_user(u: dict) -> dict:
    profile = u.get("profile", {})
    return {
        "id": u.get("id"),
        "status": u.get("status"),
        "email": profile.get("email"),
        "login": profile.get("login"),
        "first_name": profile.get("firstName"),
        "last_name": profile.get("lastName"),
    }


def _format_users(users: list) -> str:
    if not users:
        return "No users found."
    lines = [f"Found {len(users)} user(s):\n"]
    for u in users:
        n = _normalize_user(u) if "profile" in u else u
        full_name = f"{n.get('first_name','')} {n.get('last_name','')}".strip() or "N/A"
        lines.append(
            f"• {full_name} ({n.get('email', 'N/A')})"
            f"\n  ID: {n.get('id', 'N/A')}, Status: {n.get('status', 'N/A')}"
        )
    return "\n".join(lines)


def _is_okta_id(s: str) -> bool:
    """Okta user IDs start with 00u and are ~20 chars."""
    return s.startswith("00u") and len(s) > 10


def _is_email(s: str) -> bool:
    return "@" in s and "." in s.split("@")[-1]


# ---------------------------
# Tools
# ---------------------------

@mcp.tool()
def list_users(
    limit: int = 100,
    query: Optional[str] = None,
    ctx: Context | None = None
) -> str:
    """List Okta users. Use query for name or email prefix search."""
    caller = get_caller_email()

    if query in ("null", None, ""):
        query = None

    logger.info(f"[caller={caller}] listing users query={query}, limit={limit}")

    params = {"limit": limit}
    if query:
        # q= does prefix search on firstName, lastName, email — NOT search=
        params["q"] = query

    try:
        client = get_client()
        users = client.get("/api/v1/users", params=params)
        logger.info(f"[caller={caller}] Found {len(users)} users")
        return _format_users(users)
    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error listing users: {str(e)}"


@mcp.tool()
def find_user(identifier: str, ctx: Context | None = None) -> dict:
    """Universal user lookup. Pass email, Okta ID (00u...), or full name like 'Teresa Kindred'.
    Example: { "identifier": "orly.lampert@kaltura.com" }"""
    caller = get_caller_email()

    if not identifier or identifier in ("null", ""):
        raise ValueError("identifier cannot be empty")

    identifier = identifier.strip()
    logger.info(f"[caller={caller}] Finding user: {identifier!r}")

    client = get_client()

    # --- Strategy 1: Okta ID direct lookup ---
    if _is_okta_id(identifier):
        try:
            user = client.get(f"/api/v1/users/{identifier}")
            logger.info(f"[caller={caller}] Found by ID")
            return {"user": _normalize_user(user), "match_type": "id"}
        except Exception:
            pass

    # --- Strategy 2: Email direct lookup ---
    if _is_email(identifier):
        try:
            user = client.get(f"/api/v1/users/{identifier}")
            logger.info(f"[caller={caller}] Found by exact email")
            return {"user": _normalize_user(user), "match_type": "exact_email"}
        except Exception:
            pass
        # Also try q= search for email
        try:
            users = client.get("/api/v1/users", params={"q": identifier, "limit": 5})
            if users:
                logger.info(f"[caller={caller}] Found by q= email search")
                return {"user": _normalize_user(users[0]), "match_type": "email_search",
                        "match_count": len(users)}
        except Exception:
            pass

    # --- Strategy 3: q= prefix search (works for full name and email prefix) ---
    try:
        users = client.get("/api/v1/users", params={"q": identifier, "limit": 10})
        if users:
            logger.info(f"[caller={caller}] Found {len(users)} via q= search")
            return {"user": _normalize_user(users[0]), "match_type": "q_search",
                    "match_count": len(users), "all_matches": [_normalize_user(u) for u in users]}
    except Exception:
        pass

    # --- Strategy 4: Okta expression search for first + last name ---
    parts = identifier.split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        expr = f'profile.firstName eq "{first}" and profile.lastName eq "{last}"'
        try:
            users = client.get("/api/v1/users", params={"search": expr, "limit": 10})
            if users:
                logger.info(f"[caller={caller}] Found via name expression search")
                return {"user": _normalize_user(users[0]), "match_type": "name_expression",
                        "match_count": len(users)}
        except Exception:
            pass

        # --- Strategy 5: Last name only q= search ---
        try:
            users = client.get("/api/v1/users", params={"q": last, "limit": 20})
            if users:
                # Filter by first name substring
                filtered = [u for u in users
                           if first.lower() in u.get("profile", {}).get("firstName", "").lower()]
                matches = filtered if filtered else users
                logger.info(f"[caller={caller}] Found via last name search, filtered to {len(matches)}")
                return {"user": _normalize_user(matches[0]), "match_type": "lastname_search",
                        "match_count": len(matches)}
        except Exception:
            pass

    # --- Strategy 6: Fuzzy fallback ---
    try:
        all_users = client.get("/api/v1/users", params={"limit": 200})
        keys = [_make_key(u) for u in all_users]
        fuzzy_keys = get_close_matches(identifier, keys, n=10, cutoff=0.4)
        search_lower = identifier.lower()
        substring_keys = [k for k in keys if search_lower in k.lower() and k not in fuzzy_keys]
        matched_keys = set(fuzzy_keys + substring_keys)
        matched = [_normalize_user(u) for u, k in zip(all_users, keys) if k in matched_keys]
        if matched:
            logger.info(f"[caller={caller}] Found {len(matched)} via fuzzy fallback")
            return {"user": matched[0], "match_type": "fuzzy", "match_count": len(matched),
                    "all_matches": matched[:5]}
    except Exception as e:
        logger.error(f"[caller={caller}] Fuzzy fallback failed: {e}")

    raise ValueError(f"No users found matching '{identifier}'")


@mcp.tool()
def get_user(user_id: str, ctx: Context | None = None) -> dict:
    """Get user by exact Okta ID or login/email."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting user: {user_id}")
    client = get_client()
    user = client.get(f"/api/v1/users/{user_id}")
    return _normalize_user(user)


@mcp.tool()
def search_users(
    search: str,
    limit: int = 50,
    ctx: Context | None = None
) -> dict:
    """Search users using Okta search syntax or plain name/email."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Searching users: {search}")
    client = get_client()

    if not search or search == "null":
        users = client.get("/api/v1/users", params={"limit": limit})
    else:
        # Try q= first (simpler, faster)
        try:
            users = client.get("/api/v1/users", params={"q": search, "limit": limit})
        except Exception:
            # Fall back to Okta expression
            expr = (
                f'profile.firstName sw "{search}" or ' 
                f'profile.lastName sw "{search}" or '
                f'profile.email sw "{search}"'
            )
            users = client.get("/api/v1/users", params={"search": expr, "limit": limit})

    normalized = [_normalize_user(u) for u in users]
    return {"users": normalized, "count": len(normalized), "search_term": search}


@mcp.tool()
def search_users_fuzzy(
    search_term: str,
    limit: int = 200,
    ctx: Context | None = None
) -> dict:
    """Fuzzy search users by name/email using substring and difflib matching."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Fuzzy searching: {search_term}")
    client = get_client()

    # First try fast q= search
    if search_term and search_term != "null":
        try:
            quick = client.get("/api/v1/users", params={"q": search_term, "limit": 20})
            if quick:
                return {"users": [_normalize_user(u) for u in quick],
                        "count": len(quick), "search_term": search_term, "search_type": "q_fast"}
        except Exception:
            pass

    # Fall back to full fuzzy scan
    users = client.get("/api/v1/users", params={"limit": limit})

    if not search_term or search_term == "null":
        return {"users": [_normalize_user(u) for u in users],
                "count": len(users), "search_term": "", "search_type": "all"}

    keys = [_make_key(u) for u in users]
    fuzzy_keys = get_close_matches(search_term, keys, n=20, cutoff=0.4)
    search_lower = search_term.lower()
    substring_keys = [k for k in keys if search_lower in k.lower() and k not in fuzzy_keys]
    matched_keys = set(fuzzy_keys + substring_keys)
    matched = [_normalize_user(u) for u, k in zip(users, keys) if k in matched_keys]

    logger.info(f"[caller={caller}] Fuzzy matches: {len(matched)}")
    return {"users": matched, "count": len(matched),
            "search_term": search_term, "search_type": "fuzzy"}


@mcp.tool()
def get_user_groups(user_id: str, ctx: Context | None = None) -> dict:
    """Get all groups a user belongs to."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting groups for: {user_id}")
    client = get_client()
    groups = client.get(f"/api/v1/users/{user_id}/groups")
    return {
        "groups": [{"id": g.get("id"), "name": g.get("profile", {}).get("name"),
                    "description": g.get("profile", {}).get("description")} for g in groups],
        "count": len(groups),
        "user_id": user_id
    }


@mcp.tool()
def check_permissions(ctx: Context | None = None) -> dict:
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


@mcp.tool()
def search_users_by_attribute(
    attribute: str,
    value: str,
    limit: int = 200,
    ctx: Context | None = None
) -> str:
    """Search users by any profile attribute (division, department, title, location, etc.)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Searching users with {attribute}={value}")
    try:
        client = get_client()
        search_filter = f'profile.{attribute} eq "{value}"'
        response = client.get("/api/v1/users", params={"search": search_filter, "limit": limit})
        if not response:
            return f'No users found with {attribute}="{value}"'
        result = f'Found {len(response)} user(s) with {attribute}="{value}":\n\n'
        for u in response:
            p = u.get("profile", {})
            result += (f"• {p.get('firstName')} {p.get('lastName')} ({p.get('email')})"
                      f"\n  Status: {u.get('status')}, ID: {u.get('id')}"
                      f"\n  {attribute}: {p.get(attribute)}\n\n")
        return result
    except Exception as e:
        return f"❌ Error searching by attribute: {str(e)}"