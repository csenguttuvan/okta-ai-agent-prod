from typing import Optional, List, Dict, Any
from loguru import logger
from mcp.server.fastmcp import Context
from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client
from okta_mcp_server.context import get_caller_email, get_caller_groups



# ---------------------------
# Helper Functions
# ---------------------------

def _validate_user_is_active(client, user_id: str, caller: str) -> tuple[bool, str, dict]:
    """
    Validate that a user is ACTIVE before performing operations.
    
    Args:
        client: The Okta client
        user_id: User ID or email to validate
        caller: Email of the person making the request
    
    Returns:
        tuple: (is_active: bool, error_message: str, user_data: dict)
    """
    try:
        user = client.get(f"/api/v1/users/{user_id}")
        status = user.get("status")
        
        if status == "ACTIVE":
            return True, "", user
        else:
            email = user.get("profile", {}).get("email", user_id)
            error_msg = f"User {email} has status '{status}'. Only ACTIVE users can be modified."
            logger.warning(f"[caller={caller}] ⚠️ {error_msg}")
            return False, error_msg, user
            
    except Exception as e:
        error_msg = f"Failed to validate user {user_id}: {str(e)}"
        logger.error(f"[caller={caller}] ❌ {error_msg}")
        return False, error_msg, {}




@mcp.tool()
def create_user(
    email: str,
    first_name: str,
    last_name: str,
    activate: bool = True,
    ctx: Context = None
) -> dict:
    """Create a new Okta user (requires okta.users.manage scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Creating user: {email}")
    
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
        user = client.post(f"/api/v1/users?activate={str(activate).lower()}", data=body)
        logger.info(f"[caller={caller}] ✅ Created user: {user.get('id')}")
        return user
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error creating user: {str(e)}")
        raise

@mcp.tool()
def deactivate_user(user_id: str, ctx: Context = None) -> dict:
    """Deactivate an Okta user (requires okta.users.manage scope)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Deactivating user: {user_id}")
    
    client = get_client()
    
    try:
        client.post(f"/api/v1/users/{user_id}/lifecycle/deactivate", data={})
        logger.info(f"[caller={caller}] ✅ Deactivated user: {user_id}")
        return {"message": f"User {user_id} deactivated successfully"}
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error deactivating user: {str(e)}")
        raise

@mcp.tool()
def delete_user(user_id: str, ctx: Context = None) -> dict:
    """Delete an Okta user (requires okta.users.manage scope).
    
    Note: User must be deactivated first."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Deleting user: {user_id}")
    
    client = get_client()
    
    try:
        client.delete(f"/api/v1/users/{user_id}")
        logger.info(f"[caller={caller}] ✅ Deleted user: {user_id}")
        return {"message": f"User {user_id} deleted successfully"}
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error deleting user: {str(e)}")
        raise


@mcp.tool()
def add_users_to_group(
    group_id: str,
    user_ids: list[str]
) -> dict:
    """Add multiple users to a group in a single operation.
    
    Only ACTIVE users will be added. Non-active users will be skipped.
    
    Args:
        group_id: The Okta group ID
        user_ids: List of Okta user IDs to add to the group
        
    Returns:
        Dictionary with added count, skipped count, and results
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Batch adding {len(user_ids)} users to group {group_id}")
    
    try:
        client = get_client()
        
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
                
                # Add user to group
                client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
                results.append({
                    "user_id": user_id,
                    "status": "added"
                })
                logger.info(f"[caller={caller}] ✅ Added user {user_id} to group {group_id}")
                
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
        
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Failed to initialize Okta client: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to initialize Okta client: {str(e)}"
        }




@mcp.tool()
def search_users_by_attribute(
    attribute: str,
    value: str,
    limit: int = 200,
    ctx: Context = None
) -> dict:
    """Search users by profile attributes (e.g., department, division, title, location).
    
    Supports filtering by any profile attribute:
    - division: User's division (e.g., "Corp IT", "Engineering")
    - department: Department name
    - title: Job title
    - location: Office location
    - Any custom profile attribute
    
    Args:
        attribute: Profile attribute name (e.g., 'division', 'department', 'title')
        value: Attribute value to match
        limit: Maximum number of results (default: 200)
    
    Returns:
        Dict with matching users
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Searching users with {attribute}={value}")
    
    try:
        client = get_client()
        
        # Build Okta search filter: profile.{attribute} eq "{value}"
        search_filter = f'profile.{attribute} eq "{value}"'
        
        # Use Okta's search API
        response = client.get(f"/api/v1/users", params={
            "search": search_filter,
            "limit": limit
        })
        
        users = []
        for user in response:
            user_data = {
                "id": user.get("id"),
                "email": user.get("profile", {}).get("email"),
                "firstName": user.get("profile", {}).get("firstName"),
                "lastName": user.get("profile", {}).get("lastName"),
                "status": user.get("status"),
                attribute: user.get("profile", {}).get(attribute)
            }
            users.append(user_data)
        
        logger.info(f"[caller={caller}] Found {len(users)} users with {attribute}={value}")
        
        return {
            "success": True,
            "users": users,
            "count": len(users),
            "filter": search_filter
        }
        
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error searching users by attribute: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "users": [],
            "count": 0
        }


@mcp.tool()
def add_users_to_group_by_attribute(
    attribute: str,
    value: str,
    group_id: str,
    dry_run: bool = False,
    ctx: Context = None
) -> dict:
    """Find ACTIVE users by profile attribute and add them to a group.
    
    Only ACTIVE users will be added. Users with other statuses are excluded from search.
    
    Args:
        attribute: Profile attribute name (e.g., 'division')
        value: Attribute value to match (e.g., 'Corp IT')
        group_id: Okta group ID to add users to
        dry_run: If True, only return who would be added without making changes
        
    Returns:
        Dict with operation results
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Bulk adding ACTIVE users with {attribute}={value} to group {group_id}")
    
    try:
        client = get_client()
        
        # Step 1: Search users - ONLY ACTIVE users
        search_filter = f'profile.{attribute} eq "{value}" and status eq "ACTIVE"'
        response = client.get(f"/api/v1/users", params={
            "search": search_filter,
            "limit": 200
        })
        
        matching_users = []
        for user in response:
            matching_users.append({
                "id": user.get("id"),
                "email": user.get("profile", {}).get("email"),
                "name": f"{user.get('profile', {}).get('firstName', '')} {user.get('profile', {}).get('lastName', '')}",
                "status": user.get("status")  # Should all be ACTIVE
            })
        
        if not matching_users:
            logger.info(f"[caller={caller}] No ACTIVE users found with {attribute}={value}")
            return {
                "success": True,
                "message": f"No ACTIVE users found with {attribute}={value}",
                "count": 0,
                "users": [],
                "note": "Search filtered to ACTIVE users only"
            }
        
        # Step 2: Dry run
        if dry_run:
            logger.info(f"[caller={caller}] DRY RUN: Would add {len(matching_users)} ACTIVE users to group")
            return {
                "success": True,
                "message": f"DRY RUN: Would add {len(matching_users)} ACTIVE users to group",
                "count": len(matching_users),
                "users": matching_users,
                "group_id": group_id,
                "note": "Only ACTIVE users shown"
            }
        
        # Step 3: Add users to group
        results = []
        errors = []
        
        for user in matching_users:
            try:
                client.put(f"/api/v1/groups/{group_id}/users/{user['id']}")
                results.append({
                    "user_id": user["id"],
                    "email": user["email"],
                    "status": "added"
                })
                logger.info(f"[caller={caller}] ✅ Added {user['email']} to group {group_id}")
                
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower() or "409" in error_msg:
                    results.append({
                        "user_id": user["id"],
                        "email": user["email"],
                        "status": "already_member"
                    })
                    logger.info(f"[caller={caller}] ℹ️ {user['email']} already in group")
                else:
                    errors.append({
                        "user_id": user["id"],
                        "email": user["email"],
                        "error": error_msg
                    })
                    logger.error(f"[caller={caller}] ❌ Failed to add {user['email']}: {error_msg}")
        
        added_count = len([r for r in results if r["status"] == "added"])
        already_member_count = len([r for r in results if r["status"] == "already_member"])
        
        logger.info(f"[caller={caller}] ✅ Completed: {added_count} added, {already_member_count} already members, {len(errors)} errors")
        
        return {
            "success": True,
            "message": f"Added {added_count} ACTIVE users to group",
            "total_found": len(matching_users),
            "added": added_count,
            "already_members": already_member_count,
            "errors": len(errors),
            "results": results,
            "error_details": errors if errors else None,
            "note": "Only ACTIVE users were processed"
        }
        
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error in bulk group assignment: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "count": 0
        }



@mcp.tool()
def remove_users_from_group_by_attribute(
    attribute: str,
    value: str,
    group_id: str,
    dry_run: bool = False,
    ctx: Context = None
) -> dict:
    """Find ACTIVE users by profile attribute and remove them from a group.
    
    Only ACTIVE users will be removed. Users with other statuses are excluded from search.
    
    Args:
        attribute: Profile attribute name (e.g., 'division')
        value: Attribute value to match (e.g., 'Corp IT')
        group_id: Okta group ID to remove users from
        dry_run: If True, only return who would be removed without making changes
        
    Returns:
        Dict with operation results
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Bulk removing ACTIVE users with {attribute}={value} from group {group_id}")
    
    try:
        client = get_client()
        
        # Step 1: Search users - ONLY ACTIVE users
        search_filter = f'profile.{attribute} eq "{value}" and status eq "ACTIVE"'
        response = client.get(f"/api/v1/users", params={
            "search": search_filter,
            "limit": 200
        })
        
        matching_users = []
        for user in response:
            matching_users.append({
                "id": user.get("id"),
                "email": user.get("profile", {}).get("email"),
                "name": f"{user.get('profile', {}).get('firstName', '')} {user.get('profile', {}).get('lastName', '')}",
                "status": user.get("status")
            })
        
        if not matching_users:
            logger.info(f"[caller={caller}] No ACTIVE users found with {attribute}={value}")
            return {
                "success": True,
                "message": f"No ACTIVE users found with {attribute}={value}",
                "count": 0,
                "users": [],
                "note": "Search filtered to ACTIVE users only"
            }
        
        # Step 2: Dry run
        if dry_run:
            logger.info(f"[caller={caller}] DRY RUN: Would remove {len(matching_users)} ACTIVE users from group")
            return {
                "success": True,
                "message": f"DRY RUN: Would remove {len(matching_users)} ACTIVE users from group",
                "count": len(matching_users),
                "users": matching_users,
                "group_id": group_id,
                "note": "Only ACTIVE users shown"
            }
        
        # Step 3: Remove users from group
        results = []
        errors = []
        
        for user in matching_users:
            try:
                client.delete(f"/api/v1/groups/{group_id}/users/{user['id']}")
                results.append({
                    "user_id": user["id"],
                    "email": user["email"],
                    "status": "removed"
                })
                logger.info(f"[caller={caller}] ✅ Removed {user['email']} from group {group_id}")
                
            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower() or "404" in error_msg:
                    results.append({
                        "user_id": user["id"],
                        "email": user["email"],
                        "status": "not_member"
                    })
                    logger.info(f"[caller={caller}] ℹ️ {user['email']} not in group")
                else:
                    errors.append({
                        "user_id": user["id"],
                        "email": user["email"],
                        "error": error_msg
                    })
                    logger.error(f"[caller={caller}] ❌ Failed to remove {user['email']}: {error_msg}")
        
        removed_count = len([r for r in results if r["status"] == "removed"])
        not_member_count = len([r for r in results if r["status"] == "not_member"])
        
        logger.info(f"[caller={caller}] ✅ Completed: {removed_count} removed, {not_member_count} not members, {len(errors)} errors")
        
        return {
            "success": True,
            "message": f"Removed {removed_count} ACTIVE users from group",
            "total_found": len(matching_users),
            "removed": removed_count,
            "not_members": not_member_count,
            "errors": len(errors),
            "results": results,
            "error_details": errors if errors else None,
            "note": "Only ACTIVE users were processed"
        }
        
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error in bulk group removal: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "count": 0
        }

    
@mcp.tool()
def unassign_users_from_application_by_attribute(
    app_id: str,
    attribute: str,
    value: str,
    dry_run: bool = False,
    ctx: Context | None = None
) -> dict[str, Any]:
    """Find ACTIVE users by profile attribute and remove them from an application.
    
    Only ACTIVE users will be unassigned. Users with other statuses are excluded from search.
    
    Args:
        app_id: The Okta application ID
        attribute: Profile attribute name (e.g., 'division', 'department')
        value: Attribute value to match
        dry_run: If True, only return who would be removed without making changes
        
    Returns:
        Dict with operation results
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Bulk removing ACTIVE users with {attribute}={value} from app {app_id}")
    
    if not app_id or not attribute or not value:
        error_msg = "app_id, attribute, and value are all required"
        logger.error(f"[caller={caller}] {error_msg}")
        raise ValueError(error_msg)
    
    try:
        client = get_client()
        
        # Step 1: Search users by attribute - ONLY ACTIVE users
        search_filter = f'profile.{attribute} eq "{value}" and status eq "ACTIVE"'
        response = client.get("/api/v1/users", params={
            "search": search_filter,
            "limit": 200
        })
        
        matching_users = []
        for user in response:
            matching_users.append({
                "id": user.get("id"),
                "email": user.get("profile", {}).get("email"),
                "name": f"{user.get('profile', {}).get('firstName', '')} {user.get('profile', {}).get('lastName', '')}".strip(),
                "status": user.get("status")
            })
        
        if not matching_users:
            logger.info(f"[caller={caller}] No ACTIVE users found with {attribute}={value}")
            return {
                "success": True,
                "message": f"No ACTIVE users found with {attribute}={value}",
                "count": 0,
                "users": [],
                "note": "Search filtered to ACTIVE users only"
            }
        
        # Step 2: Dry run
        if dry_run:
            logger.info(f"[caller={caller}] DRY RUN: Would remove {len(matching_users)} ACTIVE users from app {app_id}")
            return {
                "success": True,
                "message": f"DRY RUN: Would remove {len(matching_users)} ACTIVE users from application",
                "count": len(matching_users),
                "users": matching_users,
                "app_id": app_id,
                "filter": search_filter,
                "note": "Only ACTIVE users shown"
            }
        
        # Step 3: Remove users from application
        results = []
        errors = []
        
        for user in matching_users:
            try:
                client.delete(f"/api/v1/apps/{app_id}/users/{user['id']}")
                results.append({
                    "user_id": user["id"],
                    "email": user["email"],
                    "status": "removed"
                })
                logger.info(f"[caller={caller}] ✅ Removed {user['email']} from app {app_id}")
                
            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower() or "404" in error_msg:
                    results.append({
                        "user_id": user["id"],
                        "email": user["email"],
                        "status": "not_assigned"
                    })
                    logger.info(f"[caller={caller}] ℹ️ {user['email']} not assigned to app")
                else:
                    errors.append({
                        "user_id": user["id"],
                        "email": user["email"],
                        "error": error_msg
                    })
                    logger.error(f"[caller={caller}] ❌ Failed to remove {user['email']}: {error_msg}")
        
        removed_count = len([r for r in results if r["status"] == "removed"])
        not_assigned_count = len([r for r in results if r["status"] == "not_assigned"])
        
        logger.info(f"[caller={caller}] ✅ Completed: {removed_count} removed, {not_assigned_count} not assigned, {len(errors)} errors")
        
        return {
            "success": True,
            "message": f"Removed {removed_count} ACTIVE users from application",
            "total_found": len(matching_users),
            "removed": removed_count,
            "not_assigned": not_assigned_count,
            "errors": len(errors),
            "results": results,
            "error_details": errors if errors else None,
            "app_id": app_id,
            "filter": search_filter,
            "note": "Only ACTIVE users were processed"
        }
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error in bulk app removal: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "count": 0
        }

    
