from contextvars import ContextVar
from fastmcp.server.dependencies import get_http_headers

caller_email_var: ContextVar[str] = ContextVar("caller_email", default="unknown")
caller_groups_var: ContextVar[list] = ContextVar("caller_groups", default=[])

def get_caller_email() -> str:
    # Prefer real HTTP headers when available (works reliably with FastMCP)
    headers = get_http_headers()  # returns {} if not in HTTP context
    email = headers.get("x-user-email") or headers.get("x-forwarded-user")
    if email:
        return email

    # Fallback to contextvar (e.g., stdio mode or older paths)
    return caller_email_var.get()

def get_caller_groups() -> list:
    headers = get_http_headers()
    groups_str = headers.get("x-user-groups", "")
    if groups_str:
        return [g for g in groups_str.split(",") if g]

    return caller_groups_var.get()
