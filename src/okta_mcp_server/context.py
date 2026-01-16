from contextvars import ContextVar

caller_email_var: ContextVar[str] = ContextVar("caller_email", default="unknown")
caller_groups_var: ContextVar[list] = ContextVar("caller_groups", default=[])


def get_caller_email() -> str:
    """Get caller email from context variable set by middleware."""
    return caller_email_var.get()


def get_caller_groups() -> list:
    """Get caller groups from context variable set by middleware."""
    return caller_groups_var.get()
