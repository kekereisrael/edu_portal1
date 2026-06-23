"""
School Service — business logic for school management.

Handles school creation, branding updates, member management,
and school-scoped data operations.
"""

import logging
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

logger = logging.getLogger(__name__)
User = get_user_model()


def get_school_by_slug(slug: str):
    """Return an active School by slug, or None."""
    from schools.models import School
    try:
        return School.objects.get(slug=slug, is_active=True)
    except School.DoesNotExist:
        return None


def get_school_by_id(school_id) -> object | None:
    """Return an active School by UUID, or None."""
    from schools.models import School
    try:
        return School.objects.get(id=school_id, is_active=True)
    except School.DoesNotExist:
        return None


def create_school(
    *,
    name: str,
    email: str,
    owner_user,
    school_type: str = 'secondary_school',
    phone: str = '',
    address: str = '',
    city: str = '',
    state: str = '',
    country: str = 'Nigeria',
    website: str = '',
    logo=None,
    primary_color: str = '#1A73E8',
    secondary_color: str = '#FFFFFF',
    principal_name: str = '',
    motto: str = '',
    timezone: str = 'Africa/Lagos',
    grading_system: str = 'percentage',
    academic_year_start_month: int = 9,
):
    """
    Atomically create a School + SchoolSettings + owner SchoolMembership
    + seed default class levels.

    Returns the created School instance.
    """
    from schools.models import School, SchoolSettings, SchoolMembership, ClassLevel

    with transaction.atomic():
        school = School.objects.create(
            name=name,
            email=email,
            school_type=school_type,
            phone=phone,
            address=address,
            city=city,
            state=state,
            country=country,
            website=website,
            logo=logo,
            primary_color=primary_color,
            secondary_color=secondary_color,
            owner=owner_user,
            is_active=True,
        )

        SchoolSettings.objects.create(
            school=school,
            principal_name=principal_name,
            motto=motto,
            timezone=timezone,
            grading_system=grading_system,
            academic_year_start_month=academic_year_start_month,
        )

        SchoolMembership.objects.create(
            school=school,
            user=owner_user,
            role=SchoolMembership.SchoolRole.SCHOOL_ADMIN,
            is_active=True,
        )

        # Seed default JSS1–SSS3 class levels
        _seed_class_levels(school)

        logger.info('School created: %s (id=%s)', school.name, school.id)
        return school


def _seed_class_levels(school):
    """Create the six default Nigerian secondary school class levels."""
    from schools.models import ClassLevel
    defaults = [
        (ClassLevel.LevelCode.JSS1, 1),
        (ClassLevel.LevelCode.JSS2, 2),
        (ClassLevel.LevelCode.JSS3, 3),
        (ClassLevel.LevelCode.SSS1, 4),
        (ClassLevel.LevelCode.SSS2, 5),
        (ClassLevel.LevelCode.SSS3, 6),
    ]
    for code, order in defaults:
        ClassLevel.objects.get_or_create(
            school=school,
            code=code,
            defaults={'order': order},
        )


def update_school_branding(school, *, logo=None, primary_color=None, secondary_color=None):
    """Update school branding fields."""
    update_fields = []
    if logo is not None:
        school.logo = logo
        update_fields.append('logo')
    if primary_color is not None:
        school.primary_color = primary_color
        update_fields.append('primary_color')
    if secondary_color is not None:
        school.secondary_color = secondary_color
        update_fields.append('secondary_color')
    if update_fields:
        update_fields.append('updated_at')
        school.save(update_fields=update_fields)
    return school


def deactivate_school(school):
    """Deactivate a school (soft delete)."""
    school.is_active = False
    school.save(update_fields=['is_active', 'updated_at'])
    logger.warning('School deactivated: %s (id=%s)', school.name, school.id)
    return school


def get_school_statistics(school) -> dict:
    """
    Return a dict of key statistics for a school.
    Used by the admin dashboard.
    """
    from schools.models import SchoolMembership, ClassRoom, AcademicSession
    from subjects.models import Subject

    memberships = SchoolMembership.objects.filter(school=school, is_active=True)

    return {
        'total_students': memberships.filter(role='student').count(),
        'total_teachers': memberships.filter(role='teacher').count(),
        'total_parents':  memberships.filter(role='parent').count(),
        'total_admins':   memberships.filter(role='school_admin').count(),
        'total_classrooms': ClassRoom.objects.filter(school=school, is_active=True).count(),
        'total_subjects': Subject.objects.filter(school=school, is_active=True).count(),
        'total_sessions': AcademicSession.objects.filter(school=school).count(),
    }


def add_member_to_school(school, user, role: str) -> object:
    """
    Add a user to a school with the given role.
    Raises ValueError if the user is already an active member.
    """
    from schools.models import SchoolMembership
    existing = SchoolMembership.objects.filter(school=school, user=user).first()
    if existing:
        if existing.is_active:
            raise ValueError(f'{user.email} is already an active member of {school.name}.')
        # Reactivate
        existing.role = role
        existing.is_active = True
        existing.save(update_fields=['role', 'is_active'])
        return existing

    return SchoolMembership.objects.create(
        school=school,
        user=user,
        role=role,
        is_active=True,
    )


def remove_member_from_school(school, membership_id) -> None:
    """Soft-remove a member from a school."""
    from schools.models import SchoolMembership
    try:
        membership = SchoolMembership.objects.get(id=membership_id, school=school)
        if membership.user == school.owner:
            raise ValueError('Cannot remove the school owner.')
        membership.is_active = False
        membership.save(update_fields=['is_active'])
    except SchoolMembership.DoesNotExist:
        raise ValueError('Membership not found.')
