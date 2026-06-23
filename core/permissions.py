"""
Core permissions used across multiple apps.
"""

from rest_framework import permissions


class HasSchoolContext(permissions.BasePermission):
    """Ensure request has a school context attached."""

    message = 'No school context. Please provide X-School-ID header or join a school.'

    def has_permission(self, request, view):
        return hasattr(request, 'school') and request.school is not None


class IsSchoolAdmin(permissions.BasePermission):
    """Ensure user is a school admin for the current school."""

    message = 'You must be a school admin to perform this action.'

    def has_permission(self, request, view):
        if not hasattr(request, 'school_membership') or request.school_membership is None:
            return False
        return request.school_membership.role == 'school_admin'


class IsTeacher(permissions.BasePermission):
    """Ensure user is a teacher in the current school."""

    message = 'You must be a teacher to perform this action.'

    def has_permission(self, request, view):
        if not hasattr(request, 'school_membership') or request.school_membership is None:
            return False
        return request.school_membership.role in ['teacher', 'school_admin']


class IsStudent(permissions.BasePermission):
    """Ensure user is a student in the current school."""

    message = 'You must be a student to perform this action.'

    def has_permission(self, request, view):
        if not hasattr(request, 'school_membership') or request.school_membership is None:
            return False
        return request.school_membership.role == 'student'


class IsPlatformAdmin(permissions.BasePermission):
    """Ensure user is a platform admin."""

    message = 'You must be a platform admin to perform this action.'

    def has_permission(self, request, view):
        return request.user.is_platform_admin


class IsSchoolAdminOrTeacher(permissions.BasePermission):
    """Ensure user is either a school admin or teacher."""

    message = 'You must be a school admin or teacher to perform this action.'

    def has_permission(self, request, view):
        if not hasattr(request, 'school_membership') or request.school_membership is None:
            return False
        return request.school_membership.role in ['school_admin', 'teacher']


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object-level permission: only the owner can modify."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # Check various owner field names
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        if hasattr(obj, 'uploaded_by'):
            return obj.uploaded_by == request.user
        return False


class IsParent(permissions.BasePermission):
    """Ensure user is a parent in the current school."""

    message = 'You must be a parent to perform this action.'

    def has_permission(self, request, view):
        if not hasattr(request, 'school_membership') or request.school_membership is None:
            return False
        return request.school_membership.role == 'parent'


class IsSchoolAdminOrParent(permissions.BasePermission):
    """Ensure user is either a school admin or a parent."""

    message = 'You must be a school admin or parent to perform this action.'

    def has_permission(self, request, view):
        if not hasattr(request, 'school_membership') or request.school_membership is None:
            return False
        return request.school_membership.role in ['school_admin', 'parent']


class IsSchoolMember(permissions.BasePermission):
    """
    Object-level permission: the object must belong to the same school as
    the current request context.

    Works for any model that has a `school` FK/O2O field, or that exposes
    a `school` property (e.g. Term → academic_year.school).
    """

    message = 'You do not have permission to access this resource in your school.'

    def has_permission(self, request, view):
        # Require an active school context
        return hasattr(request, 'school') and request.school is not None

    def has_object_permission(self, request, view, obj):
        if not hasattr(request, 'school') or request.school is None:
            return False
        # Resolve the school from the object
        obj_school = None
        if hasattr(obj, 'school_id'):
            obj_school = obj.school_id
        elif hasattr(obj, 'school'):
            try:
                obj_school = obj.school.id if obj.school else None
            except Exception:
                return False
        if obj_school is None:
            return False
        return str(obj_school) == str(request.school.id)
