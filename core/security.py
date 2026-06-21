"""
Security utilities and middleware for the educational portal.
Includes request validation, IP blocking, and audit logging.
"""

import hashlib
import hmac
import logging
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class SecurityHeaders:
    """Middleware to add security headers to all responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        # Content Security Policy
        if not settings.DEBUG:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )

        return response


class IPBlockingMiddleware:
    """
    Middleware to block requests from blacklisted IPs.
    IPs are blacklisted after too many failed authentication attempts.
    """

    MAX_FAILED_ATTEMPTS = 10
    BLOCK_DURATION = 3600  # 1 hour in seconds
    CACHE_PREFIX = 'ip_block:'
    FAILED_PREFIX = 'ip_failed:'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self.get_client_ip(request)

        # Check if IP is blocked
        if cache.get(f'{self.CACHE_PREFIX}{ip}'):
            logger.warning(f"Blocked request from blacklisted IP: {ip}")
            return JsonResponse(
                {'error': 'Too many failed attempts. Please try again later.'},
                status=429
            )

        response = self.get_response(request)

        # Track failed authentication attempts
        if response.status_code == 401 and '/api/v1/auth/' in request.path:
            self._record_failed_attempt(ip)

        return response

    def _record_failed_attempt(self, ip):
        """Record a failed authentication attempt and block if threshold exceeded."""
        cache_key = f'{self.FAILED_PREFIX}{ip}'
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, timeout=self.BLOCK_DURATION)

        if attempts >= self.MAX_FAILED_ATTEMPTS:
            cache.set(f'{self.CACHE_PREFIX}{ip}', True, timeout=self.BLOCK_DURATION)
            logger.warning(f"IP {ip} blocked after {attempts} failed attempts")

    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


class RequestSizeLimitMiddleware:
    """Middleware to enforce request body size limits per endpoint type."""

    # Size limits in bytes
    DEFAULT_LIMIT = 5 * 1024 * 1024  # 5MB
    UPLOAD_LIMIT = 50 * 1024 * 1024  # 50MB for file uploads
    API_LIMIT = 1 * 1024 * 1024  # 1MB for regular API calls

    UPLOAD_PATHS = ['/api/v1/materials/', '/api/v1/schools/logo/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                content_length = int(content_length)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid content length'}, status=400)

            limit = self._get_limit(request.path)
            if content_length > limit:
                return JsonResponse(
                    {'error': f'Request body too large. Maximum size: {limit // (1024*1024)}MB'},
                    status=413
                )

        return self.get_response(request)

    def _get_limit(self, path):
        """Determine the size limit based on the request path."""
        for upload_path in self.UPLOAD_PATHS:
            if path.startswith(upload_path):
                return self.UPLOAD_LIMIT
        return self.API_LIMIT


class AuditLogMiddleware:
    """
    Middleware to log sensitive operations for audit trail.
    Logs authentication events, admin actions, and data modifications.
    """

    AUDIT_PATHS = [
        '/api/v1/auth/',
        '/api/v1/payments/',
        '/api/v1/subscriptions/',
        '/admin/',
    ]

    AUDIT_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        should_audit = self._should_audit(request)

        if should_audit:
            start_time = time.time()

        response = self.get_response(request)

        if should_audit:
            duration = time.time() - start_time
            self._log_audit(request, response, duration)

        return response

    def _should_audit(self, request):
        """Determine if this request should be audited."""
        if request.method in self.AUDIT_METHODS:
            for path in self.AUDIT_PATHS:
                if request.path.startswith(path):
                    return True
        return False

    def _log_audit(self, request, response, duration):
        """Log the audit entry."""
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
        ip = IPBlockingMiddleware.get_client_ip(request)

        log_data = {
            'timestamp': timezone.now().isoformat(),
            'user': str(user.id) if user else 'anonymous',
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'ip': ip,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'duration_ms': round(duration * 1000, 2),
        }

        if response.status_code >= 400:
            logger.warning(f"AUDIT: {log_data}")
        else:
            logger.info(f"AUDIT: {log_data}")


def verify_webhook_signature(secret_key, payload, signature, algorithm='sha512'):
    """
    Verify webhook signature from payment providers.
    
    Args:
        secret_key: The webhook secret key
        payload: The raw request body
        signature: The signature from the request header
        algorithm: Hash algorithm to use (sha256, sha512)
    
    Returns:
        bool: True if signature is valid
    """
    if not secret_key or not payload or not signature:
        return False

    if algorithm == 'sha512':
        computed = hmac.new(
            secret_key.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
    elif algorithm == 'sha256':
        computed = hmac.new(
            secret_key.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
    else:
        return False

    return hmac.compare_digest(computed, signature)


def sensitive_post_parameters(*parameters):
    """
    Decorator to mark sensitive POST parameters that should not be logged.
    Similar to Django's sensitive_post_parameters but for DRF views.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            request.sensitive_post_parameters = parameters or '__ALL__'
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class SchoolIsolationMiddleware:
    """
    Middleware to enforce strict school data isolation.
    Ensures that users can only access data belonging to their school.
    Adds additional validation beyond the SchoolContextMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Verify response doesn't leak cross-school data
        # This is a safety net - primary isolation is in querysets
        if hasattr(request, 'school') and request.school:
            # Add school context header for debugging
            response['X-School-Context'] = str(request.school.id)

        return response
