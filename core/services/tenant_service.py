"""
Tenant Service — school data isolation and context management.

Provides utilities for:
  - Resolving the current school from a request
  - Enforcing strict school-scoped queryset filtering
  - Cross-school data leak detection
"""

import logging
from functools import wraps

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def get_school_from_request(request):
    """
    Return the School attached to the request by SchoolContextMiddleware,
    or None if no school context is present.
    """
    return getattr(request, 'school', None)


def get_membership_from_request(request):
    """
    Return the SchoolMembership attached to the request, or None.
    """
    return getattr(request, 'school_membership', None)


def assert_school_ownership(obj, school, field: str = 'school'):
    """
    Raise PermissionError if `obj.school` does not match `school`.
    Use this in service functions that receive objects from user input.
    """
    obj_school_id = None
    if hasattr(obj, 'school_id'):
        obj_school_id = obj.school_id
    elif hasattr(obj, field):
        related = getattr(obj, field, None)
        obj_school_id = getattr(related, 'id', None)

    if obj_school_id is None or str(obj_school_id) != str(school.id):
        logger.warning(
            'Cross-school access attempt: object school=%s, request school=%s',
            obj_school_id,
            school.id,
        )
        raise PermissionError('You do not have permission to access this resource.')


def school_scoped_queryset(model_class, school, **filters):
    """
    Return a queryset for model_class filtered to the given school.
    Always applies school= filter first to prevent data leaks.
    """
    return model_class.objects.filter(school=school, **filters)


def get_user_schools(user):
    """
    Return all active schools a user belongs to (via SchoolMembership).
    """
    from schools.models import SchoolMembership
    memberships = SchoolMembership.objects.filter(
        user=user, is_active=True
    ).select_related('school')
    return [m.school for m in memberships if m.school.is_active]


def get_user_role_in_school(user, school) -> str | None:
    """
    Return the user's role in the given school, or None if not a member.
    """
    from schools.models import SchoolMembership
    try:
        membership = SchoolMembership.objects.get(
            user=user, school=school, is_active=True
        )
        return membership.role
    except SchoolMembership.DoesNotExist:
        return None


def is_user_member_of_school(user, school) -> bool:
    """Return True if the user is an active member of the school."""
    from schools.models import SchoolMembership
    return SchoolMembership.objects.filter(
        user=user, school=school, is_active=True
    ).exists()


def require_school_context(view_func):
    """
    Decorator for function-based views that require a school context.
    Returns 403 if request.school is not set.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'school', None):
            return JsonResponse(
                {'detail': 'No school context. Provide X-School-ID header.'},
                status=403,
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def validate_school_data_integrity(school) -> list[str]:
    """
    Run basic integrity checks on a school's data.
    Returns a list of warning strings (empty = all good).
    """
    from schools.models import SchoolMembership, SchoolSettings
    warnings = []

    if not SchoolSettings.objects.filter(school=school).exists():
        warnings.append(f'School {school.name} has no SchoolSettings record.')

    admin_count = SchoolMembership.objects.filter(
        school=school, role='school_admin', is_active=True
    ).count()
    if admin_count == 0:
        warnings.append(f'School {school.name} has no active school admin.')

    return warnings
