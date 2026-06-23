"""
Signals for the achievements app.
Auto-award badges after exam attempts, practice sessions, and mock exams.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='exams.ExamAttempt')
def check_badges_on_exam_attempt(sender, instance, created, **kwargs):
    """Award badges when an exam attempt is graded."""
    if instance.status in ('graded', 'submitted') and instance.percentage is not None:
        from achievements.services.badge_service import evaluate_badges_for_student
        try:
            evaluate_badges_for_student(
                student=instance.student,
                school=instance.exam.school,
                trigger='exam_attempt',
                context={
                    'attempt': instance,
                    'exam': instance.exam,
                    'percentage': float(instance.percentage),
                    'passed': instance.passed,
                },
            )
        except Exception:
            pass  # Never break exam submission due to badge errors


@receiver(post_save, sender='exams.MockExamSession')
def check_badges_on_mock_exam(sender, instance, created, **kwargs):
    """Award badges when a mock exam is submitted."""
    if instance.status in ('submitted', 'timed_out') and instance.percentage is not None:
        from achievements.services.badge_service import evaluate_badges_for_student
        try:
            evaluate_badges_for_student(
                student=instance.student,
                school=instance.bank.school,
                trigger='mock_exam',
                context={
                    'session': instance,
                    'percentage': float(instance.percentage),
                    'passed': instance.passed,
                },
            )
        except Exception:
            pass


@receiver(post_save, sender='exams.PracticeSession')
def check_badges_on_practice(sender, instance, created, **kwargs):
    """Award badges when a practice session is completed."""
    if instance.status == 'completed':
        from achievements.services.badge_service import evaluate_badges_for_student
        try:
            evaluate_badges_for_student(
                student=instance.student,
                school=instance.bank.school,
                trigger='practice_session',
                context={'session': instance},
            )
        except Exception:
            pass
