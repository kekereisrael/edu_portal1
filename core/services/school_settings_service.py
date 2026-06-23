"""
School Settings Service — manage academic configuration for a school.

Handles:
  - Academic session creation and activation
  - Term management
  - Grading system configuration (pass mark, grade boundaries)
  - School information updates
"""

import logging
from django.db import transaction

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Academic Session
# ─────────────────────────────────────────────────────────────────────────────

def create_academic_session(school, *, name: str, start_date, end_date, set_as_current: bool = False):
    """
    Create a new academic session for a school.
    Optionally set it as the current session.
    Returns the AcademicSession instance.
    """
    from schools.models import AcademicSession, SchoolSettings

    session = AcademicSession.objects.create(
        school=school,
        name=name,
        start_date=start_date,
        end_date=end_date,
        is_current=set_as_current,
    )

    if set_as_current:
        settings_obj, _ = SchoolSettings.objects.get_or_create(school=school)
        settings_obj.current_session = session
        settings_obj.save(update_fields=['current_session'])

    logger.info('Academic session created: %s for %s', name, school.name)
    return session


def set_current_session(school, session):
    """Mark a session as current and update SchoolSettings."""
    from schools.models import AcademicSession, SchoolSettings

    # Deactivate all other sessions
    AcademicSession.objects.filter(school=school, is_current=True).exclude(
        pk=session.pk
    ).update(is_current=False)

    session.is_current = True
    session.save(update_fields=['is_current'])

    settings_obj, _ = SchoolSettings.objects.get_or_create(school=school)
    settings_obj.current_session = session
    settings_obj.save(update_fields=['current_session'])

    return session


def get_current_session(school):
    """Return the current academic session for a school, or None."""
    from schools.models import AcademicSession
    return AcademicSession.objects.filter(school=school, is_current=True).first()


# ─────────────────────────────────────────────────────────────────────────────
# Term Management
# ─────────────────────────────────────────────────────────────────────────────

def create_term(academic_year, *, name: str, start_date, end_date, order: int, set_as_current: bool = False):
    """Create a term within an academic year."""
    from schools.models import Term

    term = Term.objects.create(
        academic_year=academic_year,
        name=name,
        start_date=start_date,
        end_date=end_date,
        order=order,
        is_current=set_as_current,
    )
    return term


def get_current_term(school):
    """Return the current term for a school (via current academic year), or None."""
    from schools.models import AcademicYear, Term
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    if not current_year:
        return None
    return Term.objects.filter(academic_year=current_year, is_current=True).first()


# ─────────────────────────────────────────────────────────────────────────────
# Grading System
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_GRADING_SCALE = {
    'A1': {'min': 75, 'max': 100, 'remark': 'Excellent'},
    'B2': {'min': 70, 'max': 74,  'remark': 'Very Good'},
    'B3': {'min': 65, 'max': 69,  'remark': 'Good'},
    'C4': {'min': 60, 'max': 64,  'remark': 'Credit'},
    'C5': {'min': 55, 'max': 59,  'remark': 'Credit'},
    'C6': {'min': 50, 'max': 54,  'remark': 'Credit'},
    'D7': {'min': 45, 'max': 49,  'remark': 'Pass'},
    'E8': {'min': 40, 'max': 44,  'remark': 'Pass'},
    'F9': {'min': 0,  'max': 39,  'remark': 'Fail'},
}


def get_grading_scale(school) -> dict:
    """Return the school's grading scale, falling back to the Nigerian default."""
    from schools.models import SchoolSettings
    try:
        settings_obj = SchoolSettings.objects.get(school=school)
        return settings_obj.grading_scale or DEFAULT_GRADING_SCALE
    except SchoolSettings.DoesNotExist:
        return DEFAULT_GRADING_SCALE


def update_grading_scale(school, grading_scale: dict, pass_mark: int = None):
    """Update the school's grading scale and optionally the pass mark."""
    from schools.models import SchoolSettings
    settings_obj, _ = SchoolSettings.objects.get_or_create(school=school)
    settings_obj.grading_scale = grading_scale
    update_fields = ['grading_scale']
    if pass_mark is not None:
        # Store pass_mark in grading_scale metadata
        settings_obj.grading_scale['_pass_mark'] = pass_mark
    settings_obj.save(update_fields=update_fields)
    return settings_obj


def get_grade_for_score(score: float, school) -> tuple[str, str]:
    """
    Return (grade, remark) for a given score using the school's grading scale.
    Returns ('F9', 'Fail') if no matching grade is found.
    """
    scale = get_grading_scale(school)
    for grade, bounds in scale.items():
        if grade.startswith('_'):
            continue
        if isinstance(bounds, dict):
            min_score = bounds.get('min', 0)
            max_score = bounds.get('max', 100)
            if min_score <= score <= max_score:
                return grade, bounds.get('remark', '')
    return 'F9', 'Fail'


def get_pass_mark(school) -> int:
    """Return the school's pass mark (default 40)."""
    scale = get_grading_scale(school)
    return scale.get('_pass_mark', 40)


# ─────────────────────────────────────────────────────────────────────────────
# School Information
# ─────────────────────────────────────────────────────────────────────────────

def update_school_info(school, data: dict, request=None):
    """
    Update core school information fields.
    Accepted keys: name, email, phone, address, city, state, country, website
    """
    from core.services.audit_service import log_action, AuditAction

    school_fields = ['name', 'email', 'phone', 'address', 'city', 'state', 'country', 'website']
    update_fields = []
    for field in school_fields:
        if field in data:
            setattr(school, field, data[field])
            update_fields.append(field)

    if update_fields:
        update_fields.append('updated_at')
        school.save(update_fields=update_fields)
        log_action(
            action=AuditAction.SCHOOL_SETTINGS_UPDATED,
            school=school,
            request=request,
            target=school,
            metadata={'updated_fields': update_fields},
        )

    return school


def update_school_settings(school, data: dict, request=None):
    """
    Update SchoolSettings fields.
    Accepted keys: principal_name, motto, timezone, grading_system,
                   grading_scale, academic_year_start_month, allow_parent_access,
                   exam_proctoring_enabled, max_login_attempts, session_timeout_minutes
    """
    from schools.models import SchoolSettings
    from core.services.audit_service import log_action, AuditAction

    settings_obj, _ = SchoolSettings.objects.get_or_create(school=school)
    settings_fields = [
        'principal_name', 'motto', 'timezone', 'grading_system',
        'grading_scale', 'academic_year_start_month', 'allow_parent_access',
        'exam_proctoring_enabled', 'max_login_attempts', 'session_timeout_minutes',
    ]
    update_fields = []
    for field in settings_fields:
        if field in data:
            setattr(settings_obj, field, data[field])
            update_fields.append(field)

    if update_fields:
        settings_obj.save(update_fields=update_fields)
        log_action(
            action=AuditAction.SCHOOL_SETTINGS_UPDATED,
            school=school,
            request=request,
            target=settings_obj,
            metadata={'updated_fields': update_fields},
        )

    return settings_obj


def get_full_school_settings(school) -> dict:
    """Return a combined dict of school info + settings for the settings page."""
    from schools.models import SchoolSettings, AcademicSession

    try:
        settings_obj = SchoolSettings.objects.select_related(
            'current_session'
        ).get(school=school)
    except SchoolSettings.DoesNotExist:
        settings_obj = None

    return {
        # School info
        'id':      str(school.id),
        'name':    school.name,
        'slug':    school.slug,
        'email':   school.email,
        'phone':   school.phone,
        'address': school.address,
        'city':    school.city,
        'state':   school.state,
        'country': school.country,
        'website': school.website,
        'school_type': school.school_type,
        'logo_url': school.logo.url if school.logo else None,
        # Settings
        'principal_name':           settings_obj.principal_name if settings_obj else '',
        'motto':                    settings_obj.motto if settings_obj else '',
        'timezone':                 settings_obj.timezone if settings_obj else 'Africa/Lagos',
        'grading_system':           settings_obj.grading_system if settings_obj else 'percentage',
        'grading_scale':            settings_obj.grading_scale if settings_obj else DEFAULT_GRADING_SCALE,
        'academic_year_start_month': settings_obj.academic_year_start_month if settings_obj else 9,
        'allow_parent_access':      settings_obj.allow_parent_access if settings_obj else True,
        'exam_proctoring_enabled':  settings_obj.exam_proctoring_enabled if settings_obj else False,
        'max_login_attempts':       settings_obj.max_login_attempts if settings_obj else 5,
        'session_timeout_minutes':  settings_obj.session_timeout_minutes if settings_obj else 60,
        'current_session': (
            {
                'id':   str(settings_obj.current_session.id),
                'name': settings_obj.current_session.name,
            }
            if settings_obj and settings_obj.current_session else None
        ),
    }
