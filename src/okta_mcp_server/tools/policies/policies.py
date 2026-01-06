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
async def list_policies(
    ctx: Context | None = None,
    type: str = "",
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: Optional[int] = 20,
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
        policies = await client.get("/api/v1/policies", params=params)

        if not policies:
            logger.info(f"[caller={caller}] No policies found")
            return {"policies": []}

        logger.info(f"[caller={caller}] Successfully retrieved {len(policies)} policies")
        return {"policies": policies}
    except Exception as e:
        logger.error(f"[caller={caller}] Exception listing policies: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_policy(
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
        policy = await client.get(f"/api/v1/policies/{policy_id}")
        logger.info(f"[caller={caller}] Successfully retrieved policy {policy_id}")
        return policy
    except Exception as e:
        logger.error(f"[caller={caller}] Exception getting policy: {e}")
        return {"error": str(e)}

@mcp.tool()
async def create_policy(
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
        policy = await client.post("/api/v1/policies", data=policy_data)
        logger.info(f"[caller={caller}] Created policy: {policy.get('id', 'N/A')}")
        return policy
    except Exception as e:
        logger.error(f"[caller={caller}] Exception creating policy: {e}")
        return {"error": str(e)}

@mcp.tool()
async def update_policy(
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
        policy = await client.put(f"/api/v1/policies/{policy_id}", data=policy_data)
        logger.info(f"[caller={caller}] Updated policy: {policy_id}")
        return policy
    except Exception as e:
        logger.error(f"[caller={caller}] Exception updating policy: {e}")
        return {"error": str(e)}

@mcp.tool()
async def delete_policy(
    ctx: Context | None = None,
    policy_id: str = ""
) -> Dict[str, Any]:
    """Delete a policy.

    Parameters:
        policy_id (str, required): The ID of the policy to delete.

    Returns:
        Dict with success status.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Deleting policy: {policy_id}")

    if not policy_id:
        logger.error(f"[caller={caller}] policy_id is required")
        return {"error": "policy_id is required"}

    try:
        client = get_client()
        await client.delete(f"/api/v1/policies/{policy_id}")
        logger.info(f"[caller={caller}] Deleted policy: {policy_id}")
        return {
            "success": True,
            "message": f"Policy {policy_id} deleted successfully"
        }
    except Exception as e:
        logger.error(f"[caller={caller}] Exception deleting policy: {e}")
        return {"error": str(e)}

@mcp.tool()
async def activate_policy(
    ctx: Context | None = None,
    policy_id: str = ""
) -> Dict[str, Any]:
    """Activate a policy.

    Parameters:
        policy_id (str, required): The ID of the policy to activate.

    Returns:
        Dict with success status.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Activating policy: {policy_id}")

    if not policy_id:
        logger.error(f"[caller={caller}] policy_id is required")
        return {"error": "policy_id is required"}

    try:
        client = get_client()
        await client.post(f"/api/v1/policies/{policy_id}/lifecycle/activate")
        logger.info(f"[caller={caller}] Activated policy: {policy_id}")
        return {
            "success": True,
            "message": f"Policy {policy_id} activated successfully"
        }
    except Exception as e:
        logger.error(f"[caller={caller}] Exception activating policy: {e}")
        return {"error": str(e)}

@mcp.tool()
async def deactivate_policy(
    ctx: Context | None = None,
    policy_id: str = ""
) -> Dict[str, Any]:
    """Deactivate a policy.

    Parameters:
        policy_id (str, required): The ID of the policy to deactivate.

    Returns:
        Dict with success status.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Deactivating policy: {policy_id}")

    if not policy_id:
        logger.error(f"[caller={caller}] policy_id is required")
        return {"error": "policy_id is required"}

    try:
        client = get_client()
        await client.post(f"/api/v1/policies/{policy_id}/lifecycle/deactivate")
        logger.info(f"[caller={caller}] Deactivated policy: {policy_id}")
        return {
            "success": True,
            "message": f"Policy {policy_id} deactivated successfully"
        }
    except Exception as e:
        logger.error(f"[caller={caller}] Exception deactivating policy: {e}")
        return {"error": str(e)}

@mcp.tool()
async def list_policy_rules(
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
        rules = await client.get(f"/api/v1/policies/{policy_id}/rules")

        if not rules:
            logger.info(f"[caller={caller}] No policy rules found")
            return {"rules": []}

        logger.info(f"[caller={caller}] Successfully retrieved {len(rules)} rules")
        return {"rules": rules}
    except Exception as e:
        logger.error(f"[caller={caller}] Exception listing policy rules: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_policy_rule(
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
        rule = await client.get(f"/api/v1/policies/{policy_id}/rules/{rule_id}")
        logger.info(f"[caller={caller}] Successfully retrieved rule {rule_id}")
        return rule
    except Exception as e:
        logger.error(f"[caller={caller}] Exception getting policy rule: {e}")
        return {"error": str(e)}

@mcp.tool()
async def create_policy_rule(
    ctx: Context | None = None,
    policy_id: str = "",
    rule_data: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """Create a new rule for a policy.

    Parameters:
        policy_id (str, required): The ID of the policy.
        rule_data (dict, required): The rule configuration containing:
            - name (str, required): Rule name
            - priority (int, optional): Priority of the rule
            - status (str, optional): ACTIVE or INACTIVE
            - conditions (dict, optional): Rule conditions
            - actions (dict, optional): Rule actions

    Returns:
        Dict containing the created rule details.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Creating rule for policy: {policy_id}")

    if not policy_id or not rule_data:
        logger.error(f"[caller={caller}] policy_id and rule_data are required")
        return {"error": "policy_id and rule_data are required"}

    try:
        client = get_client()
        rule = await client.post(f"/api/v1/policies/{policy_id}/rules", data=rule_data)
        logger.info(f"[caller={caller}] Created rule: {rule.get('id', 'N/A')}")
        return rule
    except Exception as e:
        logger.error(f"[caller={caller}] Exception creating policy rule: {e}")
        return {"error": str(e)}

@mcp.tool()
async def update_policy_rule(
    ctx: Context | None = None,
    policy_id: str = "",
    rule_id: str = "",
    rule_data: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """Update an existing policy rule.

    Parameters:
        policy_id (str, required): The ID of the policy.
        rule_id (str, required): The ID of the rule to update.
        rule_data (dict, required): The updated rule configuration.

    Returns:
        Dict containing the updated rule details.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Updating rule: {rule_id} in policy: {policy_id}")

    if not policy_id or not rule_id or not rule_data:
        logger.error(f"[caller={caller}] policy_id, rule_id, and rule_data are required")
        return {"error": "policy_id, rule_id, and rule_data are required"}

    try:
        client = get_client()
        rule = await client.put(f"/api/v1/policies/{policy_id}/rules/{rule_id}", data=rule_data)
        logger.info(f"[caller={caller}] Updated rule: {rule_id}")
        return rule
    except Exception as e:
        logger.error(f"[caller={caller}] Exception updating policy rule: {e}")
        return {"error": str(e)}

@mcp.tool()
async def delete_policy_rule(
    ctx: Context | None = None,
    policy_id: str = "",
    rule_id: str = ""
) -> Dict[str, Any]:
    """Delete a policy rule.

    Parameters:
        policy_id (str, required): The ID of the policy.
        rule_id (str, required): The ID of the rule to delete.

    Returns:
        Dict with success status.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Deleting rule: {rule_id} from policy: {policy_id}")

    if not policy_id or not rule_id:
        logger.error(f"[caller={caller}] policy_id and rule_id are required")
        return {"error": "policy_id and rule_id are required"}

    try:
        client = get_client()
        await client.delete(f"/api/v1/policies/{policy_id}/rules/{rule_id}")
        logger.info(f"[caller={caller}] Deleted rule: {rule_id}")
        return {
            "success": True,
            "message": f"Rule {rule_id} deleted successfully"
        }
    except Exception as e:
        logger.error(f"[caller={caller}] Exception deleting policy rule: {e}")
        return {"error": str(e)}

@mcp.tool()
async def activate_policy_rule(
    ctx: Context | None = None,
    policy_id: str = "",
    rule_id: str = ""
) -> Dict[str, Any]:
    """Activate a policy rule.

    Parameters:
        policy_id (str, required): The ID of the policy.
        rule_id (str, required): The ID of the rule to activate.

    Returns:
        Dict with success status.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Activating rule: {rule_id} in policy: {policy_id}")

    if not policy_id or not rule_id:
        logger.error(f"[caller={caller}] policy_id and rule_id are required")
        return {"error": "policy_id and rule_id are required"}

    try:
        client = get_client()
        await client.post(f"/api/v1/policies/{policy_id}/rules/{rule_id}/lifecycle/activate")
        logger.info(f"[caller={caller}] Activated rule: {rule_id}")
        return {
            "success": True,
            "message": f"Rule {rule_id} activated successfully"
        }
    except Exception as e:
        logger.error(f"[caller={caller}] Exception activating policy rule: {e}")
        return {"error": str(e)}

@mcp.tool()
async def deactivate_policy_rule(
    ctx: Context | None = None,
    policy_id: str = "",
    rule_id: str = ""
) -> Dict[str, Any]:
    """Deactivate a policy rule.

    Parameters:
        policy_id (str, required): The ID of the policy.
        rule_id (str, required): The ID of the rule to deactivate.

    Returns:
        Dict with success status.
    """
    caller = get_caller_email(ctx)
    logger.info(f"[caller={caller}] Deactivating rule: {rule_id} in policy: {policy_id}")

    if not policy_id or not rule_id:
        logger.error(f"[caller={caller}] policy_id and rule_id are required")
        return {"error": "policy_id and rule_id are required"}

    try:
        client = get_client()
        await client.post(f"/api/v1/policies/{policy_id}/rules/{rule_id}/lifecycle/deactivate")
        logger.info(f"[caller={caller}] Deactivated rule: {rule_id}")
        return {
            "success": True,
            "message": f"Rule {rule_id} deactivated successfully"
        }
    except Exception as e:
        logger.error(f"[caller={caller}] Exception deactivating policy rule: {e}")
        return {"error": str(e)}