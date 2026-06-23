"""
Custom error views for the Examind application.
Phase 6E: Enhanced error handling with:
  - JSON responses for API requests (Accept: application/json)
  - HTML error pages for browser requests
  - Structured error logging with request context
  - Sentry-compatible error reporting hook
"""

import logging
import traceback

from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)
error_logger = logging.getLogger('django.request')


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_api_request(request) -> bool:
    """Return True if the request expects a JSON response."""
    accept = request.META.get('HTTP_ACCEPT', '')
    content_type = request.META.get('CONTENT_TYPE', '')
    return (
        request.path.startswith('/api/') or
        'application/json' in accept or
        'application/json' in content_type
    )


def _get_request_context(request) -> dict:
    """Extract safe request context for logging."""
    return {
        'method': request.method,
        'path': request.path,
        'user': str(request.user) if hasattr(request, 'user') else 'anonymous',
        'ip': _get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        'referer': request.META.get('HTTP_REFERER', ''),
    }


def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ─────────────────────────────────────────────────────────────────────────────
# Error handlers
# ─────────────────────────────────────────────────────────────────────────────

def bad_request(request, exception=None):
    """
    400 Bad Request
    Returned when the request is malformed or contains invalid data.
    """
    ctx = _get_request_context(request)
    logger.warning(f'400 Bad Request: {ctx["path"]} | User: {ctx["user"]} | IP: {ctx["ip"]}')

    if _is_api_request(request):
        return JsonResponse(
            {
                'error': 'Bad Request',
                'detail': 'The request was malformed or contained invalid data.',
                'status_code': 400,
            },
            status=400,
        )
    return render(request, 'errors/400.html', {'request_path': request.path}, status=400)


def permission_denied(request, exception=None):
    """
    403 Forbidden
    Returned when the user doesn't have permission to access the resource.
    """
    ctx = _get_request_context(request)
    logger.warning(
        f'403 Forbidden: {ctx["path"]} | User: {ctx["user"]} | IP: {ctx["ip"]}'
    )

    if _is_api_request(request):
        return JsonResponse(
            {
                'error': 'Forbidden',
                'detail': 'You do not have permission to access this resource.',
                'status_code': 403,
            },
            status=403,
        )
    return render(request, 'errors/403.html', {'request_path': request.path}, status=403)


def page_not_found(request, exception=None):
    """
    404 Not Found
    Returned when the requested resource doesn't exist.
    """
    ctx = _get_request_context(request)
    logger.info(f'404 Not Found: {ctx["path"]} | User: {ctx["user"]} | IP: {ctx["ip"]}')

    if _is_api_request(request):
        return JsonResponse(
            {
                'error': 'Not Found',
                'detail': f'The requested resource was not found: {request.path}',
                'status_code': 404,
            },
            status=404,
        )
    return render(
        request,
        'errors/404.html',
        {'request_path': request.path},
        status=404,
    )


def server_error(request):
    """
    500 Internal Server Error
    Returned when an unhandled exception occurs.
    """
    ctx = _get_request_context(request)

    # Log full traceback for server errors
    error_logger.error(
        f'500 Server Error: {ctx["path"]} | User: {ctx["user"]} | IP: {ctx["ip"]}',
        exc_info=True,
        extra={'request': request},
    )

    # Hook: send to Sentry if configured
    _report_to_sentry()

    if _is_api_request(request):
        return JsonResponse(
            {
                'error': 'Internal Server Error',
                'detail': 'An unexpected error occurred. Our team has been notified.',
                'status_code': 500,
            },
            status=500,
        )
    return render(request, 'errors/500.html', status=500)


def csrf_failure(request, reason=''):
    """
    403 CSRF Failure
    Returned when a CSRF token is missing or invalid.
    """
    ctx = _get_request_context(request)
    logger.warning(
        f'CSRF Failure: {ctx["path"]} | Reason: {reason} | IP: {ctx["ip"]}'
    )

    if _is_api_request(request):
        return JsonResponse(
            {
                'error': 'CSRF Verification Failed',
                'detail': reason or 'CSRF token missing or incorrect.',
                'status_code': 403,
            },
            status=403,
        )
    return render(
        request,
        'errors/403.html',
        {'request_path': request.path, 'csrf_failure': True, 'reason': reason},
        status=403,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Error reporting hook
# ─────────────────────────────────────────────────────────────────────────────

def _report_to_sentry():
    """
    Send error to Sentry if sentry-sdk is installed and DSN is configured.
    Safe to call — never raises.
    """
    try:
        import sentry_sdk
        sentry_sdk.capture_exception()
    except ImportError:
        pass
    except Exception:
        pass
