"""
Celery tasks for the exams app.
Handles auto-grading, exam scheduling, and result processing.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def auto_grade_exam(self, attempt_id):
    """
    Automatically grade an exam attempt.
    Grades objective questions (MCQ, true/false) and calculates scores.
    """
    try:
        from exams.models import ExamAttempt, Answer, Result, Question

        attempt = ExamAttempt.objects.select_related('exam').get(id=attempt_id)

        if attempt.status != 'submitted':
            logger.warning(f"Attempt {attempt_id} is not in submitted state")
            return

        exam = attempt.exam
        answers = Answer.objects.filter(attempt=attempt).select_related('question')

        total_marks = 0
        obtained_marks = 0
        auto_graded_count = 0
        needs_manual_grading = False

        for answer in answers:
            question = answer.question
            total_marks += question.marks

            if question.question_type in ['mcq', 'true_false']:
                # Auto-grade objective questions
                is_correct = _check_answer(question, answer)
                answer.is_correct = is_correct
                answer.marks_obtained = question.marks if is_correct else 0
                answer.graded_at = timezone.now()
                answer.save(update_fields=['is_correct', 'marks_obtained', 'graded_at'])

                obtained_marks += answer.marks_obtained
                auto_graded_count += 1
            else:
                # Subjective questions need manual grading
                needs_manual_grading = True

        # Also count unanswered questions
        answered_question_ids = answers.values_list('question_id', flat=True)
        unanswered = Question.objects.filter(
            exam=exam
        ).exclude(id__in=answered_question_ids)

        for question in unanswered:
            total_marks += question.marks

        # Create or update result
        if not needs_manual_grading:
            percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
            pass_mark = exam.pass_percentage or 50

            Result.objects.update_or_create(
                attempt=attempt,
                defaults={
                    'total_marks': total_marks,
                    'obtained_marks': obtained_marks,
                    'percentage': round(percentage, 2),
                    'grade': _calculate_grade(percentage),
                    'is_passed': percentage >= pass_mark,
                    'graded_by': 'system',
                    'graded_at': timezone.now(),
                }
            )

            attempt.status = 'graded'
            attempt.save(update_fields=['status', 'updated_at'])

            # Send result notification
            from notifications.tasks import send_result_notification
            result = Result.objects.get(attempt=attempt)
            send_result_notification.delay(str(result.id))
        else:
            # Partial grading - save what we have
            Result.objects.update_or_create(
                attempt=attempt,
                defaults={
                    'total_marks': total_marks,
                    'obtained_marks': obtained_marks,
                    'percentage': 0,  # Will be updated after manual grading
                    'graded_by': 'partial_auto',
                    'graded_at': timezone.now(),
                }
            )

        logger.info(
            f"Auto-graded {auto_graded_count} questions for attempt {attempt_id}. "
            f"Score: {obtained_marks}/{total_marks}. "
            f"Needs manual: {needs_manual_grading}"
        )
    except Exception as exc:
        logger.error(f"Failed to auto-grade attempt {attempt_id}: {exc}")
        self.retry(exc=exc)


@shared_task
def auto_submit_expired_exams():
    """
    Auto-submit exam attempts that have exceeded their time limit.
    Runs periodically to catch any missed auto-submissions.
    """
    from exams.models import ExamAttempt

    now = timezone.now()

    # Find in-progress attempts that have exceeded time
    expired_attempts = ExamAttempt.objects.filter(
        status='in_progress',
    ).select_related('exam')

    submitted_count = 0
    for attempt in expired_attempts:
        if attempt.exam.duration_minutes:
            expiry_time = attempt.started_at + timezone.timedelta(
                minutes=attempt.exam.duration_minutes
            )
            if now > expiry_time:
                attempt.status = 'submitted'
                attempt.submitted_at = now
                attempt.auto_submitted = True
                attempt.save(update_fields=['status', 'submitted_at', 'auto_submitted', 'updated_at'])

                # Trigger auto-grading
                auto_grade_exam.delay(str(attempt.id))
                submitted_count += 1

    if submitted_count:
        logger.info(f"Auto-submitted {submitted_count} expired exam attempts")


@shared_task
def generate_exam_analytics(exam_id):
    """Generate analytics for a completed exam."""
    from exams.models import Exam, ExamAttempt, Result
    from django.db.models import Avg, Count, Max, Min, StdDev

    try:
        exam = Exam.objects.get(id=exam_id)

        results = Result.objects.filter(attempt__exam=exam)

        if not results.exists():
            return

        stats = results.aggregate(
            avg_score=Avg('percentage'),
            max_score=Max('percentage'),
            min_score=Min('percentage'),
            std_dev=StdDev('percentage'),
            total_attempts=Count('id'),
            pass_count=Count('id', filter=models.Q(is_passed=True)),
        )

        # Store in exam metadata
        exam.analytics_data = {
            'average_score': float(stats['avg_score'] or 0),
            'highest_score': float(stats['max_score'] or 0),
            'lowest_score': float(stats['min_score'] or 0),
            'std_deviation': float(stats['std_dev'] or 0),
            'total_attempts': stats['total_attempts'],
            'pass_rate': (stats['pass_count'] / stats['total_attempts'] * 100)
            if stats['total_attempts'] > 0 else 0,
            'generated_at': timezone.now().isoformat(),
        }
        exam.save(update_fields=['analytics_data', 'updated_at'])

        logger.info(f"Analytics generated for exam {exam_id}")
    except Exception as exc:
        logger.error(f"Failed to generate exam analytics: {exc}")


def _check_answer(question, answer):
    """Check if an answer is correct for objective questions."""
    if question.question_type == 'mcq':
        # Check if selected option is the correct one
        from exams.models import QuestionOption
        correct_option = QuestionOption.objects.filter(
            question=question,
            is_correct=True,
        ).first()

        if correct_option and answer.selected_option_id == correct_option.id:
            return True
        return False

    elif question.question_type == 'true_false':
        correct_answer = question.correct_answer
        if correct_answer and answer.text_answer:
            return answer.text_answer.lower().strip() == correct_answer.lower().strip()
        return False

    return False


def _calculate_grade(percentage):
    """Calculate letter grade from percentage."""
    if percentage >= 90:
        return 'A+'
    elif percentage >= 80:
        return 'A'
    elif percentage >= 70:
        return 'B'
    elif percentage >= 60:
        return 'C'
    elif percentage >= 50:
        return 'D'
    elif percentage >= 40:
        return 'E'
    else:
        return 'F'
