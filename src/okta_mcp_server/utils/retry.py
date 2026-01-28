# okta_mcp_server/utils/retry.py
"""
Retry decorator with exponential backoff for Okta API calls.
Handles transient errors like rate limits, timeouts, and 5xx errors.
"""

import time
from functools import wraps
from typing import Callable, Any
from loguru import logger


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.
    
    Args:
        exception: The exception to check
        
    Returns:
        bool: True if error is retryable, False otherwise
    """
    error_msg = str(exception).lower()
    
    # Retryable HTTP status codes
    retryable_statuses = [
        '429',  # Too Many Requests (rate limit)
        '500',  # Internal Server Error
        '502',  # Bad Gateway
        '503',  # Service Unavailable
        '504',  # Gateway Timeout
    ]
    
    # Retryable error patterns
    retryable_patterns = [
        'rate limit',
        'too many requests',
        'timeout',
        'timed out',
        'connection',
        'temporarily unavailable',
        'service unavailable',
        'network',
        'unreachable',
    ]
    
    # Check if error matches retryable conditions
    for status in retryable_statuses:
        if status in error_msg:
            return True
    
    for pattern in retryable_patterns:
        if pattern in error_msg:
            return True
    
    return False


def retry_on_transient_error(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Callable:
    """
    Decorator to retry functions on transient errors with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay between retries (default: 30.0)
    
    Example:
        @retry_on_transient_error(max_retries=3)
        def my_api_call():
            return client.get("/api/v1/users")
    
    Retry schedule:
        - Attempt 1: immediate
        - Attempt 2: wait 1s
        - Attempt 3: wait 2s
        - Attempt 4: wait 4s
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)
                
                except Exception as e:
                    last_exception = e
                    
                    # Don't retry if it's the last attempt
                    if attempt >= max_retries:
                        logger.error(
                            f"[RETRY] ❌ Max retries ({max_retries}) exceeded for {func.__name__}. "
                            f"Final error: {str(e)[:150]}"
                        )
                        raise
                    
                    # Don't retry on non-retryable errors (4xx client errors except 429)
                    if not is_retryable_error(e):
                        logger.debug(
                            f"[RETRY] Non-retryable error for {func.__name__}: {str(e)[:100]}"
                        )
                        raise
                    
                    # Calculate wait time with exponential backoff
                    wait_time = min(delay * (backoff_factor ** attempt), max_delay)
                    
                    logger.warning(
                        f"[RETRY] ⚠️  Attempt {attempt + 1}/{max_retries} failed for {func.__name__}. "
                        f"Retrying in {wait_time:.1f}s... Error: {str(e)[:100]}"
                    )
                    
                    time.sleep(wait_time)
            
            # Should never reach here, but just in case
            raise last_exception
        
        return wrapper
    return decorator


def async_retry_on_transient_error(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Callable:
    """
    Async version of retry decorator for async functions.
    
    Usage:
        @async_retry_on_transient_error(max_retries=3)
        async def my_async_api_call():
            return await client.get("/api/v1/users")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            import asyncio
            
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except Exception as e:
                    last_exception = e
                    
                    if attempt >= max_retries:
                        logger.error(
                            f"[RETRY] ❌ Max retries ({max_retries}) exceeded for {func.__name__}. "
                            f"Final error: {str(e)[:150]}"
                        )
                        raise
                    
                    if not is_retryable_error(e):
                        logger.debug(
                            f"[RETRY] Non-retryable error for {func.__name__}: {str(e)[:100]}"
                        )
                        raise
                    
                    wait_time = min(delay * (backoff_factor ** attempt), max_delay)
                    
                    logger.warning(
                        f"[RETRY] ⚠️  Attempt {attempt + 1}/{max_retries} failed for {func.__name__}. "
                        f"Retrying in {wait_time:.1f}s... Error: {str(e)[:100]}"
                    )
                    
                    await asyncio.sleep(wait_time)
            
            raise last_exception
        
        return wrapper
    return decorator
