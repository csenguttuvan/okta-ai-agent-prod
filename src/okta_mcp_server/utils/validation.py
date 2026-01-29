# okta_mcp_server/utils/validation.py
"""
Input validation utilities for Okta MCP Server.
Validates IDs, emails, and other inputs before making API calls.
"""

import re
from typing import Optional, Union, List, Tuple
from loguru import logger


# Okta ID format patterns
OKTA_ID_PATTERNS = {
    "user": r"^00u[a-zA-Z0-9]{17}$",           # 00u + 17 chars = 20 total
    "group": r"^00g[a-zA-Z0-9]{17}$",          # 00g + 17 chars = 20 total
    "app": r"^0oa[a-zA-Z0-9]{17}$",            # 0oa + 17 chars = 20 total
    "policy": r"^00p[a-zA-Z0-9]{17}$",         # 00p + 17 chars = 20 total
    "rule": r"^0pr[a-zA-Z0-9]{17}$",           # 0pr + 17 chars = 20 total
    "event": r"^[a-zA-Z0-9\-]{36}$",           # UUID format for events
}


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_okta_id(
    value: Optional[str],
    id_type: str = "user",
    required: bool = True,
    field_name: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate Okta ID format.
    
    Args:
        value: The ID value to validate
        id_type: Type of ID (user, group, app, policy, rule, event)
        required: Whether the field is required
        field_name: Custom field name for error messages (defaults to f"{id_type}_id")
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Examples:
        >>> validate_okta_id("00u1234567890123456", "user")
        (True, None)
        
        >>> validate_okta_id("invalid", "user")
        (False, "Invalid user_id format. Expected: 00u[17 alphanumeric chars]")
        
        >>> validate_okta_id(None, "user", required=False)
        (True, None)
    """
    field = field_name or f"{id_type}_id"
    
    # Check if value is missing
    if value is None or value == "":
        if required:
            return False, f"{field} is required"
        return True, None
    
    # Check if it's a string
    if not isinstance(value, str):
        return False, f"{field} must be a string, got {type(value).__name__}"
    
    # Get the pattern for this ID type
    pattern = OKTA_ID_PATTERNS.get(id_type)
    if not pattern:
        return False, f"Unknown ID type: {id_type}"
    
    # Validate format
    if not re.match(pattern, value):
        # Provide helpful error messages
        expected_prefix = {
            "user": "00u",
            "group": "00g",
            "app": "0oa",
            "policy": "00p",
            "rule": "0pr",
        }.get(id_type, "")
        
        expected_length = 20 if id_type in ["user", "group", "policy"] else (20 if id_type == "app" else 36)
        
        error_parts = [f"Invalid {field} format."]
        
        # Check common mistakes
        if len(value) != expected_length:
            error_parts.append(f"Expected {expected_length} characters, got {len(value)}.")
        
        if expected_prefix and not value.startswith(expected_prefix):
            actual_prefix = value[:3] if len(value) >= 3 else value
            error_parts.append(f"Expected prefix '{expected_prefix}', got '{actual_prefix}'.")
            
            # Detect wrong type
            prefix_types = {
                "00u": "user",
                "00g": "group",
                "0oa": "app",
                "00p": "policy",
                "0pr": "rule",
            }
            if actual_prefix in prefix_types:
                error_parts.append(f"This looks like a {prefix_types[actual_prefix]} ID, not a {id_type} ID.")
        
        return False, " ".join(error_parts)
    
    return True, None


def validate_email(
    value: Optional[str],
    required: bool = True,
    field_name: str = "email"
) -> Tuple[bool, Optional[str]]:
    """
    Validate email format.
    
    Args:
        value: Email address to validate
        required: Whether the field is required
        field_name: Field name for error messages
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Examples:
        >>> validate_email("user@example.com")
        (True, None)
        
        >>> validate_email("invalid-email")
        (False, "Invalid email format")
    """
    if value is None or value == "":
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    if not isinstance(value, str):
        return False, f"{field_name} must be a string, got {type(value).__name__}"
    
    # Basic email regex (RFC 5322 simplified)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, value):
        return False, f"Invalid {field_name} format. Expected: user@domain.com"
    
    # Additional checks
    if len(value) > 254:  # RFC 5321
        return False, f"{field_name} too long (max 254 characters)"
    
    local_part, domain = value.rsplit('@', 1)
    if len(local_part) > 64:  # RFC 5321
        return False, f"{field_name} local part too long (max 64 characters)"
    
    return True, None


def validate_string(
    value: Optional[str],
    required: bool = True,
    field_name: str = "value",
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    pattern: Optional[str] = None,
    allowed_values: Optional[List[str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate string field with various constraints.
    
    Args:
        value: String to validate
        required: Whether the field is required
        field_name: Field name for error messages
        min_length: Minimum string length
        max_length: Maximum string length
        pattern: Regex pattern the string must match
        allowed_values: List of allowed values (enum)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None or value == "":
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    if not isinstance(value, str):
        return False, f"{field_name} must be a string, got {type(value).__name__}"
    
    # Check length constraints
    if min_length and len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    
    if max_length and len(value) > max_length:
        return False, f"{field_name} must be at most {max_length} characters"
    
    # Check pattern
    if pattern and not re.match(pattern, value):
        return False, f"{field_name} does not match required format"
    
    # Check allowed values
    if allowed_values and value not in allowed_values:
        return False, f"{field_name} must be one of: {', '.join(allowed_values)}"
    
    return True, None


def validate_boolean(
    value: Optional[bool],
    required: bool = True,
    field_name: str = "value"
) -> Tuple[bool, Optional[str]]:
    """
    Validate boolean field.
    
    Args:
        value: Boolean to validate
        required: Whether the field is required
        field_name: Field name for error messages
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    if not isinstance(value, bool):
        return False, f"{field_name} must be a boolean (true/false), got {type(value).__name__}"
    
    return True, None


def validate_integer(
    value: Optional[int],
    required: bool = True,
    field_name: str = "value",
    min_value: Optional[int] = None,
    max_value: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate integer field with range constraints.
    
    Args:
        value: Integer to validate
        required: Whether the field is required
        field_name: Field name for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        if required:
            return False, f"{field_name} is required"
        return True, None
    
    if not isinstance(value, int) or isinstance(value, bool):  # bool is subclass of int
        return False, f"{field_name} must be an integer, got {type(value).__name__}"
    
    if min_value is not None and value < min_value:
        return False, f"{field_name} must be at least {min_value}"
    
    if max_value is not None and value > max_value:
        return False, f"{field_name} must be at most {max_value}"
    
    return True, None


def validate_and_raise(
    is_valid: bool,
    error_message: Optional[str],
    log_context: Optional[str] = None
) -> None:
    """
    Helper to raise ValidationError if validation failed.
    
    Args:
        is_valid: Result from validation function
        error_message: Error message from validation function
        log_context: Optional context for logging (e.g., user email)
        
    Raises:
        ValidationError: If validation failed
        
    Example:
        >>> is_valid, error = validate_okta_id(user_id, "user")
        >>> validate_and_raise(is_valid, error, f"[{caller}]")
    """
    if not is_valid:
        if log_context:
            logger.error(f"{log_context} {error_message}")
        else:
            logger.error(error_message)
        raise ValidationError(error_message)


# Convenience function for common validation pattern
def validate_params(**validators) -> None:
    """
    Validate multiple parameters at once.
    
    Args:
        **validators: Dict of parameter_name -> (is_valid, error_message) tuples
        
    Raises:
        ValidationError: On first validation failure
        
    Example:
        >>> validate_params(
        ...     user_id=validate_okta_id(user_id, "user"),
        ...     email=validate_email(email),
        ...     confirm=validate_boolean(confirm_deletion)
        ... )
    """
    for param_name, (is_valid, error_message) in validators.items():
        if not is_valid:
            logger.error(f"Validation failed for {param_name}: {error_message}")
            raise ValidationError(error_message)

def validate_and_return(
    is_valid: bool,
    error_message: Optional[str],
    log_context: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    ✅ NEW - Helper to log validation errors WITHOUT raising exceptions.
    Bedrock-compatible: returns validation result for tools to return as strings.
    """
    if not is_valid:
        if log_context:
            logger.error(f"{log_context} {error_message}")
        else:
            logger.error(error_message)
    return is_valid, error_message
