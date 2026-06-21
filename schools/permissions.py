"""
Custom permissions for the schools app.
"""

from rest_framework.permissions import BasePermission


class HasSchoolContext(BasePermission):
    """Requires that the request has a school context attached."""

    message = 'You must belong to a school to access this resource.'

    def has_permission(self, request, view):
        if request.user.is_platform_admin:
            return True
        return request.school is not None


class IsSchoolAdmin(BasePermission):
    """Requires that the user is a school admin for the current school."""

    message = 'Only school administrators can perform this action.'

    def has_permission(self, request, view):
        if request.user.is_platform_admin:
            return True
        if not request.school_membership:
            return False
        return request.school_membership.role == 'school_admin'


class IsSchoolTeacher(BasePermission):
    """Requires that the user is a teacher in the current school."""

    message = 'Only teachers can perform this action.'

    def has_permission(self, request, view):
        if request.user.is_platform_admin:
            return True
        if not request.school_membership:
            return False
        return request.school_membership.role in ['school_admin', 'teacher']


class IsSchoolStudent(BasePermission):
    """Requires that the user is a student in the current school."""

    message = 'Only students can perform this action.'

    def has_permission(self, request, view):
        if not request.school_membership:
            return False
        return request.school_membership.role == 'student'


class IsSchoolParent(BasePermission):
    """Requires that the user is a parent in the current school."""

    message = 'Only parents can perform this action.'

    def has_permission(self, request, view):
        if not request.school_membership:
            return False
        return request.school_membership.role == 'parent'


class IsSchoolAdminOrTeacher(BasePermission):
    """Requires school admin or teacher role."""

    message = 'Only school administrators or teachers can perform this action.'

    def has_permission(self, request, view):
        if request.user.is_platform_admin:
            return True
        if not request.school_membership:
            return False
        return request.school_membership.role in ['school_admin', 'teacher']


class IsPlatformAdmin(BasePermission):
    """Requires platform admin status."""

    message = 'Only platform administrators can perform this action.'

    def has_permission(self, request, view):
        return request.user.is_platform_admin


class SchoolObjectPermission(BasePermission):
    """
    Object-level permission ensuring the object belongs to the user's school.
    Models must have a 'school' field.
    """

    message = 'You do not have permission to access this object.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_platform_admin:
            return True
        if not request.school:
            return False
        # Check if object has school field
        if hasattr(obj, 'school'):
            return obj.school == request.school
        if hasattr(obj, 'school_id'):
            return obj.school_id == request.school.id
        return True
