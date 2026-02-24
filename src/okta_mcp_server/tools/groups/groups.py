from typing import Optional, List
from loguru import logger
from mcp.server.fastmcp import Context
from difflib import get_close_matches

from okta_mcp_server.context import get_caller_email, get_caller_groups
from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client


# ---------------------------
# Helpers
# ---------------------------

def _normalize_group(g: dict) -> dict:
    """Return a compact, clean group representation — no _links, no logo bloat."""
    p = g.get("profile") or {}
    return {
        "id": g.get("id"),
        "name": (p.get("name") or "").strip(),          # strip leading \n
        "description": (p.get("description") or "").strip(),
        "type": g.get("type"),
    }


def _normalize_user_compact(u: dict) -> dict:
    p = u.get("profile") or {}
    return {
        "id": u.get("id"),
        "email": p.get("email"),
        "first_name": p.get("firstName"),
        "last_name": p.get("lastName"),
        "status": u.get("status"),
    }


def _format_groups(groups: list) -> str:
    if not groups:
        return "No groups found."
    lines = [f"Found {len(groups)} group(s):\n"]
    for g in groups:
        n = _normalize_group(g) if "_links" in g else g
        desc = f"\n  Description: {n['description']}" if n.get("description") else ""
        lines.append(f"• {n['name']} (ID: {n['id']}, Type: {n.get('type', 'N/A')}){desc}")
    return "\n".join(lines)


# ---------------------------
# Tools
# ---------------------------

@mcp.tool()
def list_groups(
    limit: int = 100,
    query: Optional[str] = None,
    ctx: Context | None = None
) -> str:
    """List Okta groups. Use query for name prefix search."""
    caller = get_caller_email()

    if query in ("null", "", None):
        query = None

    try:
        limit_int = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        limit_int = 100

    logger.info(f"[caller={caller}] listing groups query={query!r}, limit={limit_int}")

    try:
        client = get_client()
        params = {"limit": limit_int}
        if query:
            params["q"] = query

        groups = client.get("/api/v1/groups", params=params)
        logger.info(f"[caller={caller}] Found {len(groups)} groups")
        return _format_groups(groups)

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
    """Fuzzy search Okta groups by name (handles typos, partial names, case differences).

    Examples:
    - "outreach users"  → matches "Outreach - Users"
    - "disciplew dev"   → matches "Disciples-dev"
    - "sso admin"       → matches "Outreach - SSO - Admin"
    """
    caller = get_caller_email()

    if search_term in ("null", None):
        search_term = ""

    logger.info(f"[caller={caller}] Fuzzy searching groups: {search_term!r}")

    client = get_client()

    # Strategy 1: Fast q= search using first meaningful word
    if search_term:
        try:
            # Use the longest word before any dash/hyphen as the q= seed
            first_word = search_term.replace("-", " ").replace("–", " ").strip().split()[0]
            if len(first_word) >= 3:
                quick = client.get("/api/v1/groups", params={"q": first_word, "limit": 50})
                if quick:
                    # Client-side filter: normalize both sides for comparison
                    term_norm = search_term.lower().replace("-", " ").replace("_", " ").replace("–", " ")
                    # Remove common filler words for matching
                    term_parts = [p for p in term_norm.split() if len(p) > 2]

                    filtered = []
                    for g in quick:
                        name = (g.get("profile") or {}).get("name", "").strip()
                        name_norm = name.lower().replace("-", " ").replace("_", " ")
                        # Match if all meaningful parts of search_term appear in name
                        if all(part in name_norm for part in term_parts):
                            filtered.append(_normalize_group(g))

                    if filtered:
                        logger.info(f"[caller={caller}] q= search found {len(filtered)} matches")
                        return {
                            "groups": filtered,
                            "count": len(filtered),
                            "search_term": search_term,
                            "matched_names": [g["name"] for g in filtered],
                            "search_type": "q_filtered"
                        }

                    # If all-parts filter too strict, return all q= results
                    normalized_quick = [_normalize_group(g) for g in quick]
                    logger.info(f"[caller={caller}] q= prefix returned {len(normalized_quick)}")
                    return {
                        "groups": normalized_quick,
                        "count": len(normalized_quick),
                        "search_term": search_term,
                        "matched_names": [g["name"] for g in normalized_quick],
                        "search_type": "q_prefix"
                    }
        except Exception as e:
            logger.warning(f"[caller={caller}] q= search failed, falling back: {e}")

    # Strategy 2: Full fuzzy scan
    try:
        all_groups = client.get("/api/v1/groups", params={"limit": limit})
    except Exception as e:
        return {"groups": [], "count": 0, "error": str(e)}

    if not search_term:
        normalized = [_normalize_group(g) for g in all_groups]
        return {
            "groups": normalized,
            "count": len(normalized),
            "search_term": "",
            "matched_names": [g["name"] for g in normalized],
            "search_type": "all"
        }

    # Normalize names for comparison (strip \n, lower, dashes→spaces)
    names_raw = [(g, (g.get("profile") or {}).get("name", "").strip()) for g in all_groups]
    names_norm = [(g, raw, raw.lower().replace("-", " ").replace("_", " ")) for g, raw in names_raw]

    term_norm = search_term.lower().replace("-", " ").replace("_", " ")
    term_parts = [p for p in term_norm.split() if len(p) > 2]

    matched = []
    for g, raw, norm in names_norm:
        # Substring check
        if term_norm in norm or any(part in norm for part in term_parts):
            matched.append(_normalize_group(g))
            continue
        # Fuzzy check
        close = get_close_matches(term_norm, [norm], n=1, cutoff=0.35)
        if close:
            matched.append(_normalize_group(g))

    matched = matched[:20]
    logger.info(f"[caller={caller}] Fuzzy scan found {len(matched)} matches")

    return {
        "groups": matched,
        "count": len(matched),
        "search_term": search_term,
        "matched_names": [g["name"] for g in matched],
        "search_type": "fuzzy"
    }


@mcp.tool()
def get_group(group_id: str, ctx: Context | None = None) -> dict:
    """Get details for a specific group by ID."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting group: {group_id}")

    try:
        client = get_client()
        group = client.get(f"/api/v1/groups/{group_id}")
        return _normalize_group(group)
    except PermissionError as e:
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error getting group: {e}")
        raise


@mcp.tool()
def list_group_users(
    group_id: str,
    limit: int = 100,
    ctx: Context | None = None
) -> dict:
    """List members of a group."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing users in group: {group_id}")

    try:
        client = get_client()
        users = client.get(f"/api/v1/groups/{group_id}/users", params={"limit": limit})
        normalized = [_normalize_user_compact(u) for u in users]
        logger.info(f"[caller={caller}] Found {len(normalized)} users in group")
        return {
            "users": normalized,
            "count": len(normalized),
            "group_id": group_id
        }
    except PermissionError as e:
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing group users: {e}")
        raise


@mcp.tool()
def create_group(
    name: str,
    description: str = "",
    ctx: Context | None = None
) -> dict:
    """Create a new Okta group (requires groups.manage scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Creating group: {name!r}")

    if not name or not name.strip():
        raise ValueError("Group name cannot be empty")

    try:
        client = get_client()
        body = {"profile": {"name": name.strip(), "description": description.strip()}}
        group = client.post("/api/v1/groups", data=body)
        result = _normalize_group(group)
        logger.info(f"[caller={caller}] ✅ Created group: {result['id']}")
        return result
    except PermissionError as e:
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error creating group: {e}")
        raise


@mcp.tool()
def update_group(
    group_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    ctx: Context | None = None
) -> dict:
    """Update a group's name or description (requires groups.manage scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Updating group: {group_id}")

    if not name and description is None:
        raise ValueError("Provide at least one of: name, description")

    try:
        client = get_client()
        current = client.get(f"/api/v1/groups/{group_id}")
        profile = current.get("profile") or {}

        if name:
            profile["name"] = name.strip()
        if description is not None:
            profile["description"] = description.strip()

        group = client.put(f"/api/v1/groups/{group_id}", data={"profile": profile})
        result = _normalize_group(group)
        logger.info(f"[caller={caller}] ✅ Updated group: {group_id}")
        return result
    except PermissionError as e:
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error updating group: {e}")
        raise


@mcp.tool()
def delete_group(
    group_id: str,
    confirm_deletion: bool = False,
    ctx: Context | None = None
) -> str:
    """Delete an Okta group (requires groups.manage scope).

    ⚠️ DESTRUCTIVE — removes the group and all memberships. Set confirm_deletion=True.
    """
    caller = get_caller_email()

    if not confirm_deletion:
        return "❌ Set confirm_deletion=True to proceed. ⚠️ This permanently removes the group."

    logger.warning(f"[caller={caller}] ⚠️ Deleting group: {group_id}")

    try:
        client = get_client()
        group = client.get(f"/api/v1/groups/{group_id}")
        name = (group.get("profile") or {}).get("name", group_id).strip()

        logger.warning(f"AUDIT: Group deletion | caller={caller} | group={name} | id={group_id}")
        client.delete(f"/api/v1/groups/{group_id}")

        return f"✅ Group '{name}' (ID: {group_id}) deleted successfully."
    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error deleting group: {str(e)}"


@mcp.tool()
def add_user_to_group(
    group_id: str,
    user_id: str,
    ctx: Context | None = None
) -> str:
    """Add a single user to a group (requires groups.manage scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Adding user {user_id} to group {group_id}")

    try:
        client = get_client()
        client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
        return f"✅ User {user_id} added to group {group_id} successfully."
    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        err = str(e)
        if "409" in err or "already" in err.lower():
            return f"ℹ️ User {user_id} is already a member of group {group_id}."
        return f"❌ Error adding user to group: {err}"


@mcp.tool()
def remove_user_from_group(
    group_id: str,
    user_id: str,
    ctx: Context | None = None
) -> str:
    """Remove a single user from a group (requires groups.manage scope)."""
    caller = get_caller_email()
    logger.warning(f"[caller={caller}] Removing user {user_id} from group {group_id}")

    try:
        client = get_client()
        client.delete(f"/api/v1/groups/{group_id}/users/{user_id}")
        logger.warning(f"AUDIT: User removed from group | caller={caller} | user={user_id} | group={group_id}")
        return f"✅ User {user_id} removed from group {group_id} successfully."
    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        err = str(e)
        if "404" in err or "not found" in err.lower():
            return f"ℹ️ User {user_id} is not a member of group {group_id}."
        return f"❌ Error removing user from group: {err}"


@mcp.tool()
def preview_group_deletion_impact(
    group_id: str,
    ctx: Context | None = None
) -> dict:
    """Preview the impact of deleting a group — shows member count and app assignments."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Previewing deletion impact for group: {group_id}")

    try:
        client = get_client()
        group = client.get(f"/api/v1/groups/{group_id}")
        name = (group.get("profile") or {}).get("name", group_id).strip()

        users = client.get(f"/api/v1/groups/{group_id}/users", params={"limit": 200})
        apps = client.get(f"/api/v1/groups/{group_id}/apps", params={"limit": 50})

        return {
            "group_id": group_id,
            "group_name": name,
            "member_count": len(users),
            "app_count": len(apps),
            "apps": [
                {"id": a.get("id"), "label": a.get("label"), "status": a.get("status")}
                for a in apps
            ],
            "warning": (
                f"Deleting this group will remove {len(users)} members "
                f"and unlink {len(apps)} application assignment(s)."
            )
        }
    except Exception as e:
        return {"error": str(e), "group_id": group_id}