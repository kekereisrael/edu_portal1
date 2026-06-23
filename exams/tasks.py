"""
Celery tasks for the exams app.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def auto_submit_expired_attempt(self, attempt_id):
    """Auto-submit an exam attempt that has exceeded its time limit."""
    try:
        from exams.models import ExamAttempt
        attempt = ExamAttempt.objects.select_related('exam').get(id=attempt_id)
        if attempt.status == ExamAttempt.Status.IN_PROGRESS:
            attempt.submit(auto=True)
            logger.info(f'Auto-submitted attempt {attempt_id}')
    except Exception as exc:
        logger.error(f'Failed to auto-submit attempt {attempt_id}: {exc}')
        self.retry(exc=exc)


@shared_task
def auto_submit_expired_exams():
    """Periodic task: auto-submit all expired in-progress attempts."""
    from exams.models import ExamAttempt
    now = timezone.now()
    expired = ExamAttempt.objects.filter(
        status=ExamAttempt.Status.IN_PROGRESS
    ).select_related('exam')

    count = 0
    for attempt in expired:
        if attempt.exam.duration_minutes:
            expiry = attempt.started_at + timezone.timedelta(minutes=attempt.exam.duration_minutes)
            if now > expiry:
                attempt.submit(auto=True)
                count += 1

    if count:
        logger.info(f'Auto-submitted {count} expired exam attempts')
    return count


@shared_task
def send_exam_result_notification(attempt_id):
    """Send notification to student after exam grading."""
    try:
        from exams.models import ExamAttempt
        from notifications.models import Notification
        attempt = ExamAttempt.objects.select_related('exam', 'student').get(id=attempt_id)
        if attempt.status == ExamAttempt.Status.GRADED:
            passed_text = 'Passed ✓' if attempt.passed else 'Failed ✗'
            Notification.objects.create(
                school=attempt.exam.school,
                recipient=attempt.student,
                title=f'Exam Result: {attempt.exam.title}',
                message=(
                    f'Your result for "{attempt.exam.title}" is ready. '
                    f'Score: {attempt.percentage}% — {passed_text}'
                ),
                notification_type='success' if attempt.passed else 'warning',
                channel='in_app',
                related_object_type='exam_attempt',
                related_object_id=attempt.id,
            )
    except Exception as exc:
        logger.error(f'Failed to send result notification for attempt {attempt_id}: {exc}')
