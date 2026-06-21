"""
Middleware for school context injection (multi-tenancy).
"""

from django.http import JsonResponse
from django.urls import resolve

from .models import SchoolMembership


class SchoolContextMiddleware:
    """
    Middleware that attaches the current school to the request object.
    
    After authentication, this middleware looks up the user's school membership
    and attaches `request.school` and `request.school_membership` for use
    in views and permissions.
    
    Skips for:
    - Unauthenticated requests
    - Platform admin routes
    - Auth endpoints (login, register)
    - Admin panel
    """

    EXEMPT_URL_NAMES = [
        'accounts:register',
        'accounts:login',
        'accounts:token_refresh',
    ]

    EXEMPT_URL_PREFIXES = [
        '/admin/',
        '/api/v1/auth/register/',
        '/api/v1/auth/login/',
        '/api/v1/auth/token/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Initialize school context
        request.school = None
        request.school_membership = None

        # Skip for exempt URLs
        if self._is_exempt(request):
            return self.get_response(request)

        # Skip for unauthenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)

        # Platform admins don't need school context
        if request.user.is_platform_admin:
            return self.get_response(request)

        # Try to get school from header (for multi-school users)
        school_id = request.headers.get('X-School-ID')

        if school_id:
            # Specific school requested
            try:
                membership = SchoolMembership.objects.select_related('school').get(
                    user=request.user,
                    school_id=school_id,
                    is_active=True,
                )
                request.school = membership.school
                request.school_membership = membership
            except SchoolMembership.DoesNotExist:
                pass
        else:
            # Default to first active membership
            membership = (
                SchoolMembership.objects
                .select_related('school')
                .filter(user=request.user, is_active=True)
                .first()
            )
            if membership:
                request.school = membership.school
                request.school_membership = membership

        return self.get_response(request)

    def _is_exempt(self, request):
        """Check if the current URL is exempt from school context."""
        for prefix in self.EXEMPT_URL_PREFIXES:
            if request.path.startswith(prefix):
                return True
        return False
