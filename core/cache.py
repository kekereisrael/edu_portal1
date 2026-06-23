"""
Caching utilities for the educational portal.
Provides cache key generation, cache decorators, and cache invalidation helpers.
"""

import hashlib
import functools
from django.core.cache import cache
from django.conf import settings


# Cache timeout constants (in seconds)
CACHE_SHORT = 60  # 1 minute
CACHE_MEDIUM = 300  # 5 minutes
CACHE_LONG = 3600  # 1 hour
CACHE_DAY = 86400  # 24 hours
CACHE_WEEK = 604800  # 7 days


def make_cache_key(prefix, *args, **kwargs):
    """
    Generate a consistent cache key from prefix and arguments.
    
    Args:
        prefix: String prefix for the cache key
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key
    
    Returns:
        str: A cache key string
    """
    key_parts = [prefix] + [str(a) for a in args]
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        key_parts.extend([f"{k}={v}" for k, v in sorted_kwargs])

    key_string = ':'.join(key_parts)

    # Hash if key is too long (memcached limit is 250 chars)
    if len(key_string) > 200:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    return key_string


def school_cache_key(school_id, resource, *args):
    """Generate a school-scoped cache key."""
    return make_cache_key(f"school:{school_id}:{resource}", *args)


def user_cache_key(user_id, resource, *args):
    """Generate a user-scoped cache key."""
    return make_cache_key(f"user:{user_id}:{resource}", *args)


def cached_property_with_ttl(ttl=CACHE_MEDIUM):
    """
    Decorator for caching expensive property computations.
    Uses Django's cache backend instead of instance-level caching.
    
    Args:
        ttl: Cache timeout in seconds
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self):
            cache_key = make_cache_key(
                f"{self.__class__.__name__}:{func.__name__}",
                str(self.pk)
            )
            result = cache.get(cache_key)
            if result is None:
                result = func(self)
                cache.set(cache_key, result, timeout=ttl)
            return result
        return property(wrapper)
    return decorator


def cache_response(timeout=CACHE_MEDIUM, key_func=None, vary_on_school=True):
    """
    Decorator for caching DRF view responses.
    
    Args:
        timeout: Cache timeout in seconds
        key_func: Optional function to generate cache key from request
        vary_on_school: Whether to include school context in cache key
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Build cache key
            if key_func:
                cache_key = key_func(request, *args, **kwargs)
            else:
                parts = [
                    request.path,
                    request.method,
                    str(request.query_params),
                ]
                if vary_on_school and hasattr(request, 'school') and request.school:
                    parts.append(str(request.school.id))
                if request.user and request.user.is_authenticated:
                    parts.append(str(request.user.id))

                cache_key = make_cache_key('view_cache', *parts)

            # Try to get from cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

            # Execute view and cache result
            response = view_func(self, request, *args, **kwargs)

            # Only cache successful responses
            if response.status_code == 200:
                cache.set(cache_key, response, timeout=timeout)

            return response
        return wrapper
    return decorator


def invalidate_school_cache(school_id, resource=None):
    """
    Invalidate all cache entries for a school or a specific resource.
    
    Args:
        school_id: The school UUID
        resource: Optional specific resource to invalidate
    """
    try:
        if resource:
            pattern = f"school:{school_id}:{resource}:*"
        else:
            pattern = f"school:{school_id}:*"

        # Use cache.delete_pattern if available (django-redis)
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
        else:
            # Fallback: delete known keys
            _delete_known_keys(school_id, resource)
    except Exception:
        # Silently fail - cache invalidation should never crash the app
        pass


def invalidate_user_cache(user_id, resource=None):
    """Invalidate all cache entries for a user."""
    try:
        if resource:
            pattern = f"user:{user_id}:{resource}:*"
        else:
            pattern = f"user:{user_id}:*"

        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
    except Exception:
        # Silently fail - cache invalidation should never crash the app
        pass


def _delete_known_keys(school_id, resource=None):
    """Fallback cache invalidation for backends without pattern delete."""
    known_resources = [
        'subjects', 'exams', 'materials', 'students',
        'teachers', 'analytics', 'subscription', 'storage',
    ]

    resources = [resource] if resource else known_resources
    for res in resources:
        cache.delete(school_cache_key(school_id, res))


class CacheInvalidationMixin:
    """
    Mixin for DRF views that automatically invalidates cache on mutations.
    Add to ViewSets that modify data.
    """

    cache_resource = None  # Override in subclass

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._invalidate_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._invalidate_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._invalidate_cache()

    def _invalidate_cache(self):
        """Invalidate cache for the current school context."""
        if self.cache_resource and hasattr(self.request, 'school') and self.request.school:
            invalidate_school_cache(self.request.school.id, self.cache_resource)


class QueryCountDebugMixin:
    """
    Debug mixin that logs the number of database queries per request.
    Only active in DEBUG mode.
    """

    def dispatch(self, request, *args, **kwargs):
        if settings.DEBUG:
            from django.db import connection
            initial_queries = len(connection.queries)
            response = super().dispatch(request, *args, **kwargs)
            final_queries = len(connection.queries)
            query_count = final_queries - initial_queries
            response['X-Query-Count'] = str(query_count)

            if query_count > 10:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"High query count ({query_count}) for "
                    f"{request.method} {request.path}"
                )
            return response
        return super().dispatch(request, *args, **kwargs)
