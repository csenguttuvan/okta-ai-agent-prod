# okta_mcp_server/utils/retryable_client.py
"""
Wrapper for Okta client that adds automatic retry logic to all API calls.
"""

from typing import Any
from okta_mcp_server.utils.retry import retry_on_transient_error
from loguru import logger


class RetryableOktaClient:
    """
    Wrapper around Okta client that adds automatic retry with exponential backoff.
    
    All HTTP methods (get, post, put, delete, patch) are automatically wrapped
    with retry logic that handles transient errors like rate limits and timeouts.
    
    Usage:
        client = get_client()  # Your existing client
        retryable_client = RetryableOktaClient(client)
        
        # All calls now have automatic retry
        users = retryable_client.get("/api/v1/users")
    """
    
    def __init__(self, client: Any, max_retries: int = 3, backoff_factor: float = 2.0):
        """
        Initialize retryable client wrapper.
        
        Args:
            client: The underlying Okta API client
            max_retries: Maximum retry attempts for transient errors (default: 3)
            backoff_factor: Exponential backoff multiplier (default: 2.0)
        """
        self._client = client
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        logger.info(
            f"[RETRY] ✅ Initialized RetryableOktaClient "
            f"(max_retries={max_retries}, backoff={backoff_factor}x)"
        )
    
    def _wrap_method(self, method_name: str):
        """
        Wrap a client method with retry logic.
        
        Args:
            method_name: Name of the method to wrap (e.g., 'get', 'post')
            
        Returns:
            Wrapped method with retry logic
        """
        original_method = getattr(self._client, method_name)
        
        @retry_on_transient_error(
            max_retries=self._max_retries,
            backoff_factor=self._backoff_factor
        )
        def wrapped(*args, **kwargs):
            return original_method(*args, **kwargs)
        
        return wrapped
    
    def get(self, *args, **kwargs):
        """GET request with automatic retry on transient errors."""
        return self._wrap_method('get')(*args, **kwargs)
    
    def post(self, *args, **kwargs):
        """POST request with automatic retry on transient errors."""
        return self._wrap_method('post')(*args, **kwargs)
    
    def put(self, *args, **kwargs):
        """PUT request with automatic retry on transient errors."""
        return self._wrap_method('put')(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """DELETE request with automatic retry on transient errors."""
        return self._wrap_method('delete')(*args, **kwargs)
    
    def patch(self, *args, **kwargs):
        """PATCH request with automatic retry on transient errors."""
        return self._wrap_method('patch')(*args, **kwargs)
    
    def __getattr__(self, name: str):
        """
        Forward any other attribute access to the underlying client.
        This ensures compatibility with all client methods and properties.
        """
        return getattr(self._client, name)
    
    def __repr__(self) -> str:
        return (
            f"RetryableOktaClient(max_retries={self._max_retries}, "
            f"backoff_factor={self._backoff_factor})"
        )
