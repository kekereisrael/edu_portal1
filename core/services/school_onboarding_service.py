"""
School Onboarding Service — manages the multi-step school registration wizard.

Steps:
  0. Init registration (school name + email) → sends verification email
  1. Verify email token
  2. Basic school info (name, address, principal)
  3. Logo & branding
  4. Academic setup (grading, timezone)
  5. Admin account credentials
  6. Complete → atomically create School + User + Membership
"""

import logging
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


def start_registration(*, school_name: str, school_email: str, phone: str = '', ip_address: str = None):
    """
    Step 0: Create a SchoolRegistration record and send a verification email.
    Returns the SchoolRegistration instance.
    Raises ValueError if a live registration already exists for this email.
    """
    from schools.models import SchoolRegistration, SchoolVerificationToken

    live_statuses = [
        SchoolRegistration.Status.PENDING_VERIFICATION,
        SchoolRegistration.Status.EMAIL_VERIFIED,
        SchoolRegistration.Status.ONBOARDING_STEP_1,
        SchoolRegistration.Status.ONBOARDING_STEP_2,
        SchoolRegistration.Status.ONBOARDING_STEP_3,
        SchoolRegistration.Status.ONBOARDING_STEP_4,
        SchoolRegistration.Status.COMPLETED,
    ]
    if SchoolRegistration.objects.filter(school_email=school_email, status__in=live_statuses).exists():
        raise ValueError('A registration with this email already exists.')

    registration = SchoolRegistration.objects.create(
        school_name=school_name,
        school_email=school_email.lower(),
        phone=phone,
        ip_address=ip_address,
        status=SchoolRegistration.Status.PENDING_VERIFICATION,
    )

    token_obj = SchoolVerificationToken.create_for_registration(registration)
    _send_verification_email(registration, token_obj.token)
    logger.info('School registration started: %s', school_email)
    return registration


def _send_verification_email(registration, token: str):
    """Send the verification email (fire-and-forget via Celery if available)."""
    try:
        from notifications.tasks import send_school_verification_email
        send_school_verification_email.delay(str(registration.id), token)
    except ImportError:
        # Fallback: send synchronously
        from django.core.mail import send_mail
        from django.conf import settings as django_settings
        subject = 'Verify your school email — Examind'
        body = (
            f'Hello,\n\n'
            f'Thank you for registering {registration.school_name} on Examind.\n\n'
            f'Your verification token is:\n\n  {token}\n\n'
            f'This token expires in 48 hours.\n\n'
            f'— The Examind Team'
        )
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@examind.ng'),
            recipient_list=[registration.school_email],
            fail_silently=True,
        )


def verify_email(*, token_str: str):
    """
    Step 1: Verify the email token.
    Returns the updated SchoolRegistration.
    Raises ValueError on invalid/expired token.
    """
    from schools.models import SchoolVerificationToken

    try:
        token_obj = SchoolVerificationToken.objects.select_related('registration').get(
            token=token_str
        )
    except SchoolVerificationToken.DoesNotExist:
        raise ValueError('Invalid verification token.')

    if not token_obj.is_valid:
        raise ValueError('Token has expired or has already been used.')

    token_obj.mark_used()
    return token_obj.registration


def save_onboarding_step(registration, step: int, data: dict):
    """
    Generic helper to save onboarding step data.
    step: 1 (basic info), 2 (branding), 3 (academic), 4 (admin account)
    """
    from schools.models import SchoolRegistration

    status_map = {
        1: SchoolRegistration.Status.ONBOARDING_STEP_1,
        2: SchoolRegistration.Status.ONBOARDING_STEP_2,
        3: SchoolRegistration.Status.ONBOARDING_STEP_3,
        4: SchoolRegistration.Status.ONBOARDING_STEP_4,
    }

    if step == 4 and 'admin_password' in data:
        registration.admin_password_hash = make_password(data.pop('admin_password'))
        data.pop('confirm_password', None)

    for field, value in data.items():
        if hasattr(registration, field):
            setattr(registration, field, value)

    registration.status = status_map[step]
    registration.save()
    return registration


def complete_registration(registration):
    """
    Final step: atomically create School + admin User + SchoolSettings +
    SchoolMembership + seed class levels.
    Returns (school, admin_user).
    Raises ValueError on validation failure.
    """
    from schools.models import School, SchoolSettings, SchoolMembership

    required = [
        'school_name', 'school_email',
        'admin_first_name', 'admin_last_name',
        'admin_email', 'admin_password_hash',
    ]
    missing = [f for f in required if not getattr(registration, f, None)]
    if missing:
        raise ValueError(f'Missing required fields: {missing}')

    if User.objects.filter(email=registration.admin_email).exists():
        raise ValueError('An account with this admin email already exists.')

    with transaction.atomic():
        admin_user = User.objects.create(
            email=registration.admin_email,
            first_name=registration.admin_first_name,
            last_name=registration.admin_last_name,
            password=registration.admin_password_hash,
            role=User.Role.SCHOOL_ADMIN,
            is_active=True,
            is_verified=True,
        )

        school = School.objects.create(
            name=registration.school_name,
            email=registration.school_email,
            phone=registration.phone or '',
            address=registration.address or '',
            city=registration.city or '',
            state=registration.state or '',
            country=registration.country,
            website=registration.website or '',
            owner=admin_user,
            is_active=True,
        )

        if registration.logo:
            school.logo = registration.logo
            school.save(update_fields=['logo'])

        SchoolSettings.objects.create(
            school=school,
            principal_name=registration.principal_name or '',
            motto=registration.motto or '',
            timezone=registration.timezone,
            grading_system=registration.grading_system,
            academic_year_start_month=registration.academic_year_start_month,
        )

        SchoolMembership.objects.create(
            school=school,
            user=admin_user,
            role=SchoolMembership.SchoolRole.SCHOOL_ADMIN,
            is_active=True,
        )

        from core.services.school_service import _seed_class_levels
        _seed_class_levels(school)

        registration.school = school
        registration.status = registration.Status.COMPLETED
        registration.completed_at = timezone.now()
        registration.admin_password_hash = None  # clear hashed password
        registration.save()

        logger.info('School registration completed: %s (id=%s)', school.name, school.id)
        return school, admin_user
