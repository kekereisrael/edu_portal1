"""
Permission Service — centralised role-based access control helpers.

Provides programmatic permission checks that can be used in service
functions, Celery tasks, and management commands (where DRF permission
classes are not available).
"""

import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Role constants (mirrors SchoolMembership.SchoolRole)
# ─────────────────────────────────────────────────────────────────────────────

ROLE_SCHOOL_ADMIN = 'school_admin'
ROLE_TEACHER      = 'teacher'
ROLE_STUDENT      = 'student'
ROLE_PARENT       = 'parent'


# ─────────────────────────────────────────────────────────────────────────────
# Core checks
# ─────────────────────────────────────────────────────────────────────────────

def user_has_role_in_school(user, school, *roles) -> bool:
    """
    Return True if the user has any of the given roles in the school.

    Example:
        user_has_role_in_school(user, school, 'school_admin', 'teacher')
    """
    from schools.models import SchoolMembership
    return SchoolMembership.objects.filter(
        user=user,
        school=school,
        role__in=roles,
        is_active=True,
    ).exists()


def is_platform_admin(user) -> bool:
    """Return True if the user is a platform-level admin."""
    return bool(getattr(user, 'is_platform_admin', False))


def is_school_admin(user, school) -> bool:
    return user_has_role_in_school(user, school, ROLE_SCHOOL_ADMIN)


def is_teacher(user, school) -> bool:
    return user_has_role_in_school(user, school, ROLE_TEACHER, ROLE_SCHOOL_ADMIN)


def is_student(user, school) -> bool:
    return user_has_role_in_school(user, school, ROLE_STUDENT)


def is_parent(user, school) -> bool:
    return user_has_role_in_school(user, school, ROLE_PARENT)


def is_school_member(user, school) -> bool:
    return user_has_role_in_school(
        user, school,
        ROLE_SCHOOL_ADMIN, ROLE_TEACHER, ROLE_STUDENT, ROLE_PARENT,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Enforcement helpers (raise PermissionError on failure)
# ─────────────────────────────────────────────────────────────────────────────

def require_school_admin(user, school):
    """Raise PermissionError if user is not a school admin."""
    if not is_school_admin(user, school):
        raise PermissionError('You must be a school admin to perform this action.')


def require_teacher(user, school):
    """Raise PermissionError if user is not a teacher or school admin."""
    if not is_teacher(user, school):
        raise PermissionError('You must be a teacher to perform this action.')


def require_student(user, school):
    """Raise PermissionError if user is not a student."""
    if not is_student(user, school):
        raise PermissionError('You must be a student to perform this action.')


def require_parent(user, school):
    """Raise PermissionError if user is not a parent."""
    if not is_parent(user, school):
        raise PermissionError('You must be a parent to perform this action.')


def require_school_member(user, school):
    """Raise PermissionError if user is not a member of the school."""
    if not is_school_member(user, school):
        raise PermissionError('You are not a member of this school.')


def require_platform_admin(user):
    """Raise PermissionError if user is not a platform admin."""
    if not is_platform_admin(user):
        raise PermissionError('You must be a platform admin to perform this action.')


# ─────────────────────────────────────────────────────────────────────────────
# Object-level checks
# ─────────────────────────────────────────────────────────────────────────────

def can_access_student_data(requesting_user, student_user, school) -> bool:
    """
    Return True if requesting_user can access student_user's data in school.

    Rules:
      - Platform admin: always
      - School admin / teacher: always (within same school)
      - Student: only their own data
      - Parent: only their linked children
    """
    if is_platform_admin(requesting_user):
        return True

    if is_school_admin(requesting_user, school) or is_teacher(requesting_user, school):
        return True

    if requesting_user == student_user and is_student(requesting_user, school):
        return True

    if is_parent(requesting_user, school):
        from schools.models import ParentStudentLink
        return ParentStudentLink.objects.filter(
            school=school,
            parent=requesting_user,
            student=student_user,
            status=ParentStudentLink.Status.APPROVED,
        ).exists()

    return False


def can_manage_member(requesting_user, target_user, school) -> bool:
    """
    Return True if requesting_user can add/remove/edit target_user in school.
    Only school admins and platform admins can manage members.
    """
    if is_platform_admin(requesting_user):
        return True
    if is_school_admin(requesting_user, school):
        # Cannot demote/remove the school owner
        if target_user == school.owner:
            return False
        return True
    return False
