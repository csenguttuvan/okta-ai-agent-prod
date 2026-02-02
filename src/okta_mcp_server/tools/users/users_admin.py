from typing import Optional, List, Dict, Any
from loguru import logger
from mcp.server.fastmcp import Context
from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client
from okta_mcp_server.context import get_caller_email, get_caller_groups

from okta_mcp_server.utils.validation import (
    validate_okta_id,
    validate_boolean,
    validate_and_raise,
    ValidationError,
)



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
def deactivate_user(
    user_id: str,
    ctx: Context = None
) -> str:  # ✅ Changed return type to str
    """Deactivate an Okta user (requires okta.users.manage scope).
    
    ⚠️ This suspends the user's access but does not delete the account.
    User can be reactivated later. Required before permanent deletion.
    
    Args:
        user_id: The Okta user ID (format: 00u1234567890123456)
        ctx: Optional context
    
    Returns:
        String message with operation status
    """
    caller = get_caller_email()
    
    # ✅ VALIDATION - NO EXCEPTIONS
    is_valid, error = validate_okta_id(user_id, "user", required=True)
    if not is_valid:
        msg = f"❌ {error}"
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Return string, don't raise
    
    logger.info(f"[{caller}] Deactivating user: {user_id}")
    
    try:
        client = get_client()
        
        # Get user email for logging
        user = client.get(f"/api/v1/users/{user_id}")
        user_email = user.get("profile", {}).get("email")
        current_status = user.get("status")
        
        # Check if already deactivated
        if current_status == "DEPROVISIONED":
            msg = f"❌ User {user_email} is already deactivated (status: {current_status})"
            logger.warning(f"[{caller}] {msg}")
            return msg
        
        # Audit log
        logger.warning(
            f"AUDIT: User deactivation | "
            f"caller={caller} | "
            f"target_user={user_email} | "
            f"target_user_id={user_id}"
        )
        
        # Deactivate user
        client.post(f"/api/v1/users/{user_id}/lifecycle/deactivate", data={})
        
        msg = f"✅ User {user_email} deactivated successfully. Can be reactivated or permanently deleted."
        logger.warning(f"[{caller}] {msg}")
        return msg  # ✅ Success string
        
    except PermissionError as e:
        msg = f"❌ Permission denied: {str(e)}"
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Error string
        
    except Exception as e:
        msg = f"❌ Error deactivating user: {str(e)}"
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Error string



@mcp.tool()
def delete_user(
    user_id: str,
    confirm_deletion: bool = False,
    ctx: Context = None
) -> str:  # ✅ Changed return type to str
    """Delete an Okta user (requires okta.users.manage scope).
    
    ⚠️ DESTRUCTIVE OPERATION - Cannot be undone. User must be deactivated first.
    
    Args:
        user_id: The Okta user ID (format: 00u1234567890123456)
        confirm_deletion: Must be True to proceed (prevents accidental deletion)
        ctx: Optional context
    
    Returns:
        String message with operation status
    
    Note:
        - User MUST be in DEACTIVATED status before deletion (Okta requirement)
        - Deletion is permanent and cannot be reversed
        - User's profile and data will be removed
    """
    caller = get_caller_email()
    
    # ✅ VALIDATION - NO EXCEPTIONS
    # Validate user_id format
    is_valid, error = validate_okta_id(user_id, "user", required=True)
    if not is_valid:
        msg = f"❌ {error}"
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Return string
    
    # Validate confirm_deletion is a boolean
    is_valid, error = validate_boolean(
        confirm_deletion,
        required=True,
        field_name="confirm_deletion"
    )
    if not is_valid:
        msg = f"❌ {error}"
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Return string
    
    # Business logic: Check confirmation is True
    if not confirm_deletion:
        msg = "❌ Deletion not confirmed. Set confirm_deletion=True to proceed. ⚠️ This is a PERMANENT operation that CANNOT be undone."
        logger.warning(f"[{caller}] {msg}")
        return msg  # ✅ Return string
    
    # END VALIDATION BLOCK
    logger.warning(f"[{caller}] ⚠️ DESTRUCTIVE: Attempting to delete user {user_id}")
    
    try:
        client = get_client()
        
        # Get user info before deletion
        user = client.get(f"/api/v1/users/{user_id}")
        user_email = user.get("profile", {}).get("email")
        user_status = user.get("status")
        
        # Verify user is DEACTIVATED (Okta requirement)
        if user_status != "DEACTIVATED":
            msg = f"❌ User {user_email} must be DEACTIVATED before deletion. Current status: {user_status}. Please deactivate the user first using deactivate_user()."
            logger.warning(f"[{caller}] {msg}")
            return msg  # ✅ Return string
        
        # Enhanced audit log
        logger.error(
            f"AUDIT: User deletion | "
            f"caller={caller} | "
            f"target_user={user_email} | "
            f"target_user_id={user_id} | "
            f"WARNING: PERMANENT_DELETION"
        )
        
        # Delete user
        client.delete(f"/api/v1/users/{user_id}")
        
        msg = f"⚠️ DELETED user {user_email} PERMANENTLY. This operation cannot be undone."
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Success string
        
    except PermissionError as e:
        msg = f"❌ Permission denied: {str(e)}"
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Error string
        
    except Exception as e:
        msg = f"❌ Error deleting user: {str(e)}"
        logger.error(f"[{caller}] {msg}")
        return msg  # ✅ Error string



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
) -> str:  # ✅ Changed to str
    """Search users by any profile attribute like division, department, title, location, etc.
    
    Common use cases:
    - Search by division: attribute="division", value="Corp IT"
    - Search by department: attribute="department", value="Engineering"
    - Search by title: attribute="title", value="Manager"
    - Search by location: attribute="location", value="New York"
    - Search by any custom profile field
    
    Args:
        attribute: Profile attribute name (e.g., 'division', 'department', 'title', 'location')
        value: Exact value to match (case-sensitive)
        limit: Maximum number of results (default: 200)
    
    Returns:
        Formatted string with user details
        
    Example:
        To find all users with division="Corp IT":
        search_users_by_attribute(attribute="division", value="Corp IT")
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
            users.append({
                "id": user.get("id"),
                "email": user.get("profile", {}).get("email"),
                "firstName": user.get("profile", {}).get("firstName"),
                "lastName": user.get("profile", {}).get("lastName"),
                "status": user.get("status"),
                attribute: user.get("profile", {}).get(attribute)
            })
        
        logger.info(f"[caller={caller}] Found {len(users)} users with {attribute}={value}")
        
        # ✅ Return formatted string instead of nested dict
        if not users:
            return f"No users found with {attribute}=\"{value}\""
        
        result = f"Found {len(users)} user(s) with {attribute}=\"{value}\":\n\n"
        for user in users:
            result += f"• {user['firstName']} {user['lastName']} ({user['email']})\n"
            result += f"  - Status: {user['status']}\n"
            result += f"  - ID: {user['id']}\n\n"
        
        return result
        
    except Exception as e:
        error_msg = f"❌ Error searching users by attribute: {str(e)}"
        logger.error(f"[caller={caller}] {error_msg}")
        return error_msg



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
    dry_run: bool = True,  # Changed default to True for safety
    confirm_removal: bool = False,
    ctx: Context = None
) -> dict:
    """Find ACTIVE users by profile attribute and remove them from a group.
    
    ⚠️ BULK OPERATION - Affects multiple users at once.
    
    Args:
        attribute: Profile attribute name (e.g., 'division')
        value: Attribute value to match (e.g., 'Corp IT')
        group_id: Okta group ID to remove users from
        dry_run: If True (default), only shows who would be affected
        confirm_removal: Must be True when dry_run=False to proceed
        ctx: Optional context
        
    Returns:
        Dict with operation results
    """
    caller = get_caller_email()
    
    # Safety check for live operations
    if not dry_run and not confirm_removal:
        return {
            "success": False,
            "error": "Removal not confirmed",
            "message": "Set confirm_removal=True to proceed with bulk removal (or use dry_run=True to preview)",
            "warning": "⚠️ This is a bulk operation that will affect multiple users"
        }
    
    if dry_run:
        logger.info(f"[caller={caller}] DRY RUN: Previewing removal of ACTIVE users with {attribute}={value} from group {group_id}")
    else:
        logger.warning(f"[caller={caller}] ⚠️ BULK OPERATION: Removing ACTIVE users with {attribute}={value} from group {group_id}")
    
    # ... rest of implementation from previous version


    
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


@mcp.tool()
def activate_user(
    user_id: str,
    send_email: bool = False,
    ctx: Context = None
) -> str:  # ✅ Changed from dict to str
    """Activate a user in PROVISIONED status (requires okta.users.manage scope).
    
    This allows activating users that were created but never completed signup.
    Only works for users in PROVISIONED or STAGED status.
    
    Args:
        user_id: The Okta user ID or login email
        send_email: Whether to send activation email to user (default: False)
        ctx: Optional context
        
    Returns:
        String message with operation status
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Activating user {user_id}")
    
    client = get_client()
    
    try:
        # Get current status
        user = client.get(f"/api/v1/users/{user_id}")
        status = user.get("status")
        email = user.get("profile", {}).get("email")
        
        if status == "ACTIVE":
            msg = f"✅ User {email} is already ACTIVE - no activation needed."
            logger.info(f"[caller={caller}] {msg}")
            return msg  # ✅ Return string
        
        if status not in ["PROVISIONED", "STAGED"]:
            msg = (
                f"❌ User {email} cannot be activated from status '{status}'. "
                f"Only PROVISIONED or STAGED users can be activated.\n"
                f"Current status: {status}\n"
                f"User ID: {user_id}"
            )
            logger.warning(f"[caller={caller}] {msg}")
            return msg  # ✅ Return string
        
        # Activate user
        params = {"sendEmail": str(send_email).lower()}
        client.post(f"/api/v1/users/{user_id}/lifecycle/activate", params=params, data={})
        
        # Build success message
        msg = f"✅ User {email} activated successfully!\n"
        msg += f"  - Previous status: {status}\n"
        msg += f"  - New status: ACTIVE\n"
        msg += f"  - User ID: {user_id}\n"
        msg += f"  - Activated by: {caller}\n"
        if send_email:
            msg += f"  - Activation email sent to {email}"
        else:
            msg += f"  - No activation email sent (send_email=False)"
        
        logger.info(f"[caller={caller}] ✅ Activated user {email}")
        return msg  # ✅ Return string
        
    except PermissionError as e:
        msg = f"❌ Permission denied: {str(e)}"
        logger.error(f"[caller={caller}] {msg}")
        return msg  # ✅ Return string instead of raising
        
    except Exception as e:
        msg = f"❌ Error activating user: {str(e)}"
        logger.error(f"[caller={caller}] {msg}")
        return msg  # ✅ Return string instead of raising



@mcp.tool()
def reactivate_user(
    user_id: str,
    ctx: Context = None
) -> str:  # ✅ Changed from dict to str
    """Reactivate a deactivated user (undo deactivation).
    
    Restores access to a previously deactivated user. Only works for DEACTIVATED users.
    Cannot restore DELETED users.
    
    Args:
        user_id: The Okta user ID or login email
        ctx: Optional context
        
    Returns:
        String message with operation status
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Attempting to reactivate user: {user_id}")
    
    client = get_client()
    
    try:
        # Check current status
        user = client.get(f"/api/v1/users/{user_id}")
        status = user.get("status")
        email = user.get("profile", {}).get("email")
        
        if status == "ACTIVE":
            msg = f"✅ User {email} is already ACTIVE - no action needed."
            logger.info(f"[caller={caller}] {msg}")
            return msg  # ✅ Return string
        
        if status != "DEPROVISIONED":
            msg = (
                f"❌ User {email} cannot be reactivated from status '{status}'. "
                f"Only DEPROVISIONED users can be reactivated.\n"
                f"DELETED users cannot be restored.\n"
                f"Current status: {status}\n"
                f"User ID: {user_id}"
            )
            logger.warning(f"[caller={caller}] {msg}")
            return msg  # ✅ Return string
        
        # Reactivate
        client.post(f"/api/v1/users/{user_id}/lifecycle/reactivate", data={})
        
        logger.info(
            f"AUDIT: User reactivation | "
            f"caller={caller} | "
            f"target_user={email} | "
            f"target_user_id={user_id}"
        )
        
        msg = f"✅ User {email} reactivated successfully!\n"
        msg += f"  - Previous status: DEPROVISIONED\n"
        msg += f"  - New status: ACTIVE\n"
        msg += f"  - User ID: {user_id}\n"
        msg += f"  - Reactivated by: {caller}"
        
        logger.info(f"[caller={caller}] ✅ Reactivated user {email}")
        return msg  # ✅ Return string
        
    except PermissionError as e:
        msg = f"❌ Permission denied: {str(e)}"
        logger.error(f"[caller={caller}] {msg}")
        return msg  # ✅ Return string
        
    except Exception as e:
        msg = f"❌ Error reactivating user: {str(e)}"
        logger.error(f"[caller={caller}] {msg}")
        return msg  # ✅ Return string


