from contextvars import ContextVar

# Create context variables for storing caller info
caller_email_var: ContextVar[str] = ContextVar("caller_email", default="unknown")
caller_groups_var: ContextVar[list] = ContextVar("caller_groups", default=[])

def get_caller_email() -> str:
    """Get the current caller's email from context"""
    return caller_email_var.get()

def get_caller_groups() -> list:
    """Get the current caller's groups from context"""
    return caller_groups_var.get()
