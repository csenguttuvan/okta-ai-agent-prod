from typing import Optional, List
from loguru import logger
from mcp.server.fastmcp import Context
from difflib import get_close_matches
import json

from okta_mcp_server.context import get_caller_email, get_caller_groups
from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client

from okta_mcp_server.utils.validation import (
    validate_okta_id,
    validate_boolean,
    validate_and_raise,
    ValidationError,
)


# ---------------------------
# Helpers
# ---------------------------

def _normalize_group(g: dict) -> dict:
    """Compact, clean group — no _links, no logo bloat."""
    p = g.get("profile") or {}
    return {
        "id": g.get("id"),
        "name": (p.get("name") or "").strip(),
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


# ---------------------------
# Tools
# ---------------------------

@mcp.tool()
def search_groups_fuzzy(
    search_term: str,
    limit: int = 200,
    ctx: Context | None = None
) -> dict:
    """Fuzzy search Okta groups by name (handles typos, partial names, case differences).

    Examples:
    - "outreach users"  → matches "Outreach - Users"
    - "corpit"          → matches "Corp IT", "corp-it"
    - "disciplew dev"   → matches "Disciples-dev"
    """
    caller = get_caller_email()

    if search_term in ("null", None):
        search_term = ""

    logger.info(f"[caller={caller}] Fuzzy searching groups: {search_term!r}")

    client = get_client()

    def normalize(s: str) -> str:
        return s.lower().replace("-", " ").replace("_", " ").replace("  ", " ").strip()

    # Strategy 1: Fast q= search using first meaningful word
    if search_term:
        try:
            first_word = normalize(search_term).split()[0]
            if len(first_word) >= 3:
                quick = client.get("/api/v1/groups", params={"q": first_word, "limit": 50})
                if quick:
                    term_norm = normalize(search_term)
                    term_parts = [p for p in term_norm.split() if len(p) > 2]

                    # Try strict all-parts match first
                    strict = [g for g in quick
                              if all(p in normalize((g.get("profile") or {}).get("name", ""))
                                     for p in term_parts)]
                    if strict:
                        result = [_normalize_group(g) for g in strict]
                        logger.info(f"[caller={caller}] q= strict match: {len(result)}")
                        return {
                            "groups": result,
                            "count": len(result),
                            "search_term": search_term,
                            "matched_names": [g["name"] for g in result],
                            "search_type": "q_strict"
                        }

                    # Fall back to returning all q= results normalized
                    result = [_normalize_group(g) for g in quick]
                    logger.info(f"[caller={caller}] q= prefix: {len(result)}")
                    return {
                        "groups": result,
                        "count": len(result),
                        "search_term": search_term,
                        "matched_names": [g["name"] for g in result],
                        "search_type": "q_prefix"
                    }
        except Exception as e:
            logger.warning(f"[caller={caller}] q= search failed, falling back: {e}")

    # Strategy 2: Full fuzzy scan
    try:
        all_groups = client.get("/api/v1/groups", params={"limit": limit})
    except Exception as e:
        return {"groups": [], "count": 0, "error": str(e), "search_term": search_term}

    if not search_term:
        normalized = [_normalize_group(g) for g in all_groups]
        return {
            "groups": normalized,
            "count": len(normalized),
            "search_term": "",
            "matched_names": [g["name"] for g in normalized],
            "search_type": "all"
        }

    term_norm = normalize(search_term)
    term_parts = [p for p in term_norm.split() if len(p) > 2]

    matched = []
    seen_ids = set()

    for g in all_groups:
        gid = g.get("id")
        if gid in seen_ids:
            continue
        raw_name = (g.get("profile") or {}).get("name", "").strip()
        name_norm = normalize(raw_name)

        # 1. Exact normalized match
        if term_norm == name_norm:
            matched.insert(0, _normalize_group(g))
            seen_ids.add(gid)
            continue

        # 2. Normalized substring
        if term_norm in name_norm:
            matched.append(_normalize_group(g))
            seen_ids.add(gid)
            continue

        # 3. All term parts present in name
        if term_parts and all(p in name_norm for p in term_parts):
            matched.append(_normalize_group(g))
            seen_ids.add(gid)
            continue

        # 4. Remove all spaces/dashes for "corpit" → "corp it" style
        term_squash = term_norm.replace(" ", "")
        name_squash = name_norm.replace(" ", "")
        if term_squash in name_squash or name_squash in term_squash:
            matched.append(_normalize_group(g))
            seen_ids.add(gid)
            continue

        # 5. Difflib fuzzy
        close = get_close_matches(term_norm, [name_norm], n=1, cutoff=0.35)
        if close:
            matched.append(_normalize_group(g))
            seen_ids.add(gid)

    matched = matched[:20]
    logger.info(f"[caller={caller}] Fuzzy scan: {len(matched)} matches for {search_term!r}")

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
    except PermissionError:
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
        return {"users": normalized, "count": len(normalized), "group_id": group_id}
    except PermissionError:
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing group users: {e}")
        raise


@mcp.tool()
def create_group(
    name: str,
    description: Optional[str] = None,
    ctx: Context | None = None
) -> dict:
    """Create a new Okta group (requires okta.groups.manage scope)."""
    caller = get_caller_email()

    if description in ("null", None, ""):
        description = ""

    if not name or not name.strip():
        raise ValueError("Group name cannot be empty")

    logger.info(f"[caller={caller}] Creating group: {name!r}")

    try:
        client = get_client()
        body = {"profile": {"name": name.strip(), "description": description}}
        group = client.post("/api/v1/groups", data=body)
        result = _normalize_group(group)
        logger.info(f"[caller={caller}] ✅ Created group: {result['id']}")
        return result
    except PermissionError:
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
    """Update a group's name or description (requires okta.groups.manage scope)."""
    caller = get_caller_email()

    if name == "null": name = None
    if description == "null": description = None

    if name is None and description is None:
        return {"success": False, "error": "Provide at least one of: name, description"}

    logger.info(f"[caller={caller}] Updating group {group_id}")

    try:
        client = get_client()
        current = client.get(f"/api/v1/groups/{group_id}")
        p = current.get("profile") or {}
        old_name = p.get("name", "")
        old_desc = p.get("description", "")

        profile = {
            "name": name.strip() if name is not None else old_name,
            "description": description if description is not None else old_desc,
        }

        updated = client.put(f"/api/v1/groups/{group_id}", data={"profile": profile})
        result = _normalize_group(updated)

        logger.info(f"AUDIT: Group update | caller={caller} | id={group_id} | "
                   f"name_changed={name is not None} | desc_changed={description is not None}")

        return {
            "success": True,
            "group": result,
            "changes": {
                "name": {"old": old_name, "new": profile["name"]} if name is not None else None,
                "description": {"old": old_desc, "new": profile["description"]} if description is not None else None,
            },
            "updated_by": caller
        }
    except PermissionError:
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error updating group: {e}")
        raise


@mcp.tool()
def delete_group(
    group_id: str,
    confirm_deletion: bool = False,
    ctx: Context = None
) -> str:
    """Delete an Okta group (requires okta.groups.manage scope).

    ⚠️ DESTRUCTIVE — removes group and all memberships. Set confirm_deletion=True.
    Built-in groups (e.g. Everyone) cannot be deleted.
    """
    caller = get_caller_email()

    is_valid, error = validate_okta_id(group_id, "group", required=True)
    if not is_valid:
        return f"❌ {error}"

    is_valid, error = validate_boolean(confirm_deletion, required=True, field_name="confirm_deletion")
    if not is_valid:
        return f"❌ {error}"

    if not confirm_deletion:
        return "❌ Set confirm_deletion=True to proceed. ⚠️ This permanently removes the group."

    logger.warning(f"[{caller}] ⚠️ Deleting group: {group_id}")

    try:
        client = get_client()
        group = client.get(f"/api/v1/groups/{group_id}")
        name = (group.get("profile") or {}).get("name", group_id).strip()
        gtype = group.get("type")

        if gtype == "BUILT_IN":
            return f"❌ Cannot delete built-in group '{name}'. Okta built-in groups are protected."

        logger.error(f"AUDIT: Group deletion | caller={caller} | group={name} | id={group_id} | PERMANENT")
        client.delete(f"/api/v1/groups/{group_id}")

        return f"⚠️ DELETED group '{name}' (ID: {group_id}) permanently. Cannot be undone."

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error deleting group: {str(e)}"


@mcp.tool()
def preview_group_deletion_impact(
    group_id: str,
    ctx: Context | None = None
) -> dict:
    """Preview the impact of deleting a group — member count and app assignments."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Previewing deletion impact: {group_id}")

    try:
        client = get_client()
        group = client.get(f"/api/v1/groups/{group_id}")
        name = (group.get("profile") or {}).get("name", group_id).strip()
        desc = (group.get("profile") or {}).get("description", "").strip()

        members = client.get(f"/api/v1/groups/{group_id}/users", params={"limit": 200})
        apps = client.get(f"/api/v1/groups/{group_id}/apps", params={"limit": 50})

        sample_members = [
            {"id": u.get("id"),
             "email": (u.get("profile") or {}).get("email"),
             "name": f"{(u.get('profile') or {}).get('firstName','')} {(u.get('profile') or {}).get('lastName','')}".strip()}
            for u in members[:10]
        ]
        app_list = [
            {"id": a.get("id"), "label": a.get("label"), "status": a.get("status")}
            for a in apps
        ]

        return {
            "group_id": group_id,
            "group_name": name,
            "group_description": desc,
            "total_members": len(members),
            "sample_members": sample_members,
            "members_note": f"Showing 10 of {len(members)}" if len(members) > 10 else "All members shown",
            "app_count": len(apps),
            "apps": app_list,
            "warnings": [
                f"⚠️ {len(members)} user(s) will lose this group membership",
                f"⚠️ {len(apps)} app assignment(s) will be removed",
                "⚠️ This cannot be undone",
            ],
            "next_step": f"delete_group(group_id='{group_id}', confirm_deletion=True)"
        }
    except Exception as e:
        return {"error": str(e), "group_id": group_id}


@mcp.tool()
def add_user_to_group(
    group_id: str,
    user_id: str,
    ctx: Context | None = None
) -> str:
    """Add a single user to a group (requires okta.groups.manage scope).
    For multiple users use add_users_to_group() instead.
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Adding user {user_id} to group {group_id}")

    try:
        client = get_client()

        # Validate user is ACTIVE
        user = client.get(f"/api/v1/users/{user_id}")
        status = user.get("status")
        email = (user.get("profile") or {}).get("email", user_id)

        if status != "ACTIVE":
            return (f"❌ Cannot add {email} to group — status is '{status}'. "
                    f"Only ACTIVE users can be added to groups.")

        client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
        return f"✅ User {email} added to group {group_id} successfully."

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        err = str(e)
        if "409" in err or "already" in err.lower():
            return f"ℹ️ User {user_id} is already a member of group {group_id}."
        return f"❌ Error adding user to group: {err}"


@mcp.tool()
def add_users_to_group(
    group_id: str,
    user_ids: list[str] | str,
    ctx: Context | None = None
) -> dict:
    """Add multiple users to a group at once (requires okta.groups.manage scope).
    Preferred over calling add_user_to_group in a loop.
    Only ACTIVE users are added; others are skipped with a reason.
    """
    caller = get_caller_email()

    # Handle JSON string input from LLMs
    if isinstance(user_ids, str):
        try:
            user_ids = json.loads(user_ids)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid user_ids format: {e}"}

    if not isinstance(user_ids, list):
        return {"success": False, "error": f"user_ids must be a list, got {type(user_ids).__name__}"}

    logger.info(f"[caller={caller}] Batch adding {len(user_ids)} users to group {group_id}")

    client = get_client()
    results, failed, skipped = [], [], []

    for user_id in user_ids:
        try:
            user = client.get(f"/api/v1/users/{user_id}")
            status = user.get("status")
            email = (user.get("profile") or {}).get("email", user_id)

            if status != "ACTIVE":
                skipped.append({"user_id": user_id, "email": email, "status": status,
                                 "reason": f"Status is '{status}', only ACTIVE allowed"})
                continue

            client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
            results.append({"user_id": user_id, "email": email, "status": "added"})

        except Exception as e:
            err = str(e)
            if "409" in err or "already" in err.lower():
                results.append({"user_id": user_id, "status": "already_member"})
            else:
                failed.append({"user_id": user_id, "error": err})

    return {
        "success": True,
        "total": len(user_ids),
        "added": len([r for r in results if r.get("status") == "added"]),
        "already_members": len([r for r in results if r.get("status") == "already_member"]),
        "skipped_inactive": len(skipped),
        "failed": len(failed),
        "results": results,
        "skipped_users": skipped or None,
        "failures": failed or None,
        "message": f"Added {len([r for r in results if r.get('status') == 'added'])} users. "
                   f"Skipped {len(skipped)} inactive."
    }


@mcp.tool()
def remove_user_from_group(
    group_id: str,
    user_id: str,
    ctx: Context = None
) -> str:
    """Remove a user from a group (requires okta.groups.manage scope)."""
    caller = get_caller_email()

    is_valid, error = validate_okta_id(group_id, "group", required=True)
    if not is_valid:
        return f"❌ {error}"

    is_valid, error = validate_okta_id(user_id, "user", required=True)
    if not is_valid:
        return f"❌ {error}"

    logger.info(f"[{caller}] Removing user {user_id} from group {group_id}")

    try:
        client = get_client()
        group = client.get(f"/api/v1/groups/{group_id}")
        user = client.get(f"/api/v1/users/{user_id}")
        group_name = (group.get("profile") or {}).get("name", group_id).strip()
        user_email = (user.get("profile") or {}).get("email", user_id)

        client.delete(f"/api/v1/groups/{group_id}/users/{user_id}")

        logger.warning(f"AUDIT: Group membership removal | caller={caller} | "
                      f"user={user_email} | group={group_name}")

        return f"✅ {user_email} removed from group '{group_name}' successfully."

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        err = str(e)
        if "404" in err or "not found" in err.lower():
            return f"ℹ️ User {user_id} is not a member of group {group_id}."
        return f"❌ Error removing user from group: {err}"