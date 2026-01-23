from typing import Any, Dict, Optional
from loguru import logger
from mcp.server.fastmcp import Context

from okta_mcp_server.mcp_instance import mcp
from okta_mcp_server.oauth_jwt_client import get_client

def get_caller_email(ctx: Context | None) -> str:
    """Extract user email from context metadata"""
    if not ctx:
        return "unknown"

    # Try to get from request context meta (when using gateway)
    if hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'meta'):
        meta = ctx.request_context.meta
        if isinstance(meta, dict):
            return meta.get('user_email', 'unknown')

    # Fallback to environment variable (for non-gateway usage)
    import os
    return os.getenv('USER_EMAIL', 'unknown')

@mcp.tool()
def list_policies(
    ctx: Context | None = None,
    type: str = "",
    limit: Optional[int] = 20,
    status: Optional[str] = None,
    q: Optional[str] = None,
    after: Optional[str] = None
) -> Dict[str, Any]:
    """List all the policies from the Okta organization.

    Parameters:
        type (str, required): Specifies the type of policy to return. Available policy types 
            are: OKTA_SIGN_ON, PASSWORD, MFA_ENROLL, IDP_DISCOVERY, ACCESS_POLICY, 
            PROFILE_ENROLLMENT, POST_AUTH_SESSION, ENTITY_RISK
        status (str, optional): Refines the query by the status of the policy - ACTIVE or INACTIVE.
        q (str, optional): A query string to search policies by name.
        limit (int, optional): Number of results to return (min 20, max 100).
        after (str, optional): Specifies the pagination cursor for the next page of policies.

    Returns:
        Dict containing:
            - policies (List[Dict]): List of policy dictionaries, each containing policy details
            - error (str): Error message if the operation fails
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Listing policies from Okta organization")
    logger.debug(f"[caller={caller}] Type: {type}, Status: {status}, Q: {q}, limit: {limit}")

    # Validate limit parameter range
    if limit is not None:
        if limit < 20:
            logger.warning(f"[caller={caller}] Limit {limit} is below minimum 20, setting to 20")
            limit = 20
        elif limit > 100:
            logger.warning(f"[caller={caller}] Limit {limit} exceeds maximum 100, setting to 100")
            limit = 100

    if not type:
        logger.error(f"[caller={caller}] type parameter is required")
        return {"error": "type parameter is required"}

    try:
        client = get_client()
        params = {"type": type, "limit": limit}
        if status:
            params["status"] = status
        if q:
            params["q"] = q
        if after:
            params["after"] = after

        logger.debug(f"[caller={caller}] Calling Okta API to list policies")
        policies = client.get("/api/v1/policies", params=params)

        if not policies:
            logger.info(f"[caller={caller}] No policies found")
            return {"policies": []}

        logger.info(f"[caller={caller}] Successfully retrieved {len(policies)} policies")
        return {"policies": policies}
    except Exception as e:
        logger.error(f"[caller={caller}] Exception listing policies: {e}")
        return {"error": str(e)}

@mcp.tool()
def get_policy(
    ctx: Context | None = None,
    policy_id: str = ""
) -> Optional[Dict[str, Any]]:
    """Retrieve a specific policy by ID.

    Parameters:
        policy_id (str, required): The ID of the policy to retrieve.

    Returns:
        Dict containing the policy details.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Getting policy: {policy_id}")

    if not policy_id:
        logger.error(f"[caller={caller}] policy_id is required")
        return {"error": "policy_id is required"}

    try:
        client = get_client()
        policy = client.get(f"/api/v1/policies/{policy_id}")
        logger.info(f"[caller={caller}] Successfully retrieved policy {policy_id}")
        return policy
    except Exception as e:
        logger.error(f"[caller={caller}] Exception getting policy: {e}")
        return {"error": str(e)}

@mcp.tool()
def create_policy(
    ctx: Context | None = None,
    policy_data: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """Create a new policy.

    Parameters:
        policy_data (dict, required): The policy configuration containing:
            - type (str, required): Policy type (OKTA_SIGN_ON, PASSWORD, MFA_ENROLL, 
              ACCESS_POLICY, PROFILE_ENROLLMENT, POST_AUTH_SESSION, ENTITY_RISK, 
              DEVICE_SIGNAL_COLLECTION)
            - name (str, required): Policy name
            - description (str, optional): Policy description
            - status (str, optional): ACTIVE or INACTIVE (default ACTIVE)
            - priority (int, optional): Priority of the policy
            - conditions (dict, optional): Policy conditions
            - settings (dict, optional): Policy-specific settings

    Returns:
        Dict containing the created policy details.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Creating policy")

    if not policy_data:
        logger.error(f"[caller={caller}] policy_data is required")
        return {"error": "policy_data is required"}

    try:
        client = get_client()
        policy = client.post("/api/v1/policies", data=policy_data)
        logger.info(f"[caller={caller}] Created policy: {policy.get('id', 'N/A')}")
        return policy
    except Exception as e:
        logger.error(f"[caller={caller}] Exception creating policy: {e}")
        return {"error": str(e)}

@mcp.tool()
def update_policy(
    ctx: Context | None = None,
    policy_id: str = "",
    policy_data: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """Update an existing policy.

    Parameters:
        policy_id (str, required): The ID of the policy to update.
        policy_data (dict, required): The updated policy configuration.

    Returns:
        Dict containing the updated policy details.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Updating policy: {policy_id}")

    if not policy_id or not policy_data:
        logger.error(f"[caller={caller}] policy_id and policy_data are required")
        return {"error": "policy_id and policy_data are required"}

    try:
        client = get_client()
        policy = client.put(f"/api/v1/policies/{policy_id}", data=policy_data)
        logger.info(f"[caller={caller}] Updated policy: {policy_id}")
        return policy
    except Exception as e:
        logger.error(f"[caller={caller}] Exception updating policy: {e}")
        return {"error": str(e)}



@mcp.tool()
def list_policy_rules(
    ctx: Context | None = None,
    policy_id: str = ""
) -> Dict[str, Any]:
    """List all rules for a specific policy.

    Parameters:
        policy_id (str, required): The ID of the policy.

    Returns:
        Dict containing:
            - rules (List[Dict]): List of policy rule dictionaries
            - error (str): Error message if the operation fails
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Listing rules for policy: {policy_id}")

    if not policy_id:
        logger.error(f"[caller={caller}] policy_id is required")
        return {"error": "policy_id is required"}

    try:
        client = get_client()
        rules = client.get(f"/api/v1/policies/{policy_id}/rules")

        if not rules:
            logger.info(f"[caller={caller}] No policy rules found")
            return {"rules": []}

        logger.info(f"[caller={caller}] Successfully retrieved {len(rules)} rules")
        return {"rules": rules}
    except Exception as e:
        logger.error(f"[caller={caller}] Exception listing policy rules: {e}")
        return {"error": str(e)}

@mcp.tool()
def get_policy_rule(
    ctx: Context | None = None,
    policy_id: str = "",
    rule_id: str = ""
) -> Optional[Dict[str, Any]]:
    """Retrieve a specific policy rule.

    Parameters:
        policy_id (str, required): The ID of the policy.
        rule_id (str, required): The ID of the rule.

    Returns:
        Dict containing the policy rule details.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Getting policy rule: {rule_id} from policy: {policy_id}")

    if not policy_id or not rule_id:
        logger.error(f"[caller={caller}] policy_id and rule_id are required")
        return {"error": "policy_id and rule_id are required"}

    try:
        client = get_client()
        rule = client.get(f"/api/v1/policies/{policy_id}/rules/{rule_id}")
        logger.info(f"[caller={caller}] Successfully retrieved rule {rule_id}")
        return rule
    except Exception as e:
        logger.error(f"[caller={caller}] Exception getting policy rule: {e}")
        return {"error": str(e)}
    


@mcp.tool()
def reset_user_mfa_and_password(
    user_id: str,
    revoke_sessions: bool = True,
    ctx: Context = None
) -> dict:
    """Reset user's MFA factors and password, returning a temporary password.
    
    Only ACTIVE users can have their MFA and password reset.
    
    This tool performs two operations:
    1. Resets all MFA factors for the user (requires re-enrollment)
    2. Expires password and generates a temporary password
    
    Args:
        user_id: The Okta user ID or login email
        revoke_sessions: If True, signs user out of all sessions (default: True)
        ctx: Optional context
        
    Returns:
        Dict containing temporary password and operation status
        
    Requires: okta.users.manage scope
    """
    caller = get_caller_email()
    logger.info(f"[caller={caller}] Resetting MFA and password for user: {user_id}")
    
    client = get_client()
    
    # Validate user is ACTIVE
    is_active, error_msg, user = _validate_user_is_active(client, user_id, caller)
    
    if not is_active:
        logger.error(f"[caller={caller}] ❌ Cannot reset credentials: {error_msg}")
        return {
            "success": False,
            "user_id": user_id,
            "user_status": user.get("status"),
            "error": error_msg,
            "message": "Only ACTIVE users can have their MFA and password reset"
        }
    
    results = {
        "user_id": user_id,
        "success": False,
        "mfa_reset": False,
        "password_reset": False,
        "temp_password": None,
        "sessions_revoked": revoke_sessions
    }
    
    try:
        # Step 1: Reset all MFA factors
        try:
            client.post(f"/api/v1/users/{user_id}/lifecycle/reset_factors", data={})
            results["mfa_reset"] = True
            logger.info(f"[caller={caller}] ✅ MFA factors reset for user: {user_id}")
        except Exception as mfa_error:
            logger.error(f"[caller={caller}] ❌ Failed to reset MFA: {str(mfa_error)}")
            results["mfa_error"] = str(mfa_error)
        
        # Step 2: Expire password and get temporary password
        try:
            response = client.post(
                f"/api/v1/users/{user_id}/lifecycle/expire_password",
                params={"tempPassword": "true", "revokeSessions": str(revoke_sessions).lower()},
                data={}
            )
            
            temp_password = response.get("tempPassword")
            results["password_reset"] = True
            results["temp_password"] = temp_password
            logger.info(f"[caller={caller}] ✅ Password reset with temp password for user: {user_id}")
        except Exception as pwd_error:
            logger.error(f"[caller={caller}] ❌ Failed to reset password: {str(pwd_error)}")
            results["password_error"] = str(pwd_error)
        
        # Overall success if at least one operation succeeded
        results["success"] = results["mfa_reset"] or results["password_reset"]
        
        if results["success"]:
            logger.info(f"[caller={caller}] ✅ Reset completed - MFA: {results['mfa_reset']}, Password: {results['password_reset']}")
            return {
                "success": True,
                "user_id": user_id,
                "user_status": "ACTIVE",
                "temp_password": results["temp_password"],
                "message": "User MFA and password reset successfully. Provide the temporary password to the user.",
                "mfa_reset": results["mfa_reset"],
                "password_reset": results["password_reset"],
                "sessions_revoked": revoke_sessions,
                "next_steps": [
                    "User must sign in with the temporary password",
                    "User will be prompted to set a new password",
                    "User must re-enroll in MFA factors"
                ]
            }
        else:
            raise Exception("Both MFA and password reset operations failed")
            
    except PermissionError as e:
        logger.error(f"[caller={caller}] ❌ Permission denied: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"[caller={caller}] ❌ Error resetting user credentials: {str(e)}")
        return {
            "success": False,
            "user_id": user_id,
            "error": str(e),
            "partial_results": results
        }

