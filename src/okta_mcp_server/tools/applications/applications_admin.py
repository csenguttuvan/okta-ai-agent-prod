from typing import Optional, Dict, Any
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
    ctx: Context | None = None,
    label: str = "",
    sign_on_mode: str = "SAML_2_0",
    app_settings: Optional[Dict[str, Any]] = None,
    # OIDC-specific parameters
    redirect_uris: Optional[list] = None,
    grant_types: Optional[list] = None,
    response_types: Optional[list] = None,
    application_type: str = "web",
    activate: bool = True
) -> Dict[str, Any]:
    """Create a new Okta application (requires okta.apps.manage scope).
    
    Args:
        label: Display name for the application (required)
        sign_on_mode: Authentication mode - SAML_2_0, OPENID_CONNECT, BROWSER_PLUGIN,
                      WS_FEDERATION, BASIC_AUTH, BOOKMARK (default: SAML_2_0)
        app_settings: Application-specific settings dict (optional, for non-OIDC apps)
        redirect_uris: List of redirect URIs (required for OIDC)
        grant_types: List of OAuth grant types (for OIDC, default: ["authorization_code"])
        response_types: List of response types (for OIDC, default: ["code"])
        application_type: OIDC app type - web, native, or browser (default: web)
        activate: Whether to activate the app immediately (default: True)
    
    Returns:
        Dict containing the created application details
    
    Examples:
        # Create OIDC web application:
        create_application(
            label="My Web App",
            sign_on_mode="OPENID_CONNECT",
            redirect_uris=["https://app.example.com/callback"],
            grant_types=["authorization_code"],
            response_types=["code"]
        )
        
        # Create SAML app:
        create_application(label="Enterprise SSO", sign_on_mode="SAML_2_0")
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Creating application: {label} (mode={sign_on_mode})")
    
    if not label:
        logger.error(f"[caller={caller}] label is required")
        raise ValueError("label is required")
    
    # Build application payload
    app_data = {
        "label": label,
        "signOnMode": sign_on_mode
    }
    
    # Handle OIDC-specific configuration
    if sign_on_mode == "OPENID_CONNECT":
        if not redirect_uris and application_type != "service":
            logger.error(f"[caller={caller}] redirect_uris required for OIDC apps (unless service app)")
            raise ValueError("redirect_uris are required for OIDC web/native/browser apps")
        
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
        
        # Extract client credentials for OIDC apps
        result = {
            "success": True,
            "application": app,
            "id": app_id,
            "label": app_label,
            "status": app.get("status", "UNKNOWN")
        }
        
        # Add OIDC client credentials to response
        if sign_on_mode == "OPENID_CONNECT":
            oauth_client = app.get("credentials", {}).get("oauthClient", {})
            result["client_id"] = oauth_client.get("client_id")
            result["client_secret"] = oauth_client.get("client_secret")
            logger.info(f"[caller={caller}] ✅ Created OIDC app '{app_label}' (client_id: {result.get('client_id')})")
        else:
            logger.info(f"[caller={caller}] ✅ Created application '{app_label}' (ID: {app_id})")
        
        return result
        
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error creating application: {str(e)}")
        raise

   