"""
Safe cache wrapper utilities.
Prevents Redis/cache backend crashes from propagating to the application.
All cache operations are wrapped in try/except to ensure graceful degradation.
"""

import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def safe_cache_get(key, default=None):
    """
    Safely get a value from cache.
    Returns default if cache is unavailable or key doesn't exist.
    """
    try:
        return cache.get(key, default)
    except Exception as exc:
        logger.warning(f"Cache GET failed for key '{key}': {exc}")
        return default


def safe_cache_set(key, value, timeout=300):
    """
    Safely set a value in cache.
    Silently fails if cache backend is unavailable.
    """
    try:
        cache.set(key, value, timeout=timeout)
    except Exception as exc:
        logger.warning(f"Cache SET failed for key '{key}': {exc}")


def safe_cache_delete(key):
    """
    Safely delete a key from cache.
    Silently fails if cache backend is unavailable.
    """
    try:
        cache.delete(key)
    except Exception as exc:
        logger.warning(f"Cache DELETE failed for key '{key}': {exc}")


def safe_cache_get_or_set(key, default_func, timeout=300):
    """
    Safely get from cache or compute and set.
    If cache is unavailable, just computes the value without caching.
    
    Args:
        key: Cache key
        default_func: Callable that returns the value to cache
        timeout: Cache timeout in seconds
    
    Returns:
        Cached value or freshly computed value
    """
    try:
        value = cache.get(key)
        if value is not None:
            return value
    except Exception as exc:
        logger.warning(f"Cache GET failed for key '{key}': {exc}")

    # Compute the value
    value = default_func() if callable(default_func) else default_func

    try:
        cache.set(key, value, timeout=timeout)
    except Exception as exc:
        logger.warning(f"Cache SET failed for key '{key}': {exc}")

    return value


def safe_cache_delete_pattern(pattern):
    """
    Safely delete cache keys matching a pattern.
    Only works with backends that support delete_pattern (e.g., django-redis).
    Silently fails for other backends.
    """
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
    except Exception as exc:
        logger.warning(f"Cache DELETE_PATTERN failed for pattern '{pattern}': {exc}")
