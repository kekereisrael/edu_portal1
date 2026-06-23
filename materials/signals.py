"""
Signals for the materials app.
Phase 6E: Auto exam generation + notification on material upload.

Triggers:
  - post_save on Material (is_published=True):
      1. Notify enrolled students that new material is available
      2. Queue auto-generation of practice questions from the material
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='materials.Material')
def on_material_saved(sender, instance, created, **kwargs):
    """
    Fired after a Material is saved.
    - On first publish: notify students + trigger question generation
    - On subsequent saves: skip (avoid re-triggering)
    """
    if not instance.is_published:
        return

    # Only act on the first publish (created OR just became published)
    # We detect "just published" by checking update_fields
    update_fields = kwargs.get('update_fields')
    if update_fields and 'is_published' not in update_fields and not created:
        return

    # Run in try/except so material save never fails due to signal errors
    try:
        _notify_material_uploaded(instance)
    except Exception as e:
        logger.error(f'[MaterialSignal] Notification failed for {instance.id}: {e}')

    try:
        _queue_question_generation(instance)
    except Exception as e:
        logger.error(f'[MaterialSignal] Question generation failed for {instance.id}: {e}')


def _notify_material_uploaded(material):
    """
    Notify all enrolled students in the material's school + subject
    that new study material is available.
    """
    from core.services.notification_delivery_service import notify_material_uploaded
    notify_material_uploaded(material)


def _queue_question_generation(material):
    """
    Trigger auto-generation of practice questions from the uploaded material.
    Runs synchronously (Celery eager mode) or async if Celery is configured.

    Only generates for document/image materials (not video/audio/links).
    """
    if material.material_type not in ('document', 'image'):
        logger.info(
            f'[MaterialSignal] Skipping question gen for '
            f'{material.material_type} material: {material.title}'
        )
        return

    # Find or create a QuestionBank for this subject in this school
    try:
        from exams.models import QuestionBank
        bank = QuestionBank.objects.filter(
            school=material.school,
            subject=material.subject,
            is_active=True,
        ).first()

        if not bank:
            logger.info(
                f'[MaterialSignal] No active QuestionBank found for '
                f'{material.subject.name} in {material.school.name}. Skipping.'
            )
            return

        from core.services.exam_generation_service import exam_generation_service

        result = exam_generation_service.generate_from_material(
            material=material,
            num_questions=10,
            difficulty='mixed',
            question_type='mcq',
            school=material.school,
            user=material.uploaded_by,
        )

        if result.success:
            saved = exam_generation_service.save_generated_questions(
                exam=None,
                result=result,
                question_bank=bank,
            )
            logger.info(
                f'[MaterialSignal] Auto-generated {saved} questions '
                f'for bank "{bank.name}" from material "{material.title}"'
            )
        else:
            logger.info(
                f'[MaterialSignal] Question generation returned no results: '
                f'{result.error_message}'
            )

    except Exception as e:
        logger.warning(f'[MaterialSignal] Question generation error: {e}')
