"""
Celery tasks for the notifications app.
Handles notification delivery, push notifications, and cleanup.
"""

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification(self, notification_id):
    """
    Send a notification through all configured channels.
    Supports: in-app, email, push notification.
    """
    try:
        from notifications.models import Notification

        notification = Notification.objects.select_related('user').get(id=notification_id)

        channels = notification.channels or ['in_app']

        if 'email' in channels:
            _send_email_notification(notification)

        if 'push' in channels:
            _send_push_notification(notification)

        notification.sent_at = timezone.now()
        notification.save(update_fields=['sent_at'])

        logger.info(f"Notification {notification_id} sent via {channels}")
    except Exception as exc:
        logger.error(f"Failed to send notification {notification_id}: {exc}")
        self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_bulk_notification(self, bulk_notification_id):
    """Send a bulk notification to multiple recipients."""
    try:
        from notifications.models import BulkNotification, Notification

        bulk = BulkNotification.objects.get(id=bulk_notification_id)
        recipients = bulk.get_recipients()

        created_count = 0
        for user in recipients:
            notification = Notification.objects.create(
                user=user,
                school=bulk.school,
                title=bulk.title,
                message=bulk.message,
                notification_type=bulk.notification_type,
                channels=bulk.channels,
                priority=bulk.priority,
            )
            send_notification.delay(str(notification.id))
            created_count += 1

        bulk.sent_count = created_count
        bulk.status = 'sent'
        bulk.sent_at = timezone.now()
        bulk.save(update_fields=['sent_count', 'status', 'sent_at'])

        logger.info(f"Bulk notification {bulk_notification_id} sent to {created_count} recipients")
    except Exception as exc:
        logger.error(f"Failed to send bulk notification: {exc}")
        self.retry(exc=exc)


@shared_task
def cleanup_old_notifications():
    """Remove read notifications older than 90 days."""
    from notifications.models import Notification

    threshold = timezone.now() - timedelta(days=90)

    deleted = Notification.objects.filter(
        is_read=True,
        created_at__lt=threshold,
    ).delete()

    logger.info(f"Cleaned up {deleted[0]} old notifications")


@shared_task
def send_exam_reminder(exam_id, minutes_before=30):
    """Send reminder notification before an exam starts."""
    from exams.models import Exam
    from notifications.models import Notification
    from subjects.models import Enrollment

    try:
        exam = Exam.objects.select_related('subject', 'school').get(id=exam_id)

        # Get enrolled students
        enrollments = Enrollment.objects.filter(
            subject=exam.subject,
            status='active',
        ).select_related('student')

        for enrollment in enrollments:
            Notification.objects.create(
                user=enrollment.student,
                school=exam.school,
                title=f'Exam Reminder: {exam.title}',
                message=f'Your exam "{exam.title}" starts in {minutes_before} minutes.',
                notification_type='exam_reminder',
                channels=['in_app', 'push'],
                priority='high',
            )

        logger.info(f"Exam reminders sent for exam {exam_id}")
    except Exception as exc:
        logger.error(f"Failed to send exam reminders: {exc}")


@shared_task
def send_result_notification(result_id):
    """Notify student when their exam result is available."""
    from exams.models import Result
    from notifications.models import Notification

    try:
        result = Result.objects.select_related(
            'attempt__student', 'attempt__exam', 'attempt__school'
        ).get(id=result_id)

        student = result.attempt.student
        exam = result.attempt.exam

        Notification.objects.create(
            user=student,
            school=result.attempt.school,
            title=f'Result Available: {exam.title}',
            message=f'Your result for "{exam.title}" is now available. Score: {result.percentage}%',
            notification_type='result_available',
            channels=['in_app', 'email', 'push'],
            priority='high',
            data={
                'exam_id': str(exam.id),
                'result_id': str(result.id),
                'score': float(result.percentage),
            }
        )

        logger.info(f"Result notification sent to {student.email}")
    except Exception as exc:
        logger.error(f"Failed to send result notification: {exc}")


def _send_email_notification(notification):
    """Send notification via email."""
    try:
        send_mail(
            subject=notification.title,
            message=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error(f"Email notification failed: {exc}")


def _send_push_notification(notification):
    """Send push notification (placeholder for FCM/APNs integration)."""
    from notifications.models import DeviceToken

    tokens = DeviceToken.objects.filter(
        user=notification.user,
        is_active=True,
    )

    for token in tokens:
        try:
            # TODO: Integrate with FCM/APNs
            # For now, just log the attempt
            logger.info(
                f"Push notification queued for device {token.device_type}: "
                f"{notification.title}"
            )
        except Exception as exc:
            logger.error(f"Push notification failed for token {token.id}: {exc}")
