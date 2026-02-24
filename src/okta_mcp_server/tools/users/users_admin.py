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
    """Validate that a user is ACTIVE before performing operations."""
    try:
        user = client.get(f"/api/v1/users/{user_id}")
        status = user.get("status")
        if status == "ACTIVE":
            return True, "", user
        email = user.get("profile", {}).get("email", user_id)
        error_msg = f"User {email} has status '{status}'. Only ACTIVE users can be modified."
        logger.warning(f"[caller={caller}] ⚠️ {error_msg}")
        return False, error_msg, user
    except Exception as e:
        error_msg = f"Failed to validate user {user_id}: {str(e)}"
        logger.error(f"[caller={caller}] ❌ {error_msg}")
        return False, error_msg, {}


# ---------------------------
# Tools
# ---------------------------

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
    body = {
        "profile": {
            "email": email,
            "login": email,
            "firstName": first_name,
            "lastName": last_name,
        }
    }

    try:
        # FIX: activate param goes in the URL query string, not a separate unused dict
        user = client.post(f"/api/v1/users?activate={str(activate).lower()}", data=body)
        logger.info(f"[caller={caller}] ✅ Created user: {user.get('id')}")
        return {
            "id": user.get("id"),
            "email": user.get("profile", {}).get("email"),
            "status": user.get("status"),
            "created": user.get("created"),
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error creating user: {str(e)}")
        raise


@mcp.tool()
def update_user(
    user_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    department: Optional[str] = None,
    title: Optional[str] = None,
    ctx: Context = None
) -> str:
    """Update a user's profile attributes (requires okta.users.manage scope).

    Args:
        user_id: Okta user ID (00u...) or login email
        first_name: New first name (optional)
        last_name: New last name (optional)
        email: New email/login (optional)
        department: New department (optional)
        title: New title (optional)
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Updating user: {user_id}")

    profile = {}
    if first_name: profile["firstName"] = first_name
    if last_name:  profile["lastName"]  = last_name
    if email:
        profile["email"] = email
        profile["login"] = email
    if department: profile["department"] = department
    if title:      profile["title"]      = title

    if not profile:
        return "❌ No fields provided to update."

    try:
        client = get_client()
        user = client.post(f"/api/v1/users/{user_id}", data={"profile": profile})
        updated_email = user.get("profile", {}).get("email", user_id)
        msg = f"✅ Updated user {updated_email} — changed: {', '.join(profile.keys())}"
        logger.info(f"[caller={caller}] {msg}")
        return msg
    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error updating user: {str(e)}"


@mcp.tool()
def deactivate_user(user_id: str, ctx: Context = None) -> str:
    """Deactivate an Okta user (requires okta.users.manage scope).

    ⚠️ Suspends user access but does not delete. Required before permanent deletion.

    Args:
        user_id: Okta user ID (00u...)
    """
    caller = get_caller_email()

    is_valid, error = validate_okta_id(user_id, "user", required=True)
    if not is_valid:
        return f"❌ {error}"

    logger.info(f"[{caller}] Deactivating user: {user_id}")

    try:
        client = get_client()
        user = client.get(f"/api/v1/users/{user_id}")
        user_email = user.get("profile", {}).get("email")
        current_status = user.get("status")

        if current_status == "DEPROVISIONED":
            return f"❌ User {user_email} is already deactivated (DEPROVISIONED)."

        logger.warning(
            f"AUDIT: User deactivation | caller={caller} | "
            f"target={user_email} | id={user_id}"
        )

        client.post(f"/api/v1/users/{user_id}/lifecycle/deactivate", data={})
        msg = f"✅ User {user_email} deactivated (DEPROVISIONED). Can be reactivated or permanently deleted."
        logger.warning(f"[{caller}] {msg}")
        return msg

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error deactivating user: {str(e)}"


@mcp.tool()
def delete_user(
    user_id: str,
    confirm_deletion: bool = False,
    ctx: Context = None
) -> str:
    """Permanently delete an Okta user (requires okta.users.manage scope).

    ⚠️ IRREVERSIBLE. User must be DEPROVISIONED first via deactivate_user().

    Args:
        user_id: Okta user ID (00u...)
        confirm_deletion: Must be True to proceed
    """
    caller = get_caller_email()

    is_valid, error = validate_okta_id(user_id, "user", required=True)
    if not is_valid:
        return f"❌ {error}"

    is_valid, error = validate_boolean(confirm_deletion, required=True, field_name="confirm_deletion")
    if not is_valid:
        return f"❌ {error}"

    if not confirm_deletion:
        return "❌ Set confirm_deletion=True to proceed. ⚠️ This is PERMANENT and cannot be undone."

    logger.warning(f"[{caller}] ⚠️ DESTRUCTIVE: Attempting to delete user {user_id}")

    try:
        client = get_client()
        user = client.get(f"/api/v1/users/{user_id}")
        user_email = user.get("profile", {}).get("email")
        user_status = user.get("status")

        # FIX: Only DEPROVISIONED is valid for deletion, not SUSPENDED
        if user_status != "DEPROVISIONED":
            return (
                f"❌ User {user_email} must be DEPROVISIONED before deletion.\n"
                f"Current status: {user_status}\n"
                f"Run deactivate_user('{user_id}') first."
            )

        logger.error(
            f"AUDIT: User deletion | caller={caller} | "
            f"target={user_email} | id={user_id} | WARNING=PERMANENT"
        )

        client.delete(f"/api/v1/users/{user_id}")
        msg = f"⚠️ PERMANENTLY DELETED user {user_email}. This cannot be undone."
        logger.error(f"[{caller}] {msg}")
        return msg

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error deleting user: {str(e)}"


@mcp.tool()
def reset_user_mfa_and_password(
    user_id: str,
    ctx: Context = None
) -> str:
    """Reset MFA factors and send password reset email for a user.

    Args:
        user_id: Okta user ID (00u...) or login email
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Resetting MFA and password for: {user_id}")

    try:
        client = get_client()

        user = client.get(f"/api/v1/users/{user_id}")
        user_email = user.get("profile", {}).get("email", user_id)
        uid = user.get("id")

        results = []

        # Reset all MFA factors
        try:
            factors = client.get(f"/api/v1/users/{uid}/factors")
            for factor in factors:
                fid = factor.get("id")
                if fid:
                    client.delete(f"/api/v1/users/{uid}/factors/{fid}")
            results.append(f"✅ Reset {len(factors)} MFA factor(s)")
        except Exception as e:
            results.append(f"⚠️ MFA reset failed: {str(e)}")

        # Send password reset email
        try:
            client.post(
                f"/api/v1/users/{uid}/lifecycle/reset_password",
                params={"sendEmail": "true"},
                data={}
            )
            results.append(f"✅ Password reset email sent to {user_email}")
        except Exception as e:
            results.append(f"⚠️ Password reset failed: {str(e)}")

        logger.warning(
            f"AUDIT: MFA+password reset | caller={caller} | "
            f"target={user_email} | id={uid}"
        )

        return f"Reset completed for {user_email}:\n" + "\n".join(results)

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error resetting user: {str(e)}"


@mcp.tool()
def add_users_to_group(
    group_id: str,
    user_ids: List[str]
) -> dict:
    """Add multiple users to a group. Only ACTIVE users are added."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Batch adding {len(user_ids)} users to group {group_id}")

    try:
        client = get_client()
        results, failed, skipped_inactive = [], [], []

        for user_id in user_ids:
            try:
                is_active, error_msg, user = _validate_user_is_active(client, user_id, caller)
                if not is_active:
                    skipped_inactive.append({
                        "user_id": user_id,
                        "status": user.get("status"),
                        "email": user.get("profile", {}).get("email"),
                        "reason": error_msg
                    })
                    continue
                client.put(f"/api/v1/groups/{group_id}/users/{user_id}")
                results.append({"user_id": user_id, "status": "added"})
            except Exception as e:
                failed.append({"user_id": user_id, "error": str(e)})

        return {
            "success": True,
            "total": len(user_ids),
            "added": len(results),
            "skipped_inactive": len(skipped_inactive),
            "failed": len(failed),
            "results": results,
            "skipped_users": skipped_inactive or None,
            "failures": failed or None,
            "message": f"Added {len(results)} users. Skipped {len(skipped_inactive)} inactive."
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def search_users_by_attribute(
    attribute: str,
    value: str,
    limit: int = 200,
    ctx: Context = None
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
            result += (
                f"• {p.get('firstName')} {p.get('lastName')} ({p.get('email')})\n"
                f"  Status: {u.get('status')}, ID: {u.get('id')}\n"
                f"  {attribute}: {p.get(attribute)}\n\n"
            )
        return result

    except Exception as e:
        return f"❌ Error searching by attribute: {str(e)}"


@mcp.tool()
def add_users_to_group_by_attribute(
    attribute: str,
    value: str,
    group_id: str,
    dry_run: bool = False,
    ctx: Context = None
) -> dict:
    """Find ACTIVE users by profile attribute and add them to a group."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Bulk adding ACTIVE users with {attribute}={value} to group {group_id}")

    try:
        client = get_client()
        search_filter = f'profile.{attribute} eq "{value}" and status eq "ACTIVE"'
        response = client.get("/api/v1/users", params={"search": search_filter, "limit": 200})

        matching_users = [
            {
                "id": u.get("id"),
                "email": u.get("profile", {}).get("email"),
                "name": f"{u.get('profile',{}).get('firstName','')} {u.get('profile',{}).get('lastName','')}".strip(),
                "status": u.get("status")
            }
            for u in response
        ]

        if not matching_users:
            return {"success": True, "message": f"No ACTIVE users found with {attribute}={value}", "count": 0}

        if dry_run:
            return {"success": True, "message": f"DRY RUN: Would add {len(matching_users)} users",
                    "count": len(matching_users), "users": matching_users, "group_id": group_id}

        results, errors = [], []
        for user in matching_users:
            try:
                client.put(f"/api/v1/groups/{group_id}/users/{user['id']}")
                results.append({"user_id": user["id"], "email": user["email"], "status": "added"})
            except Exception as e:
                err = str(e)
                if "409" in err or "already exists" in err.lower():
                    results.append({"user_id": user["id"], "email": user["email"], "status": "already_member"})
                else:
                    errors.append({"user_id": user["id"], "email": user["email"], "error": err})

        added = len([r for r in results if r["status"] == "added"])
        already = len([r for r in results if r["status"] == "already_member"])

        return {
            "success": True,
            "message": f"Added {added} ACTIVE users to group",
            "total_found": len(matching_users),
            "added": added, "already_members": already,
            "errors": len(errors), "results": results,
            "error_details": errors or None
        }

    except Exception as e:
        return {"success": False, "error": str(e), "count": 0}


@mcp.tool()
def remove_users_from_group_by_attribute(
    attribute: str,
    value: str,
    group_id: str,
    dry_run: bool = True,
    confirm_removal: bool = False,
    ctx: Context = None
) -> dict:
    """Find ACTIVE users by profile attribute and remove them from a group.

    ⚠️ BULK OPERATION. Defaults to dry_run=True for safety.

    Args:
        attribute: Profile attribute (e.g. 'division')
        value: Attribute value to match
        group_id: Okta group ID to remove users from
        dry_run: Preview only if True (default)
        confirm_removal: Must be True when dry_run=False
    """
    caller = get_caller_email()

    if not dry_run and not confirm_removal:
        return {
            "success": False,
            "error": "Set confirm_removal=True to proceed, or use dry_run=True to preview.",
            "warning": "⚠️ This is a bulk operation affecting multiple users."
        }

    logger.info(f"[caller={caller}] {'DRY RUN: ' if dry_run else ''}Removing ACTIVE users "
                f"with {attribute}={value} from group {group_id}")

    try:
        client = get_client()
        search_filter = f'profile.{attribute} eq "{value}" and status eq "ACTIVE"'
        response = client.get("/api/v1/users", params={"search": search_filter, "limit": 200})

        matching_users = [
            {
                "id": u.get("id"),
                "email": u.get("profile", {}).get("email"),
                "name": f"{u.get('profile',{}).get('firstName','')} {u.get('profile',{}).get('lastName','')}".strip(),
                "status": u.get("status")
            }
            for u in response
        ]

        if not matching_users:
            return {"success": True, "message": f"No ACTIVE users found with {attribute}={value}", "count": 0}

        if dry_run:
            return {
                "success": True,
                "message": f"DRY RUN: Would remove {len(matching_users)} ACTIVE users from group",
                "count": len(matching_users), "users": matching_users, "group_id": group_id,
                "note": "Set dry_run=False and confirm_removal=True to proceed"
            }

        results, errors = [], []
        for user in matching_users:
            try:
                client.delete(f"/api/v1/groups/{group_id}/users/{user['id']}")
                results.append({"user_id": user["id"], "email": user["email"], "status": "removed"})
                logger.info(f"[caller={caller}] ✅ Removed {user['email']} from group {group_id}")
            except Exception as e:
                err = str(e)
                if "404" in err or "not found" in err.lower():
                    results.append({"user_id": user["id"], "email": user["email"], "status": "not_member"})
                else:
                    errors.append({"user_id": user["id"], "email": user["email"], "error": err})

        removed = len([r for r in results if r["status"] == "removed"])
        not_member = len([r for r in results if r["status"] == "not_member"])

        logger.warning(f"AUDIT: Bulk group removal | caller={caller} | {attribute}={value} | "
                      f"group={group_id} | removed={removed}")

        return {
            "success": True,
            "message": f"Removed {removed} ACTIVE users from group",
            "total_found": len(matching_users),
            "removed": removed, "not_member": not_member,
            "errors": len(errors), "results": results,
            "error_details": errors or None
        }

    except Exception as e:
        return {"success": False, "error": str(e), "count": 0}


@mcp.tool()
def unassign_users_from_application_by_attribute(
    app_id: str,
    attribute: str,
    value: str,
    dry_run: bool = False,
    ctx: Context | None = None
) -> Dict[str, Any]:
    """Find ACTIVE users by profile attribute and remove them from an application."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Bulk removing users with {attribute}={value} from app {app_id}")

    if not app_id or not attribute or not value:
        raise ValueError("app_id, attribute, and value are all required")

    try:
        client = get_client()
        search_filter = f'profile.{attribute} eq "{value}" and status eq "ACTIVE"'
        response = client.get("/api/v1/users", params={"search": search_filter, "limit": 200})

        matching_users = [
            {
                "id": u.get("id"),
                "email": u.get("profile", {}).get("email"),
                "name": f"{u.get('profile',{}).get('firstName','')} {u.get('profile',{}).get('lastName','')}".strip(),
                "status": u.get("status")
            }
            for u in response
        ]

        if not matching_users:
            return {"success": True, "message": f"No ACTIVE users found with {attribute}={value}", "count": 0}

        if dry_run:
            return {"success": True, "message": f"DRY RUN: Would remove {len(matching_users)} users",
                    "count": len(matching_users), "users": matching_users, "app_id": app_id}

        results, errors = [], []
        for user in matching_users:
            try:
                client.delete(f"/api/v1/apps/{app_id}/users/{user['id']}")
                results.append({"user_id": user["id"], "email": user["email"], "status": "removed"})
            except Exception as e:
                err = str(e)
                if "404" in err or "not found" in err.lower():
                    results.append({"user_id": user["id"], "email": user["email"], "status": "not_assigned"})
                else:
                    errors.append({"user_id": user["id"], "email": user["email"], "error": err})

        removed = len([r for r in results if r["status"] == "removed"])
        not_assigned = len([r for r in results if r["status"] == "not_assigned"])

        return {
            "success": True,
            "message": f"Removed {removed} users from application",
            "total_found": len(matching_users),
            "removed": removed, "not_assigned": not_assigned,
            "errors": len(errors), "results": results,
            "error_details": errors or None, "app_id": app_id
        }

    except PermissionError as e:
        raise
    except Exception as e:
        return {"success": False, "error": str(e), "count": 0}


@mcp.tool()
def activate_user(user_id: str, send_email: bool = False, ctx: Context = None) -> str:
    """Activate a user in PROVISIONED or STAGED status."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Activating user {user_id}")
    client = get_client()

    try:
        user = client.get(f"/api/v1/users/{user_id}")
        status = user.get("status")
        email = user.get("profile", {}).get("email")

        if status == "ACTIVE":
            return f"✅ User {email} is already ACTIVE."

        if status not in ["PROVISIONED", "STAGED"]:
            return (f"❌ Cannot activate user {email} from status '{status}'. "
                    f"Only PROVISIONED or STAGED users can be activated.")

        client.post(f"/api/v1/users/{user_id}/lifecycle/activate",
                    params={"sendEmail": str(send_email).lower()}, data={})

        return (f"✅ User {email} activated successfully.\n"
                f"  Previous status: {status} → ACTIVE\n"
                f"  Activated by: {caller}\n"
                f"  Email sent: {send_email}")

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error activating user: {str(e)}"


@mcp.tool()
def reactivate_user(user_id: str, ctx: Context = None) -> str:
    """Reactivate a DEPROVISIONED user (undo deactivation)."""
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Reactivating user: {user_id}")
    client = get_client()

    try:
        user = client.get(f"/api/v1/users/{user_id}")
        status = user.get("status")
        email = user.get("profile", {}).get("email")

        if status == "ACTIVE":
            return f"✅ User {email} is already ACTIVE."

        if status != "DEPROVISIONED":
            return (f"❌ Cannot reactivate user {email} from status '{status}'. "
                    f"Only DEPROVISIONED users can be reactivated.")

        client.post(f"/api/v1/users/{user_id}/lifecycle/reactivate", data={})

        logger.warning(f"AUDIT: User reactivation | caller={caller} | target={email} | id={user_id}")

        return (f"✅ User {email} reactivated successfully.\n"
                f"  Previous status: DEPROVISIONED → ACTIVE\n"
                f"  Reactivated by: {caller}")

    except PermissionError as e:
        return f"❌ Permission denied: {str(e)}"
    except Exception as e:
        return f"❌ Error reactivating user: {str(e)}"