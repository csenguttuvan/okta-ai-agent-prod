from typing import Optional, Dict, Any, List
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client
from okta_mcp_server.context import get_caller_email, get_caller_groups



@mcp.tool()
def list_applications(
    ctx: Context | None = None,
    limit: int = 20,
    after: Optional[str] = None,
    filter: Optional[str] = None
) -> Dict[str, Any]:
    """List all applications in the Okta organization.

    Args:
        limit: Maximum number of applications to return (default 20)
        after: Pagination cursor for next page
        filter: Filter expression (e.g., 'status eq "ACTIVE"')

    Returns:
        Dict containing list of applications
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing applications limit={limit}")

    params = {"limit": limit}
    if after:
        params["after"] = after
    if filter:
        params["filter"] = filter

    try:
        client = get_client()
        apps = client.get("/api/v1/apps", params=params)
        logger.info(f"[caller={caller}] Found {len(apps)} applications")
        return {
            "applications": apps,
            "count": len(apps)
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing applications: {str(e)}")
        raise

@mcp.tool()
def get_application(
    ctx: Context | None = None,
    app_id: str = ""
) -> Optional[Dict[str, Any]]:
    """Get details of a specific application by ID.

    Args:
        app_id: The Okta application ID

    Returns:
        Dict containing application details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Getting application: {app_id}")

    if not app_id:
        logger.error(f"[caller={caller}] app_id is required")
        raise ValueError("app_id is required")

    try:
        client = get_client()
        app = client.get(f"/api/v1/apps/{app_id}")
        logger.info(f"[caller={caller}] Retrieved application: {app.get('label', 'N/A')}")
        return app
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error getting application: {str(e)}")
        raise

@mcp.tool()
def list_application_users(
    ctx: Context | None = None,
    app_id: str = "",
    limit: int = 50
) -> Dict[str, Any]:
    """List users assigned to an application.

    Args:
        app_id: The Okta application ID
        limit: Maximum number of users to return

    Returns:
        Dict containing list of assigned users
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing users for application: {app_id}")

    if not app_id:
        logger.error(f"[caller={caller}] app_id is required")
        raise ValueError("app_id is required")

    params = {"limit": limit}

    try:
        client = get_client()
        users = client.get(f"/api/v1/apps/{app_id}/users", params=params)
        logger.info(f"[caller={caller}] Found {len(users)} users for application {app_id}")
        return {
            "users": users,
            "count": len(users),
            "app_id": app_id
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing application users: {str(e)}")
        raise

@mcp.tool()
def list_application_groups(
    ctx: Context | None = None,
    app_id: str = "",
    limit: int = 50
) -> Dict[str, Any]:
    """List groups assigned to an application.

    Args:
        app_id: The Okta application ID
        limit: Maximum number of groups to return

    Returns:
        Dict containing list of assigned groups
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing groups for application: {app_id}")

    if not app_id:
        logger.error(f"[caller={caller}] app_id is required")
        raise ValueError("app_id is required")

    params = {"limit": limit}

    try:
        client = get_client()
        groups = client.get(f"/api/v1/apps/{app_id}/groups", params=params)
        logger.info(f"[caller={caller}] Found {len(groups)} groups for application {app_id}")
        return {
            "groups": groups,
            "count": len(groups),
            "app_id": app_id
        }
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error listing application groups: {str(e)}")
        raise

@mcp.tool()
def assign_user_to_application(
    ctx: Context | None = None,
    app_id: str = "",
    user_id: str = ""
) -> Dict[str, Any]:
    """Assign a user to an application.

    Args:
        app_id: The Okta application ID
        user_id: The Okta user ID

    Returns:
        Dict with assignment details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Assigning user {user_id} to application {app_id}")

    if not app_id or not user_id:
        logger.error(f"[caller={caller}] app_id and user_id are required")
        raise ValueError("app_id and user_id are required")

    try:
        client = get_client()
        assignment = client.post(
            f"/api/v1/apps/{app_id}/users",
            data={"id": user_id}
        )
        logger.info(f"[caller={caller}] Assigned user {user_id} to application {app_id}")
        return assignment
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error assigning user to application: {str(e)}")
        raise

@mcp.tool()
def assign_group_to_application(
    ctx: Context | None = None,
    app_id: str = "",
    group_id: str = ""
) -> Dict[str, Any]:
    """Assign a group to an application.

    Args:
        app_id: The Okta application ID
        group_id: The Okta group ID

    Returns:
        Dict with assignment details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Assigning group {group_id} to application {app_id}")

    if not app_id or not group_id:
        logger.error(f"[caller={caller}] app_id and group_id are required")
        raise ValueError("app_id and group_id are required")

    try:
        client = get_client()
        assignment = client.put(
            f"/api/v1/apps/{app_id}/groups/{group_id}",
            data={}
        )
        logger.info(f"[caller={caller}] Assigned group {group_id} to application {app_id}")
        return assignment
    except PermissionError as e:
        logger.error(f"[caller={caller}] Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] Error assigning group to application: {str(e)}")
        raise


@mcp.tool()
def create_application(
    label: str,
    sign_on_mode: str,
    url: str = "",
    ctx: Context | None = None,
    app_settings: Optional[Dict[str, Any]] = None,
    redirect_uris: Optional[list] = None,
    grant_types: Optional[list] = None,
    response_types: Optional[list] = None,
    application_type: str = "web",
    activate: bool = True
) -> Dict[str, Any]:
    """Create a new Okta application (requires okta.apps.manage scope).
    
    IMPORTANT: This tool creates basic applications. SAML apps require additional 
    configuration via the Okta UI after creation (ACS URL, Entity ID, certificates).
    
    Args:
        label: Display name for the application (REQUIRED - always ask user)
        sign_on_mode: Authentication mode (REQUIRED - ask user to choose):
                      - BOOKMARK: Simple link to external URL (requires url parameter)
                      - OPENID_CONNECT: OAuth/OIDC app (requires redirect_uris)
                      - SAML_2_0: SAML SSO application (basic creation only)
                      - BROWSER_PLUGIN: Browser plugin app
                      - BASIC_AUTH: Basic authentication app
        url: The URL for BOOKMARK applications (REQUIRED if sign_on_mode is BOOKMARK)
        app_settings: Additional application settings (optional)
        redirect_uris: List of callback URLs (REQUIRED for OPENID_CONNECT apps)
        grant_types: OAuth grant types for OIDC (default: ["authorization_code"])
        response_types: OAuth response types for OIDC (default: ["code"])
        application_type: Type of OIDC app - "web", "native", "browser", or "service" (default: "web")
        activate: Whether to activate immediately (default: True)
    
    Required Fields by Application Type:
        BOOKMARK: label + sign_on_mode + url
        OPENID_CONNECT: label + sign_on_mode + redirect_uris
        SAML_2_0: label + sign_on_mode (NOTE: Requires additional UI configuration)
    
    Returns:
        Dict containing the created application details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Creating application: {label} (mode={sign_on_mode})")
    
    # Validate required parameters
    if not label or not sign_on_mode:
        error_msg = "Both 'label' and 'sign_on_mode' are required. Please ask the user for these values."
        logger.error(f"[caller={caller}] {error_msg}")
        raise ValueError(error_msg)
    
    # Validate sign_on_mode
    valid_modes = ["BOOKMARK", "OPENID_CONNECT", "SAML_2_0", "BROWSER_PLUGIN", "BASIC_AUTH", "WS_FEDERATION"]
    if sign_on_mode not in valid_modes:
        error_msg = f"Invalid sign_on_mode '{sign_on_mode}'. Must be one of: {', '.join(valid_modes)}"
        logger.error(f"[caller={caller}] {error_msg}")
        raise ValueError(error_msg)
    
    # Build application payload
    app_data = {
        "label": label,
        "signOnMode": sign_on_mode
    }
    
    # Handle BOOKMARK-specific configuration
    if sign_on_mode == "BOOKMARK":
        if not url:
            error_msg = "BOOKMARK applications require a 'url' parameter. Please ask the user for the application URL."
            logger.error(f"[caller={caller}] {error_msg}")
            raise ValueError(error_msg)
        
        app_data["name"] = "bookmark"  # Required for BOOKMARK apps
        app_data["settings"] = {
            "app": {
                "url": url,
                "requestIntegration": False
            }
        }
        logger.info(f"[caller={caller}] BOOKMARK config: url={url}")
    
    # Handle OIDC-specific configuration
    elif sign_on_mode == "OPENID_CONNECT":
        if not redirect_uris and application_type != "service":
            error_msg = "OPENID_CONNECT applications require 'redirect_uris'. Please ask the user for callback URLs."
            logger.error(f"[caller={caller}] {error_msg}")
            raise ValueError(error_msg)
        
        app_data["name"] = "oidc_client"  # Required for custom OIDC apps
        
        # Set defaults for OIDC
        if grant_types is None:
            grant_types = ["authorization_code"] if application_type != "service" else ["client_credentials"]
        if response_types is None:
            response_types = ["code"]
        
        app_data["credentials"] = {
            "oauthClient": {
                "token_endpoint_auth_method": "client_secret_basic"
            }
        }
        
        app_data["settings"] = {
            "oauthClient": {
                "redirect_uris": redirect_uris or [],
                "grant_types": grant_types,
                "response_types": response_types,
                "application_type": application_type
            }
        }
        
        logger.info(f"[caller={caller}] OIDC config: grant_types={grant_types}, app_type={application_type}")
    
    # Handle SAML_2_0 - basic creation only
    elif sign_on_mode == "SAML_2_0":
        # SAML apps need minimal config for API creation
        # Full SAML config (ACS URL, Entity ID, certs) must be done via UI
        logger.warning(f"[caller={caller}] Creating basic SAML app - additional configuration required via Okta UI")
        # Note: No "name" field needed for basic SAML app creation
        # It will be auto-assigned by Okta
    
    # Handle other app types with custom settings
    elif app_settings:
        app_data["settings"] = {
            "app": app_settings
        }
    
    # Build endpoint with activate parameter
    endpoint = f"/api/v1/apps?activate={str(activate).lower()}"
    
    try:
        client = get_client()
        app = client.post(endpoint, data=app_data)
        
        app_id = app.get("id", "N/A")
        app_label = app.get("label", "N/A")
        
        # Build result
        result = {
            "success": True,
            "application": app,
            "id": app_id,
            "label": app_label,
            "status": app.get("status", "UNKNOWN"),
            "sign_on_mode": sign_on_mode
        }
        
        # Add type-specific info and warnings to response
        if sign_on_mode == "OPENID_CONNECT":
            oauth_client = app.get("credentials", {}).get("oauthClient", {})
            result["client_id"] = oauth_client.get("client_id")
            result["client_secret"] = oauth_client.get("client_secret")
            logger.info(f"[caller={caller}] ✅ Created OIDC app '{app_label}' (client_id: {result.get('client_id')})")
        elif sign_on_mode == "BOOKMARK":
            bookmark_url = app.get("settings", {}).get("app", {}).get("url")
            result["url"] = bookmark_url
            logger.info(f"[caller={caller}] ✅ Created BOOKMARK app '{app_label}' (URL: {bookmark_url})")
        elif sign_on_mode == "SAML_2_0":
            result["warning"] = "SAML app created but requires additional configuration in Okta UI (ACS URL, Entity ID, certificates)"
            logger.info(f"[caller={caller}] ✅ Created SAML app '{app_label}' (ID: {app_id}) - UI configuration required")
        else:
            logger.info(f"[caller={caller}] ✅ Created application '{app_label}' (ID: {app_id})")
        
        return result
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error creating application: {str(e)}")
        raise


@mcp.tool()
def batch_assign_users_to_application(
    app_id: str,
    user_ids: list[str],
    ctx: Context | None = None
) -> Dict[str, Any]:
    """Assign multiple users to an application in batch.
    
    Args:
        app_id: The Okta application ID
        user_ids: List of Okta user IDs to assign to the application
    
    Returns:
        Dict with batch assignment results including success/failure counts
    
    Example:
        batch_assign_users_to_application(
            app_id="0oa123abc",
            user_ids=["00u111", "00u222", "00u333"]
        )
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Batch assigning {len(user_ids)} users to application {app_id}")
    
    if not app_id or not user_ids:
        error_msg = "Both app_id and user_ids are required"
        logger.error(f"[caller={caller}] {error_msg}")
        raise ValueError(error_msg)
    
    try:
        client = get_client()
        results = []
        errors = []
        
        for user_id in user_ids:
            try:
                assignment = client.post(
                    f"/api/v1/apps/{app_id}/users",
                    data={"id": user_id}
                )
                results.append({
                    "user_id": user_id,
                    "status": "assigned",
                    "assignment_id": assignment.get("id")
                })
                logger.info(f"[caller={caller}] ✅ Assigned user {user_id} to app {app_id}")
                
            except Exception as e:
                error_msg = str(e)
                # Check if already assigned (409 conflict)
                if "already exists" in error_msg.lower() or "409" in error_msg:
                    results.append({
                        "user_id": user_id,
                        "status": "already_assigned"
                    })
                    logger.info(f"[caller={caller}] ℹ️ User {user_id} already assigned to app")
                else:
                    errors.append({
                        "user_id": user_id,
                        "error": error_msg
                    })
                    logger.error(f"[caller={caller}] ❌ Failed to assign user {user_id}: {error_msg}")
        
        assigned_count = len([r for r in results if r["status"] == "assigned"])
        already_assigned_count = len([r for r in results if r["status"] == "already_assigned"])
        
        logger.info(f"[caller={caller}] ✅ Completed: {assigned_count} assigned, {already_assigned_count} already assigned, {len(errors)} errors")
        
        return {
            "success": True,
            "message": f"Assigned {assigned_count} users to application",
            "total_requested": len(user_ids),
            "assigned": assigned_count,
            "already_assigned": already_assigned_count,
            "errors": len(errors),
            "results": results,
            "error_details": errors if errors else None,
            "app_id": app_id
        }
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error in batch assignment: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "total_requested": len(user_ids),
            "assigned": 0
        } 
    
@mcp.tool()
def assign_user_to_application_with_role(
    app_id: str,
    user_id: str,
    role: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    ctx: Context | None = None
) -> Dict[str, Any]:
    """Assign a user to an application with a specific role or profile attributes.
    
    This is particularly useful for applications like AWS where you need to assign
    users to specific IAM roles imported from AWS via SAML.
    
    Args:
        app_id: The Okta application ID
        user_id: The Okta user ID or login email
        role: The role to assign (e.g., for AWS: "arn:aws:iam::123456789012:role/AdminRole,arn:aws:iam::123456789012:saml-provider/OktaProvider")
        profile: Dict of additional profile attributes to set for this app assignment
                 Example: {"samlRoles": ["role1", "role2"], "customAttribute": "value"}
        
    Returns:
        Dict with assignment details including the assigned role
        
    Examples:
        # Assign user to AWS app with specific IAM role
        assign_user_to_application_with_role(
            app_id="0oa123abc",
            user_id="john.doe@example.com",
            role="arn:aws:iam::123456789012:role/AdminRole,arn:aws:iam::123456789012:saml-provider/OktaProvider"
        )
        
        # Assign with custom profile attributes
        assign_user_to_application_with_role(
            app_id="0oa123abc",
            user_id="jane.doe@example.com",
            profile={"department": "Engineering", "customRole": "Developer"}
        )
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Assigning user {user_id} to app {app_id} with role: {role}")
    
    if not app_id or not user_id:
        error_msg = "Both app_id and user_id are required"
        logger.error(f"[caller={caller}] {error_msg}")
        raise ValueError(error_msg)
    
    try:
        client = get_client()
        
        # Build the assignment payload
        assignment_data = {
            "id": user_id
        }
        
        # Add profile data if role or custom profile provided
        if role or profile:
            profile_data = profile.copy() if profile else {}
            
            # Add role to profile if provided
            if role:
                # For AWS apps, the role field is typically "samlRoles" (array)
                # But some apps use "role" (string). We'll support both patterns.
                if isinstance(role, list):
                    profile_data["samlRoles"] = role
                else:
                    # Single role - try to detect if it's AWS format
                    if "arn:aws:iam::" in role:
                        profile_data["samlRoles"] = [role]
                    else:
                        profile_data["role"] = role
            
            assignment_data["profile"] = profile_data
            logger.info(f"[caller={caller}] Profile data: {profile_data}")
        
        # Assign user to application
        assignment = client.post(
            f"/api/v1/apps/{app_id}/users",
            data=assignment_data
        )
        
        assigned_profile = assignment.get("profile", {})
        logger.info(f"[caller={caller}] ✅ Assigned user {user_id} to app {app_id}")
        
        return {
            "success": True,
            "user_id": user_id,
            "app_id": app_id,
            "assignment_id": assignment.get("id"),
            "profile": assigned_profile,
            "role": assigned_profile.get("samlRoles") or assigned_profile.get("role"),
            "message": f"User {user_id} assigned to application with role/profile"
        }
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[caller={caller}] ❌ Error assigning user with role: {error_msg}")
        
        # Provide helpful error message for common issues
        if "400" in error_msg:
            raise ValueError(f"Invalid role or profile format. Check app profile schema: {error_msg}")
        raise



@mcp.tool()
def update_user_application_role(
    app_id: str,
    user_id: str,
    role: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    ctx: Context | None = None
) -> Dict[str, Any]:
    """Update the role or profile for a user already assigned to an application.
    
    Use this to change AWS IAM roles or other app-specific attributes for existing assignments.
    
    Args:
        app_id: The Okta application ID
        user_id: The Okta user ID or login email
        role: The new role to assign (e.g., AWS IAM role ARN)
        profile: Dict of profile attributes to update
        
    Returns:
        Dict with updated assignment details
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Updating role for user {user_id} in app {app_id}")
    
    if not app_id or not user_id:
        error_msg = "Both app_id and user_id are required"
        logger.error(f"[caller={caller}] {error_msg}")
        raise ValueError(error_msg)
    
    try:
        client = get_client()
        
        # Build profile update
        profile_data = profile.copy() if profile else {}
        
        if role:
            if isinstance(role, list):
                profile_data["samlRoles"] = role
            else:
                if "arn:aws:iam::" in role:
                    profile_data["samlRoles"] = [role]
                else:
                    profile_data["role"] = role
        
        # Update the application user profile
        updated = client.post(
            f"/api/v1/apps/{app_id}/users/{user_id}",
            data={"profile": profile_data}
        )
        
        logger.info(f"[caller={caller}] ✅ Updated role for user {user_id} in app {app_id}")
        
        return {
            "success": True,
            "user_id": user_id,
            "app_id": app_id,
            "profile": updated.get("profile", {}),
            "role": updated.get("profile", {}).get("samlRoles") or updated.get("profile", {}).get("role"),
            "message": "User application role updated successfully"
        }
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error updating user role: {str(e)}")
        raise


@mcp.tool()
def list_application_available_roles(
    app_id: str,
    ctx: Context | None = None
) -> Dict[str, Any]:
    """List all available/importable roles defined for an application.
    
    For AWS apps, this returns all IAM roles that have been imported from AWS into Okta.
    For other SAML apps, this returns the role options configured in the app settings.
    These are the roles you can assign to users.
    
    Args:
        app_id: The Okta application ID
        
    Returns:
        Dict containing available roles that can be assigned to users
        
    Example for AWS app:
        {
            "available_roles": [
                "arn:aws:iam::123456789012:role/AdminRole,arn:aws:iam::123456789012:saml-provider/Okta",
                "arn:aws:iam::123456789012:role/DeveloperRole,arn:aws:iam::123456789012:saml-provider/Okta",
                "arn:aws:iam::123456789012:role/ReadOnlyRole,arn:aws:iam::123456789012:saml-provider/Okta"
            ],
            "role_count": 3,
            "app_name": "AWS Account",
            "aws_account_id": "123456789012"
        }
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Listing available roles for app: {app_id}")
    
    if not app_id:
        error_msg = "app_id is required"
        logger.error(f"[caller={caller}] {error_msg}")
        raise ValueError(error_msg)
    
    try:
        client = get_client()
        
        # Get the full application details
        app = client.get(f"/api/v1/apps/{app_id}")
        
        app_name = app.get("label", "Unknown")
        app_settings = app.get("settings", {})
        app_config = app_settings.get("app", {})
        sign_on_settings = app_settings.get("signOn", {})
        
        available_roles = []
        role_source = "unknown"
        additional_info = {}
        
        # Check for AWS-specific role configuration
        if "identityProviderArn" in app_config:
            # This is an AWS app
            role_source = "aws"
            
            # Extract AWS account ID and provider ARN
            idp_arn = app_config.get("identityProviderArn", "")
            if "arn:aws:iam::" in idp_arn:
                # Parse: arn:aws:iam::123456789012:saml-provider/ProviderName
                parts = idp_arn.split(":")
                if len(parts) >= 5:
                    aws_account_id = parts[4]
                    additional_info["aws_account_id"] = aws_account_id
                    additional_info["identity_provider_arn"] = idp_arn
            
            # AWS roles are stored in app config - check multiple possible locations
            # Option 1: groupFilter (role ARNs in filter)
            group_filter = app_config.get("groupFilter")
            if group_filter:
                additional_info["group_filter"] = group_filter
            
            # Option 2: roleValuePattern (for role mapping)
            role_pattern = app_config.get("roleValuePattern")
            if role_pattern:
                additional_info["role_value_pattern"] = role_pattern
            
            # Option 3: Get from app schema to see configured role options
            try:
                schema = client.get(f"/api/v1/meta/schemas/apps/{app_id}/default")
                custom_props = schema.get("definitions", {}).get("custom", {}).get("properties", {})
                
                # Check for samlRoles enum (predefined role list)
                if "samlRoles" in custom_props:
                    saml_roles_def = custom_props["samlRoles"]
                    items_def = saml_roles_def.get("items", {})
                    
                    # Check for enum values (predefined list of roles)
                    if "enum" in items_def:
                        available_roles = items_def["enum"]
                        role_source = "aws_schema_enum"
                    # Check for oneOf pattern
                    elif "oneOf" in items_def:
                        available_roles = [item.get("const") or item.get("title") 
                                         for item in items_def["oneOf"] if item.get("const") or item.get("title")]
                        role_source = "aws_schema_oneof"
            except Exception as schema_error:
                logger.warning(f"[caller={caller}] Could not fetch schema: {str(schema_error)}")
            
            # Option 4: Parse from existing user assignments if roles aren't in schema
            if not available_roles:
                try:
                    users = client.get(f"/api/v1/apps/{app_id}/users", params={"limit": 200})
                    role_set = set()
                    for user in users:
                        saml_roles = user.get("profile", {}).get("samlRoles", [])
                        role_set.update(saml_roles)
                    available_roles = sorted(list(role_set))
                    role_source = "aws_inferred_from_assignments"
                except Exception as user_error:
                    logger.warning(f"[caller={caller}] Could not infer roles from users: {str(user_error)}")
        
        # Check for SAML app role configuration (non-AWS)
        elif app.get("signOnMode") == "SAML_2_0":
            role_source = "saml"
            
            # Check schema for role enum values
            try:
                schema = client.get(f"/api/v1/meta/schemas/apps/{app_id}/default")
                custom_props = schema.get("definitions", {}).get("custom", {}).get("properties", {})
                
                # Look for role or samlRoles fields with enum
                for field_name in ["samlRoles", "role", "roles"]:
                    if field_name in custom_props:
                        field_def = custom_props[field_name]
                        
                        # Array type with enum items
                        if field_def.get("type") == "array":
                            items = field_def.get("items", {})
                            if "enum" in items:
                                available_roles = items["enum"]
                                role_source = f"saml_schema_{field_name}"
                                break
                        # String type with enum
                        elif "enum" in field_def:
                            available_roles = field_def["enum"]
                            role_source = f"saml_schema_{field_name}"
                            break
            except Exception as schema_error:
                logger.warning(f"[caller={caller}] Could not fetch SAML schema: {str(schema_error)}")
            
            # Fallback: infer from existing assignments
            if not available_roles:
                try:
                    users = client.get(f"/api/v1/apps/{app_id}/users", params={"limit": 200})
                    role_set = set()
                    for user in users:
                        profile = user.get("profile", {})
                        # Check various role fields
                        if profile.get("samlRoles"):
                            role_set.update(profile["samlRoles"])
                        elif profile.get("role"):
                            role_set.add(profile["role"])
                        elif profile.get("roles"):
                            if isinstance(profile["roles"], list):
                                role_set.update(profile["roles"])
                            else:
                                role_set.add(profile["roles"])
                    available_roles = sorted(list(role_set))
                    role_source = "saml_inferred_from_assignments"
                except Exception:
                    pass
        
        # For other app types, check schema
        else:
            try:
                schema = client.get(f"/api/v1/meta/schemas/apps/{app_id}/default")
                custom_props = schema.get("definitions", {}).get("custom", {}).get("properties", {})
                
                for field_name, field_def in custom_props.items():
                    if "role" in field_name.lower():
                        if field_def.get("type") == "array" and "enum" in field_def.get("items", {}):
                            available_roles = field_def["items"]["enum"]
                            role_source = f"schema_{field_name}"
                            break
                        elif "enum" in field_def:
                            available_roles = field_def["enum"]
                            role_source = f"schema_{field_name}"
                            break
            except Exception:
                pass
        
        logger.info(f"[caller={caller}] Found {len(available_roles)} available roles (source: {role_source})")
        
        result = {
            "success": True,
            "app_id": app_id,
            "app_name": app_name,
            "sign_on_mode": app.get("signOnMode"),
            "available_roles": available_roles,
            "role_count": len(available_roles),
            "role_source": role_source,
            **additional_info
        }
        
        # Add helpful message based on what we found
        if not available_roles:
            result["message"] = (
                "No roles found. This could mean: "
                "(1) No roles have been imported/configured for this app, "
                "(2) Roles are dynamically assigned without predefined options, or "
                "(3) No users have been assigned yet to infer roles from."
            )
            if role_source == "aws":
                result["message"] += " For AWS apps, you may need to import roles from AWS in the Okta admin UI."
        else:
            result["message"] = f"Found {len(available_roles)} available role(s) that can be assigned to users"
        
        return result
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error listing application roles: {str(e)}")
        raise

