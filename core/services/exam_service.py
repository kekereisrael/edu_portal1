"""
Exam service layer.
Handles all business logic for exam operations.
"""

import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


def get_exam_questions(exam):
    """
    Fetch questions for an exam safely.
    
    Args:
        exam: Exam model instance
    
    Returns:
        QuerySet of questions or empty queryset
    """
    try:
        from exams.models import Question
        questions = exam.questions.all().prefetch_related('options', 'tags')
        return questions
    except Exception as exc:
        logger.error(f"Error fetching questions for exam {exam.id}: {exc}")
        from exams.models import Question
        return Question.objects.none()


def get_exam_questions_for_student(exam, shuffle=None):
    """
    Fetch questions for a student taking an exam.
    Respects shuffle settings and hides correct answers.
    
    Args:
        exam: Exam model instance
        shuffle: Override shuffle setting (None = use exam setting)
    
    Returns:
        QuerySet of questions
    """
    questions = get_exam_questions(exam)

    should_shuffle = shuffle if shuffle is not None else exam.shuffle_questions
    if should_shuffle:
        questions = questions.order_by('?')

    return questions


def validate_exam_availability(exam, user):
    """
    Validate whether a user can take an exam.
    
    Args:
        exam: Exam model instance
        user: User model instance
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    from exams.models import ExamAttempt

    # Check if exam is published
    if not exam.is_published:
        return False, 'This exam is not published.'

    # Check if exam is within time window
    if not exam.is_available:
        if exam.is_upcoming:
            return False, f'This exam has not started yet. It begins at {exam.start_time}.'
        if exam.is_past:
            return False, 'This exam has ended.'
        return False, 'This exam is not currently available.'

    # Check max attempts
    existing_attempts = ExamAttempt.objects.filter(
        exam=exam, student=user
    ).count()

    if exam.max_attempts != -1 and existing_attempts >= exam.max_attempts:
        return False, f'Maximum attempts ({exam.max_attempts}) reached.'

    return True, None


def get_or_resume_attempt(exam, user):
    """
    Get an existing in-progress attempt or return None.
    Handles timed-out attempts automatically.
    
    Args:
        exam: Exam model instance
        user: User model instance
    
    Returns:
        ExamAttempt or None
    """
    from exams.models import ExamAttempt

    in_progress = ExamAttempt.objects.filter(
        exam=exam, student=user, status=ExamAttempt.Status.IN_PROGRESS
    ).first()

    if in_progress:
        if in_progress.is_timed_out:
            in_progress.timeout()
            return None
        return in_progress

    return None


def create_exam_attempt(exam, user, ip_address='127.0.0.1'):
    """
    Create a new exam attempt.
    
    Args:
        exam: Exam model instance
        user: User model instance
        ip_address: Client IP address
    
    Returns:
        ExamAttempt instance
    """
    from exams.models import ExamAttempt

    existing_attempts = ExamAttempt.objects.filter(
        exam=exam, student=user
    ).count()

    attempt = ExamAttempt.objects.create(
        exam=exam,
        student=user,
        school=exam.school,
        attempt_number=existing_attempts + 1,
        ip_address=ip_address,
    )

    return attempt


def calculate_exam_score(attempt):
    """
    Calculate and update the score for an exam attempt.
    Auto-grades objective questions.
    
    Args:
        attempt: ExamAttempt instance
    
    Returns:
        dict with score details
    """
    total_score = 0
    all_graded = True

    for answer in attempt.answers.select_related('question'):
        if answer.question.question_type in ['mcq', 'true_false', 'fill_blank']:
            answer.auto_grade()
            if answer.marks_awarded is not None:
                total_score += answer.marks_awarded
        else:
            all_graded = False

    attempt.score = total_score
    if attempt.exam.total_marks > 0:
        attempt.percentage = (total_score / attempt.exam.total_marks) * 100

    from exams.models import ExamAttempt
    if all_graded:
        attempt.status = ExamAttempt.Status.GRADED

    attempt.save(update_fields=['score', 'percentage', 'status', 'updated_at'])

    return {
        'score': float(total_score),
        'percentage': float(attempt.percentage) if attempt.percentage else 0,
        'all_graded': all_graded,
        'passed': attempt.passed,
    }


def has_questions(exam):
    """
    Check if an exam has any questions.
    
    Args:
        exam: Exam model instance
    
    Returns:
        bool
    """
    try:
        return exam.questions.exists()
    except Exception:
        return False
