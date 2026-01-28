from typing import Optional, List
from loguru import logger
from mcp.server.fastmcp import Context
from difflib import get_close_matches
import json

from okta_mcp_server.context import get_caller_email, get_caller_groups
from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client


@mcp.tool()
def search_groups_fuzzy(
    search_term: str,
    limit: int = 200,
    ctx: Context | None = None
) -> dict:
    """Fuzzy search Okta groups by name (handles typos and partial names).
    
    This is more forgiving than list_groups:
    - "corpit" matches "corp it", "corp it7", "corp-it"
    - "disciplew dev" can match "Disciples-dev"
    - Case-insensitive
    - Also tries substring matches with space/hyphen normalization
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
        
        # Normalize function: remove spaces, hyphens, underscores for comparison
        def normalize(s):
            return s.lower().replace(" ", "").replace("-", "").replace("_", "")
        
        search_normalized = normalize(search_term)
        search_lower = search_term.lower()
        
        matched_names = []
        
        # 1. Exact match (case-insensitive)
        exact_matches = [name for name in names if name.lower() == search_lower]
        matched_names.extend(exact_matches)
        
        # 2. Normalized substring match (handles "corpit" matching "corp it7")
        normalized_matches = [
            name for name in names 
            if search_normalized in normalize(name) 
            and name not in matched_names
        ]
        matched_names.extend(normalized_matches)
        
        # 3. Regular substring match (case-insensitive)
        substring_matches = [
            name for name in names 
            if search_lower in name.lower() 
            and name not in matched_names
        ]
        matched_names.extend(substring_matches)
        
        # 4. Fuzzy matches (for typos)
        fuzzy_matches = get_close_matches(
            search_term, 
            [n for n in names if n not in matched_names], 
            n=10, 
            cutoff=0.4
        )
        matched_names.extend(fuzzy_matches)
        
        # Limit to top 10 results
        matched_names = matched_names[:10]
        matched = [g for g in groups if g["profile"]["name"] in matched_names]
        
        logger.info(
            f"[caller={caller}] Fuzzy group search found {len(matched)} matches for: {search_term} | "
            f"exact={len(exact_matches)}, normalized={len(normalized_matches)}, "
            f"substring={len(substring_matches)}, fuzzy={len(fuzzy_matches)}"
        )
        
        return {
            "groups": matched,
            "count": len(matched),
            "search_term": search_term,
            "matched_names": matched_names,
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


@mcp.tool()
def create_group(
    name: str,
    description: Optional[str] = None,
    ctx: Context | None = None
) -> dict:
    """Create a new Okta group (requires okta.groups.manage scope)."""
    caller = get_caller_email()

    if description in ("null", None):
        description = None

    logger.info(f"[caller={caller}] Creating group: {name}")

    client = get_client()
    profile = {"name": name}
    if description:
        profile["description"] = description

    try:
        group = client.post("/api/v1/groups", data={"profile": profile})
        logger.info(f"[caller={caller}] Created group: {group.get('id')}")
        return group

    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error creating group: {str(e)}")
        raise


@mcp.tool()
def delete_group(
    group_id: str,
    confirm_deletion: bool = False,
    ctx: Context = None
) -> dict:
    """Delete an Okta group (requires okta.groups.manage scope).
    
    ⚠️ DESTRUCTIVE OPERATION - Cannot be undone.
    
    Args:
        group_id: The Okta group ID (format: 00g1234567890123456)
        confirm_deletion: Must be True to proceed (prevents accidental deletion)
        ctx: Optional context
        
    Returns:
        Dict with operation status
        
    Note:
        - Built-in groups (like "Everyone") cannot be deleted
        - All group memberships will be removed
        - Group rules and app assignments will be affected
    """
    caller = get_caller_email()
    
    try:
        # ✅ VALIDATION
        is_valid, error = validate_okta_id(group_id, "group", required=True)
        validate_and_raise(is_valid, error, f"[{caller}]")
        
        is_valid, error = validate_boolean(confirm_deletion, required=True, field_name="confirm_deletion")
        validate_and_raise(is_valid, error, f"[{caller}]")
        
        if not confirm_deletion:
            logger.warning(f"[{caller}] Deletion not confirmed for group {group_id}")
            return {
                "success": False,
                "error": "Deletion not confirmed",
                "message": "Set confirm_deletion=True to proceed with group deletion",
                "group_id": group_id,
                "warning": "⚠️ This is a permanent operation that CANNOT be undone"
            }
        
        logger.warning(f"[{caller}] ⚠️ DESTRUCTIVE: Attempting to delete group {group_id}")
        client = get_client()
        
        # Get group info before deletion
        group = client.get(f"/api/v1/groups/{group_id}")
        group_name = group.get("profile", {}).get("name")
        group_type = group.get("type")
        
        # Check if it's a built-in group
        if group_type == "BUILT_IN":
            logger.error(f"[{caller}] Cannot delete built-in group: {group_name}")
            return {
                "success": False,
                "error": "Cannot delete built-in groups",
                "group_id": group_id,
                "group_name": group_name,
                "group_type": group_type,
                "message": "Built-in groups like 'Everyone' are protected by Okta"
            }
        
        # Enhanced audit log
        logger.error(
            f"AUDIT: Group deletion | "
            f"caller={caller} | "
            f"target_group={group_name} | "
            f"target_group_id={group_id} | "
            f"WARNING: PERMANENT_DELETION"
        )
        
        # Delete group
        client.delete(f"/api/v1/groups/{group_id}")
        
        logger.error(f"[{caller}] ⚠️ DELETED group: {group_name} (PERMANENT)")
        
        return {
            "success": True,
            "message": f"Group '{group_name}' deleted permanently",
            "group_id": group_id,
            "group_name": group_name,
            "deleted_by": caller,
            "warning": "This operation is permanent and cannot be undone"
        }
        
    except ValidationError as e:
        logger.error(f"[{caller}] Validation error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "group_id": group_id
        }
    except PermissionError as e:
        logger.error(f"[{caller}] ❌ Permission denied: {str(e)}")
        return {
            "success": False,
            "error": f"Permission denied: {str(e)}",
            "group_id": group_id
        }
    except Exception as e:
        logger.error(f"[{caller}] ❌ Error deleting group: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "group_id": group_id
        }

@mcp.tool()
def preview_group_deletion_impact(
    group_id: str,
    ctx: Context | None = None
) -> dict:
    """Preview the impact of deleting a group before deletion.
    
    Shows affected members and application assignments to help make informed decisions.
    
    Args:
        group_id: The Okta group ID
        ctx: Optional context
        
    Returns:
        Dict with impact analysis including members and app assignments
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Previewing deletion impact for group {group_id}")
    
    client = get_client()
    
    try:
        # Get group details
        group = client.get(f"/api/v1/groups/{group_id}")
        group_name = group.get("profile", {}).get("name")
        group_description = group.get("profile", {}).get("description")
        
        # Get members
        members = client.get(f"/api/v1/groups/{group_id}/users", params={"limit": 200})
        member_list = [
            {
                "id": m.get("id"),
                "email": m.get("profile", {}).get("email"),
                "name": f"{m.get('profile', {}).get('firstName', '')} {m.get('profile', {}).get('lastName', '')}".strip()
            }
            for m in members[:10]  # Show first 10
        ]
        
        # Try to get app assignments (note: requires listing all apps and filtering)
        # This is a simplified version - full implementation would check all apps
        logger.info(f"[caller={caller}] Group has {len(members)} members")
        
        impact_summary = {
            "group_id": group_id,
            "group_name": group_name,
            "group_description": group_description,
            "impact": {
                "total_members": len(members),
                "members_shown": member_list,
                "note": f"Showing first 10 of {len(members)} members" if len(members) > 10 else "All members shown"
            },
            "warnings": [
                f"⚠️ {len(members)} users will be removed from this group",
                "⚠️ All application assignments for this group will be deleted",
                "⚠️ This operation cannot be undone"
            ],
            "recommendation": "Review all members and app assignments carefully before deletion",
            "next_steps": f"To proceed, call delete_group(group_id='{group_id}', confirm_deletion=True)"
        }
        
        return impact_summary
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error previewing impact: {str(e)}")
        raise



@mcp.tool()
def add_users_to_group(
    group_id: str,
    user_ids: list[str] | str,  # ✅ Accept both list and string
    ctx: Context | None = None
) -> dict:
    """🚀 Add multiple users to a group in a single operation (requires okta.groups.manage scope).
    
    This is the MOST EFFICIENT way to add multiple users to a group. Use this instead of 
    calling add_user_to_group multiple times.
    
    Args:
        group_id: The Okta group ID
        user_ids: List of Okta user IDs to add (can be Python list or JSON array string)
        ctx: Optional context
        
    Returns:
        Dict containing:
            - success: Operation status
            - total: Total users attempted
            - added: Number successfully added
            - skipped_inactive: Number of non-ACTIVE users skipped
            - failed: Number of failures
            - results: List of successfully added users
            - skipped_users: List of skipped users with reasons
            - failures: List of failed operations
            
    Note:
        - Only ACTIVE users can be added to groups
        - Users with status PASSWORD_EXPIRED, PROVISIONED, etc. will be skipped
        - This operation is atomic per user (one failure doesn't stop others)
    """
    caller = get_caller_email()
    
    # ✅ Handle JSON string input from LLMs
    if isinstance(user_ids, str):
        try:
            user_ids = json.loads(user_ids)
            logger.info(f"[caller={caller}] Parsed user_ids from JSON string")
        except json.JSONDecodeError as e:
            logger.error(f"[caller={caller}] Invalid user_ids JSON: {e}")
            return {
                "success": False,
                "error": f"Invalid user_ids format: expected list or JSON array string",
                "provided_value": user_ids[:100]
            }
    
    if not isinstance(user_ids, list):
        return {
            "success": False,
            "error": f"user_ids must be a list, got: {type(user_ids).__name__}"
        }
    
    logger.info(f"[caller={caller}] Batch adding {len(user_ids)} users to group: {group_id}")

    client = get_client()
    
    results = []
    failed = []
    skipped_inactive = []
    
    for user_id in user_ids:
        try:
            # Get user status first
            user = client.get(f"/api/v1/users/{user_id}")
            
            if user.get("status") != "ACTIVE":
                skipped_inactive.append({
                    "user_id": user_id,
                    "status": user.get("status"),
                    "email": user.get("profile", {}).get("email"),
                    "reason": f"User {user.get('profile', {}).get('email')} has status '{user.get('status')}'. Only ACTIVE users can be modified."
                })
                logger.warning(f"[caller={caller}] ⏭️ Skipped inactive user {user_id} (status: {user.get('status')})")
                continue
            
            # Add user to group
            client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
            
            results.append({
                "user_id": user_id,
                "status": "added"
            })
            logger.info(f"[caller={caller}] ✅ Added user {user_id} to group")
            
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
        "skipped_inactive": len(skipped_inactive),
        "failed": len(failed),
        "results": results,
        "skipped_users": skipped_inactive if skipped_inactive else None,
        "failures": failed if failed else None,
        "message": f"Added {len(results)} users. Skipped {len(skipped_inactive)} inactive users."
    }



@mcp.tool()
def remove_user_from_group(
    group_id: str,
    user_id: str,
    ctx: Context = None
) -> dict:
    """Remove a user from a group (requires okta.groups.manage scope).
    
    ⚠️ This removes the user's group membership and associated permissions.
    
    Args:
        group_id: The Okta group ID (format: 00g1234567890123456)
        user_id: The Okta user ID (format: 00u1234567890123456)
        ctx: Optional context
        
    Returns:
        Dict with operation status
    """
    caller = get_caller_email()
    
    try:
        # ✅ VALIDATION
        is_valid, error = validate_okta_id(group_id, "group", required=True)
        validate_and_raise(is_valid, error, f"[{caller}]")
        
        is_valid, error = validate_okta_id(user_id, "user", required=True)
        validate_and_raise(is_valid, error, f"[{caller}]")
        
        logger.info(f"[{caller}] Removing user {user_id} from group {group_id}")
        client = get_client()
        
        # Get names for better logging
        group = client.get(f"/api/v1/groups/{group_id}")
        user = client.get(f"/api/v1/users/{user_id}")
        group_name = group.get("profile", {}).get("name")
        user_email = user.get("profile", {}).get("email")
        
        # Audit log
        logger.warning(
            f"AUDIT: Group membership removal | "
            f"caller={caller} | "
            f"user={user_email} | "
            f"group={group_name}"
        )
        
        # Remove user from group
        client.delete(f"/api/v1/groups/{group_id}/users/{user_id}")
        
        logger.info(f"[{caller}] User {user_email} removed from group {group_name}")
        
        return {
            "success": True,
            "message": f"User {user_email} removed from group '{group_name}'",
            "group_id": group_id,
            "group_name": group_name,
            "user_id": user_id,
            "user_email": user_email,
            "removed_by": caller
        }
        
    except ValidationError as e:
        logger.error(f"[{caller}] Validation error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "group_id": group_id,
            "user_id": user_id
        }
    except PermissionError as e:
        logger.error(f"[{caller}] ❌ Permission denied: {str(e)}")
        return {
            "success": False,
            "error": f"Permission denied: {str(e)}",
            "group_id": group_id,
            "user_id": user_id
        }
    except Exception as e:
        logger.error(f"[{caller}] ❌ Error removing user from group: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "group_id": group_id,
            "user_id": user_id
        }




@mcp.tool()
def remove_users_from_group(
    group_id: str,
    user_ids: List[str],
    ctx: Context | None = None
) -> dict:
    """Remove multiple users from a group in a single operation.
    
    Only ACTIVE users will be removed. Non-active users will be skipped.
    
    Args:
        group_id: The Okta group ID
        user_ids: List of Okta user IDs to remove from the group
        
    Returns:
        Dictionary with removed count, skipped count, and results
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Batch removing {len(user_ids)} users from group {group_id}")
    
    client = get_client()
    
    # Import validation function
    from okta_mcp_server.tools.users.users_admin import _validate_user_is_active
    
    results = []
    failed = []
    skipped_inactive = []
    
    for user_id in user_ids:
        try:
            # Validate user is ACTIVE
            is_active, error_msg, user = _validate_user_is_active(client, user_id, caller)
            
            if not is_active:
                skipped_inactive.append({
                    "user_id": user_id,
                    "status": user.get("status"),
                    "email": user.get("profile", {}).get("email"),
                    "reason": error_msg
                })
                logger.warning(f"[caller={caller}] ⏭️ Skipped inactive user {user_id} (status: {user.get('status')})")
                continue
            
            client.delete(f"/api/v1/groups/{group_id}/users/{user_id}")
            results.append({"user_id": user_id, "status": "removed"})
            logger.info(f"[caller={caller}] ✅ Removed user {user_id} from group {group_id}")
            logger.info(f"tool=remove_users_from_group group_id={group_id} user_id={user_id} result=success")
            
        except Exception as e:
            failed.append({"user_id": user_id, "error": str(e)})
            logger.error(f"[caller={caller}] ❌ Failed to remove user {user_id}: {str(e)}")
            logger.error(f"tool=remove_users_from_group group_id={group_id} user_id={user_id} result=error error={str(e)}")
    
    return {
        "success": True,
        "total": len(user_ids),
        "removed": len(results),
        "skipped_inactive": len(skipped_inactive),
        "failed": len(failed),
        "results": results,
        "skipped_users": skipped_inactive if skipped_inactive else None,
        "failures": failed if failed else None,
        "message": f"Removed {len(results)} users. Skipped {len(skipped_inactive)} inactive users."
    }



@mcp.tool()
def add_user_to_group(
    group_id: str,
    user_id: str,
    ctx: Context | None = None
) -> dict:
    """Add a single user to a group (requires okta.groups.manage scope).

    This is a convenience wrapper for adding one user. For adding multiple users,
    use add_users_to_group() which is more efficient.

    Args:
        group_id: The Okta group ID
        user_id: The Okta user ID to add
        ctx: Optional context

    Returns:
        Dict with operation status

    Note:
        - Only ACTIVE users can be added to groups
        - Users with other statuses (PROVISIONED, DEACTIVATED, etc.) will be rejected
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Adding user {user_id} to group {group_id}")

    client = get_client()

    try:
        # Import validation function
        from okta_mcp_server.tools.users.users_admin import _validate_user_is_active

        # Validate user is ACTIVE
        is_active, error_msg, user = _validate_user_is_active(client, user_id, caller)

        if not is_active:
            logger.error(f"[caller={caller}] ❌ Cannot add user: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "user_id": user_id,
                "user_status": user.get("status"),
                "message": "Only ACTIVE users can be added to groups"
            }

        # Add user to group
        client.put(f"/api/v1/groups/{group_id}/users/{user_id}")

        user_email = user.get("profile", {}).get("email")
        logger.info(f"[caller={caller}] ✅ Added user {user_email} to group {group_id}")

        return {
            "success": True,
            "message": f"User {user_email} added to group successfully",
            "user_id": user_id,
            "user_email": user_email,
            "group_id": group_id,
            "added_by": caller
        }

    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error adding user to group: {str(e)}")
        raise



@mcp.tool()
def update_group(
    group_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    ctx: Context | None = None
) -> dict:
    """Update an Okta group's name or description (requires okta.groups.manage scope).

    At least one of name or description must be provided to update.

    Args:
        group_id: The Okta group ID
        name: New name for the group (optional)
        description: New description for the group (optional, use empty string to clear)
        ctx: Optional context

    Returns:
        Dict with updated group information

    Example:
        # Update name only
        update_group(group_id="00gxxx", name="New Group Name")

        # Update description only
        update_group(group_id="00gxxx", description="New description")

        # Update both
        update_group(group_id="00gxxx", name="New Name", description="New description")

        # Clear description
        update_group(group_id="00gxxx", description="")
    """
    caller = get_caller_email()

    # Normalize null values
    if name == "null":
        name = None
    if description == "null":
        description = None

    # Validate that at least one field is being updated
    if name is None and description is None:
        return {
            "success": False,
            "error": "At least one of 'name' or 'description' must be provided",
            "message": "No changes requested"
        }

    logger.info(f"[caller={caller}] Updating group {group_id}")

    client = get_client()

    try:
        # Get current group data
        group = client.get(f"/api/v1/groups/{group_id}")
        current_name = group.get("profile", {}).get("name")
        current_description = group.get("profile", {}).get("description", "")

        # Build update payload with only changed fields
        profile = {}

        if name is not None:
            profile["name"] = name
            logger.info(f"[caller={caller}] Changing group name: '{current_name}' → '{name}'")
        else:
            profile["name"] = current_name  # Keep existing name

        if description is not None:
            profile["description"] = description if description else ""
            logger.info(f"[caller={caller}] Changing group description: '{current_description}' → '{description}'")
        else:
            profile["description"] = current_description  # Keep existing description

        # Update group
        updated_group = client.put(
            f"/api/v1/groups/{group_id}",
            data={"profile": profile}
        )

        logger.info(f"[caller={caller}] ✅ Updated group {group_id}")

        # Enhanced audit log
        logger.info(
            f"AUDIT: Group update | "
            f"caller={caller} | "
            f"group_id={group_id} | "
            f"group_name={profile['name']} | "
            f"name_changed={name is not None} | "
            f"description_changed={description is not None}"
        )

        return {
            "success": True,
            "message": f"Group updated successfully",
            "group": {
                "id": updated_group.get("id"),
                "name": updated_group.get("profile", {}).get("name"),
                "description": updated_group.get("profile", {}).get("description"),
                "type": updated_group.get("type")
            },
            "changes": {
                "name": {"old": current_name, "new": profile["name"]} if name is not None else None,
                "description": {"old": current_description, "new": profile["description"]} if description is not None else None
            },
            "updated_by": caller
        }

    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error updating group: {str(e)}")
        raise