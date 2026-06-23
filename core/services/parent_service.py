"""
Parent Service — business logic for parent management.

Handles:
  - Creating parent users and profiles
  - Linking parents to students (ParentStudentLink)
  - Parent dashboard data aggregation
  - Notification preferences
"""

import logging
from django.contrib.auth import get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)
User = get_user_model()


def create_parent_user(
    *,
    school,
    email: str,
    first_name: str,
    last_name: str,
    phone: str = '',
    password: str = None,
    invited_by=None,
    send_welcome_email: bool = True,
):
    """
    Create a new parent User + ParentProfile + SchoolMembership.
    If the user already exists (by email), add them to the school.
    Returns (user, membership, created_user: bool).
    """
    from schools.models import SchoolMembership
    from parents.models import ParentProfile

    created_user = False
    temp_password = None

    with transaction.atomic():
        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            import secrets
            temp_password = password or secrets.token_urlsafe(12)
            user = User.objects.create_user(
                email=email.lower(),
                password=temp_password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=User.Role.PARENT,
                is_active=True,
            )
            created_user = True

        # Ensure ParentProfile exists
        ParentProfile.objects.get_or_create(user=user)

        # Create or reactivate membership
        membership, _ = SchoolMembership.objects.get_or_create(
            school=school,
            user=user,
            defaults={'role': SchoolMembership.SchoolRole.PARENT, 'is_active': True},
        )
        if not membership.is_active or membership.role != SchoolMembership.SchoolRole.PARENT:
            membership.role = SchoolMembership.SchoolRole.PARENT
            membership.is_active = True
            membership.save(update_fields=['role', 'is_active'])

    if send_welcome_email and created_user:
        _send_parent_welcome_email(user, school, temp_password)

    logger.info(
        'Parent %s added to school %s (created=%s)',
        email, school.name, created_user,
    )
    return user, membership, created_user


def _send_parent_welcome_email(user, school, temp_password: str):
    """Send a welcome email to a newly created parent."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings as django_settings
        subject = f"Welcome to {school.name} Parent Portal — Examind"
        body = (
            f"Hello {user.first_name or user.email},\n\n"
            f"You have been added as a parent on {school.name}'s Examind portal.\n\n"
            f"Your login credentials:\n"
            f"  Email:    {user.email}\n"
            f"  Password: {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— The Examind Team"
        )
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@examind.ng'),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning('Failed to send parent welcome email to %s: %s', user.email, exc)


def link_parent_to_student(
    *,
    school,
    parent_user,
    student_user,
    relationship: str = 'parent',
    linked_by=None,
    auto_approve: bool = True,
):
    """
    Create a ParentStudentLink between parent and student in the same school.
    Returns the ParentStudentLink instance.
    Raises ValueError on validation failure.
    """
    from schools.models import ParentStudentLink, SchoolMembership

    # Validate parent membership
    if not SchoolMembership.objects.filter(
        school=school, user=parent_user,
        role=SchoolMembership.SchoolRole.PARENT, is_active=True,
    ).exists():
        raise ValueError(f'{parent_user.email} is not an active parent in {school.name}.')

    # Validate student membership
    if not SchoolMembership.objects.filter(
        school=school, user=student_user,
        role=SchoolMembership.SchoolRole.STUDENT, is_active=True,
    ).exists():
        raise ValueError(f'{student_user.email} is not an active student in {school.name}.')

    link, created = ParentStudentLink.objects.get_or_create(
        school=school,
        parent=parent_user,
        student=student_user,
        defaults={
            'relationship': relationship,
            'linked_by': linked_by,
            'status': (
                ParentStudentLink.Status.APPROVED
                if auto_approve
                else ParentStudentLink.Status.PENDING
            ),
        },
    )

    if not created:
        # Update existing link
        link.relationship = relationship
        if auto_approve:
            link.status = ParentStudentLink.Status.APPROVED
        link.save(update_fields=['relationship', 'status'])

    logger.info(
        'Parent %s linked to student %s in school %s',
        parent_user.email, student_user.email, school.name,
    )
    return link


def unlink_parent_from_student(*, school, parent_user, student_user):
    """Remove a parent-student link."""
    from schools.models import ParentStudentLink
    deleted, _ = ParentStudentLink.objects.filter(
        school=school,
        parent=parent_user,
        student=student_user,
    ).delete()
    if not deleted:
        raise ValueError('No link found between this parent and student.')


def get_parent_children(parent_user, school):
    """
    Return a queryset of approved student users linked to this parent
    in the given school.
    """
    from schools.models import ParentStudentLink
    from django.contrib.auth import get_user_model
    User = get_user_model()

    student_ids = ParentStudentLink.objects.filter(
        school=school,
        parent=parent_user,
        status=ParentStudentLink.Status.APPROVED,
    ).values_list('student_id', flat=True)

    return User.objects.filter(id__in=student_ids)


def get_parent_dashboard_data(parent_user, school) -> dict:
    """
    Aggregate data for the parent dashboard:
    - List of linked children with their current class
    - Recent exam results per child
    - Upcoming exams
    - Attendance summary (if available)
    """
    from schools.models import ParentStudentLink, StudentClassAssignment

    links = ParentStudentLink.objects.filter(
        school=school,
        parent=parent_user,
        status=ParentStudentLink.Status.APPROVED,
    ).select_related('student')

    children_data = []
    for link in links:
        student = link.student

        # Current class assignment
        current_assignment = StudentClassAssignment.objects.filter(
            school=school,
            student=student,
            status=StudentClassAssignment.Status.ACTIVE,
        ).select_related('classroom', 'academic_session').first()

        # Recent results (last 5)
        try:
            from results.models import Result
            recent_results = Result.objects.filter(
                school=school,
                student=student,
            ).order_by('-created_at')[:5]
            results_data = [
                {
                    'subject': r.subject.name if hasattr(r, 'subject') else '',
                    'score': getattr(r, 'score', None),
                    'grade': getattr(r, 'grade', None),
                    'date': r.created_at.date().isoformat() if hasattr(r, 'created_at') else None,
                }
                for r in recent_results
            ]
        except Exception:
            results_data = []

        children_data.append({
            'student_id': str(student.id),
            'student_name': student.get_full_name(),
            'student_email': student.email,
            'relationship': link.relationship,
            'current_class': (
                {
                    'classroom': current_assignment.classroom.name,
                    'session': current_assignment.academic_session.name,
                }
                if current_assignment else None
            ),
            'recent_results': results_data,
        })

    return {
        'school_name': school.name,
        'parent_name': parent_user.get_full_name(),
        'children_count': len(children_data),
        'children': children_data,
    }


def get_parents_for_student(student_user, school):
    """Return all approved parent users linked to a student in a school."""
    from schools.models import ParentStudentLink
    from django.contrib.auth import get_user_model
    User = get_user_model()

    parent_ids = ParentStudentLink.objects.filter(
        school=school,
        student=student_user,
        status=ParentStudentLink.Status.APPROVED,
    ).values_list('parent_id', flat=True)

    return User.objects.filter(id__in=parent_ids)
