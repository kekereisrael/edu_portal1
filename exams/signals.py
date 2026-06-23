"""
Signals for the exams app.
Phase 6E: Notification delivery on exam publish and result release.

Triggers:
  - Exam.is_published → True  : notify enrolled students
  - ExamResult saved          : notify student their result is ready
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='exams.Exam')
def on_exam_published(sender, instance, created, **kwargs):
    """
    Fire when an Exam is saved with is_published=True.
    Notifies all enrolled students.
    """
    if not instance.is_published:
        return

    # Only notify on the transition to published (not every save)
    update_fields = kwargs.get('update_fields')
    if update_fields and 'is_published' not in update_fields and not created:
        return

    try:
        from core.services.notification_delivery_service import notify_exam_created
        notify_exam_created(instance)
    except Exception as e:
        logger.error(f'[ExamSignal] notify_exam_created failed for {instance.id}: {e}')


@receiver(post_save, sender='exams.ExamResult')
def on_result_saved(sender, instance, created, **kwargs):
    """
    Fire when an ExamResult is first created.
    Notifies the student that their result is available.
    ExamResult has no is_published flag — every creation means the result is ready.
    """
    if not created:
        return  # Only notify on first creation, not subsequent updates

    try:
        from core.services.notification_delivery_service import notify_result_released
        notify_result_released(instance)
    except Exception as e:
        logger.error(f'[ExamSignal] notify_result_released failed for {instance.id}: {e}')
