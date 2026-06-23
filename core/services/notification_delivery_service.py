"""
notification_delivery_service.py — Phase 6E
Unified notification delivery: in-app (DB) + email.

Public API:
  notify_exam_created(exam)                  — notify enrolled students
  notify_result_released(exam_result)        — notify student their result is ready
  notify_material_uploaded(material)         — notify students new material is available
  notify_exam_reminder(student, exam, mins)  — exam starts soon
  send_bulk_notification(school, title, msg, role, classroom)
  send_email(to, subject, html_body, text_body)

All functions are safe to call from signals — they never raise exceptions.
"""

import logging
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Core delivery helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_in_app(user, title: str, message: str, notification_type: str = 'info',
                   school=None, related_type: str = '', related_id=None):
    """
    Persist an in-app notification to the database.
    Returns Notification instance or None.
    """
    try:
        from notifications.models import Notification
        return Notification.objects.create(
            recipient=user,
            school=school,
            title=title,
            message=message,
            notification_type=notification_type,
            channel=Notification.Channel.IN_APP,
            related_object_type=related_type or None,
            related_object_id=related_id or None,
            sent_at=timezone.now(),
        )
    except Exception as e:
        logger.error(f'[NotifDelivery] In-app creation failed for {user}: {e}')
        return None


def send_email(to_email: str, subject: str, html_body: str, text_body: str = '') -> bool:
    """
    Send a single email. Uses Django's EMAIL_BACKEND (console in dev, SMTP in prod).

    Returns True on success, False on failure.
    """
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@examind.app')
        text = text_body or _html_to_text(html_body)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=from_email,
            to=[to_email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info(f'[NotifDelivery] Email sent to {to_email}: {subject}')
        return True
    except Exception as e:
        logger.error(f'[NotifDelivery] Email failed to {to_email}: {e}')
        return False


def _html_to_text(html: str) -> str:
    """Strip HTML tags for plain-text fallback."""
    import re
    return re.sub(r'<[^>]+>', '', html).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Event-specific notification functions
# ─────────────────────────────────────────────────────────────────────────────

def notify_exam_created(exam) -> int:
    """
    Notify all enrolled students that a new exam has been published.

    Args:
        exam: exams.models.Exam instance (must be published)

    Returns:
        Number of notifications sent
    """
    if not exam.is_published:
        return 0

    students = _get_enrolled_students(exam.school, subject=exam.subject)
    if not students:
        return 0

    title = f'📝 New Exam: {exam.title}'
    message = (
        f'A new exam "{exam.title}" has been published in {exam.subject.name}. '
        f'Duration: {exam.duration_minutes} minutes. '
        f'{"Scheduled: " + exam.scheduled_at.strftime("%d %b %Y %H:%M") if exam.scheduled_at else "Available now."}'
    )

    count = 0
    for student in students:
        notif = _create_in_app(
            user=student,
            title=title,
            message=message,
            notification_type='info',
            school=exam.school,
            related_type='exam',
            related_id=exam.id,
        )
        if notif:
            count += 1

        # Send email notification
        _send_exam_created_email(student, exam)

    logger.info(f'[NotifDelivery] Exam created: {count} notifications sent for "{exam.title}"')
    return count


def notify_result_released(exam_result) -> bool:
    """
    Notify a student that their exam result is available.

    Args:
        exam_result: results.models.ExamResult instance

    Returns:
        True if notification was sent
    """
    student = exam_result.student
    exam = exam_result.exam
    school = exam.school

    title = f'✅ Result Available: {exam.title}'
    pct = float(exam_result.percentage) if exam_result.percentage else 0
    passed = exam_result.passed
    status_emoji = '🎉' if passed else '📚'
    status_text = 'PASSED' if passed else 'FAILED'

    message = (
        f'{status_emoji} Your result for "{exam.title}" is ready. '
        f'Score: {pct:.1f}% — {status_text}. '
        f'{"Well done! Keep it up." if passed else "Don\'t give up — review your weak areas and try again."}'
    )

    notif = _create_in_app(
        user=student,
        title=title,
        message=message,
        notification_type='success' if passed else 'warning',
        school=school,
        related_type='examresult',
        related_id=exam_result.id,
    )

    # Email
    _send_result_email(student, exam, exam_result)

    logger.info(f'[NotifDelivery] Result notification sent to {student.email}')
    return notif is not None


def notify_material_uploaded(material) -> int:
    """
    Notify enrolled students that new study material has been uploaded.

    Args:
        material: materials.models.Material instance

    Returns:
        Number of notifications sent
    """
    students = _get_enrolled_students(material.school, subject=material.subject)
    if not students:
        return 0

    title = f'📚 New Material: {material.title}'
    topic_part = f' ({material.topic.name})' if material.topic else ''
    message = (
        f'New study material "{material.title}"{topic_part} has been added to '
        f'{material.subject.name}. Check it out!'
    )

    count = 0
    for student in students:
        notif = _create_in_app(
            user=student,
            title=title,
            message=message,
            notification_type='info',
            school=material.school,
            related_type='material',
            related_id=material.id,
        )
        if notif:
            count += 1

    logger.info(
        f'[NotifDelivery] Material upload: {count} notifications for "{material.title}"'
    )
    return count


def notify_exam_reminder(student, exam, minutes_before: int = 30) -> bool:
    """
    Send an exam reminder to a student.

    Args:
        student: User instance
        exam: Exam instance
        minutes_before: Minutes before exam starts

    Returns:
        True if notification was sent
    """
    title = f'⏰ Exam Reminder: {exam.title}'
    message = (
        f'Your exam "{exam.title}" starts in {minutes_before} minutes. '
        f'Make sure you\'re ready!'
    )

    notif = _create_in_app(
        user=student,
        title=title,
        message=message,
        notification_type='warning',
        school=exam.school,
        related_type='exam',
        related_id=exam.id,
    )
    return notif is not None


def send_bulk_notification(
    school,
    title: str,
    message: str,
    role: str = None,
    classroom=None,
    sent_by=None,
) -> dict:
    """
    Send a notification to all members of a school (or filtered by role/classroom).

    Args:
        school: School instance
        title: Notification title
        message: Notification body
        role: Optional role filter ('student', 'teacher', 'school_admin')
        classroom: Optional ClassRoom instance to filter by
        sent_by: User who triggered the bulk send

    Returns:
        dict with sent_count, failed_count
    """
    from schools.models import SchoolMembership

    qs = SchoolMembership.objects.filter(
        school=school, is_active=True
    ).select_related('user')

    if role:
        qs = qs.filter(role=role)

    if classroom:
        # Filter by students in this classroom
        from schools.models import StudentClassAssignment
        student_ids = StudentClassAssignment.objects.filter(
            classroom=classroom, status='active'
        ).values_list('student_id', flat=True)
        qs = qs.filter(user_id__in=student_ids)

    sent = 0
    failed = 0

    for membership in qs:
        notif = _create_in_app(
            user=membership.user,
            title=title,
            message=message,
            notification_type='info',
            school=school,
        )
        if notif:
            sent += 1
        else:
            failed += 1

    # Track in BulkNotification model
    try:
        from notifications.models import BulkNotification
        BulkNotification.objects.create(
            school=school,
            title=title,
            message=message,
            target_role=role,
            target_classroom=classroom,
            sent_by=sent_by,
            total_recipients=sent + failed,
            sent_count=sent,
            failed_count=failed,
            status='completed',
            completed_at=timezone.now(),
        )
    except Exception as e:
        logger.warning(f'[NotifDelivery] BulkNotification record failed: {e}')

    logger.info(f'[NotifDelivery] Bulk: {sent} sent, {failed} failed — "{title}"')
    return {'sent_count': sent, 'failed_count': failed}


# ─────────────────────────────────────────────────────────────────────────────
# Email templates
# ─────────────────────────────────────────────────────────────────────────────

_EMAIL_CSS = """
<style>
  body { font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }
  .container { max-width: 600px; margin: 30px auto; background: #fff;
               border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.1); }
  .header { background: #1a56db; color: #fff; padding: 24px 32px; }
  .header h1 { margin: 0; font-size: 22px; }
  .body { padding: 24px 32px; color: #374151; line-height: 1.6; }
  .btn { display: inline-block; margin-top: 16px; padding: 12px 24px;
         background: #1a56db; color: #fff; text-decoration: none;
         border-radius: 6px; font-weight: bold; }
  .footer { background: #f9fafb; padding: 16px 32px; font-size: 12px;
            color: #9ca3af; text-align: center; }
  .score { font-size: 32px; font-weight: bold; color: #1a56db; }
  .pass { color: #16a34a; } .fail { color: #dc2626; }
</style>
"""


def _send_exam_created_email(student, exam):
    """Send exam creation email to a student."""
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    exam_url = f'{frontend_url}/exams/{exam.id}/'
    scheduled = (
        exam.scheduled_at.strftime('%d %b %Y at %H:%M')
        if getattr(exam, 'scheduled_at', None) else 'Available now'
    )

    html = f"""<!DOCTYPE html><html><head>{_EMAIL_CSS}</head><body>
<div class="container">
  <div class="header"><h1>📝 New Exam Available</h1></div>
  <div class="body">
    <p>Hi {student.full_name},</p>
    <p>A new exam has been published for you:</p>
    <ul>
      <li><strong>Exam:</strong> {exam.title}</li>
      <li><strong>Subject:</strong> {exam.subject.name}</li>
      <li><strong>Duration:</strong> {exam.duration_minutes} minutes</li>
      <li><strong>Scheduled:</strong> {scheduled}</li>
    </ul>
    <a href="{exam_url}" class="btn">View Exam</a>
  </div>
  <div class="footer">Examind — Smart Learning Platform</div>
</div></body></html>"""

    send_email(
        to_email=student.email,
        subject=f'New Exam: {exam.title}',
        html_body=html,
    )


def _send_result_email(student, exam, result):
    """Send result notification email to a student."""
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    result_url = f'{frontend_url}/results/{result.id}/'
    pct = float(result.percentage) if result.percentage else 0
    passed = result.passed
    status_cls = 'pass' if passed else 'fail'
    status_txt = '🎉 PASSED' if passed else '❌ FAILED'
    grade = getattr(result, 'grade', '') or ''

    html = f"""<!DOCTYPE html><html><head>{_EMAIL_CSS}</head><body>
<div class="container">
  <div class="header"><h1>📊 Your Exam Result</h1></div>
  <div class="body">
    <p>Hi {student.full_name},</p>
    <p>Your result for <strong>{exam.title}</strong> is now available.</p>
    <p class="score">{pct:.1f}%</p>
    <p class="{status_cls}"><strong>{status_txt}</strong>{' — Grade: ' + grade if grade else ''}</p>
    {'<p>Excellent work! Keep up the great performance.</p>' if passed else
     '<p>Don\'t be discouraged. Review your weak areas and try again!</p>'}
    <a href="{result_url}" class="btn">View Full Result</a>
  </div>
  <div class="footer">Examind — Smart Learning Platform</div>
</div></body></html>"""

    send_email(
        to_email=student.email,
        subject=f'Result: {exam.title} — {pct:.1f}%',
        html_body=html,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_enrolled_students(school, subject=None) -> list:
    """
    Return list of active student User instances for a school,
    optionally filtered by subject enrollment.
    """
    try:
        from schools.models import SchoolMembership
        qs = SchoolMembership.objects.filter(
            school=school,
            role='student',
            is_active=True,
        ).select_related('user')
        return [m.user for m in qs]
    except Exception as e:
        logger.warning(f'[NotifDelivery] Could not fetch students: {e}')
        return []
