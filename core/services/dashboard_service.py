"""
Dashboard service layer.
Handles all business logic for the student/teacher dashboard.
"""

import logging
from django.db.models import Count, Avg, Q
from django.utils import timezone

from core.utils.cache import safe_cache_get_or_set

logger = logging.getLogger(__name__)


def get_student_dashboard_data(user):
    """
    Get all dashboard data for a student user.
    
    Args:
        user: The authenticated User instance
    
    Returns:
        dict: Dashboard context data including exams, scores, notifications
    """
    try:
        from exams.models import ExamAttempt, Exam

        # Get total exams attempted
        total_attempts = ExamAttempt.objects.filter(student=user).count()

        # Get recent scores (last 5 graded attempts)
        recent_attempts = ExamAttempt.objects.filter(
            student=user,
            status=ExamAttempt.Status.GRADED,
        ).select_related('exam').order_by('-submitted_at')[:5]

        recent_scores = [
            {
                'exam_title': attempt.exam.title,
                'score': float(attempt.score) if attempt.score else 0,
                'percentage': float(attempt.percentage) if attempt.percentage else 0,
                'passed': attempt.passed,
                'submitted_at': attempt.submitted_at,
            }
            for attempt in recent_attempts
        ]

        # Get upcoming exams
        upcoming_exams = Exam.objects.filter(
            status='published',
            start_date__gt=timezone.now(),
        ).order_by('start_date')[:5]

        upcoming_exams_data = [
            {
                'title': exam.title,
                'subject': str(exam.subject) if exam.subject else 'N/A',
                'start_time': exam.start_date,
                'duration_minutes': exam.duration_minutes,
            }
            for exam in upcoming_exams
        ]

        # Get in-progress attempts
        in_progress = ExamAttempt.objects.filter(
            student=user,
            status=ExamAttempt.Status.IN_PROGRESS,
        ).select_related('exam').count()

        # Get average score
        avg_score = ExamAttempt.objects.filter(
            student=user,
            status=ExamAttempt.Status.GRADED,
            percentage__isnull=False,
        ).aggregate(avg=Avg('percentage'))['avg']

        return {
            'total_exams': total_attempts,
            'recent_scores': recent_scores,
            'upcoming_exams': upcoming_exams_data,
            'in_progress_count': in_progress,
            'average_score': round(float(avg_score), 1) if avg_score else 0,
            'active_page': 'dashboard',
        }

    except Exception as exc:
        logger.error(f"Error fetching dashboard data for user {user}: {exc}")
        return {
            'total_exams': 0,
            'recent_scores': [],
            'upcoming_exams': [],
            'in_progress_count': 0,
            'average_score': 0,
            'active_page': 'dashboard',
            'error': 'Unable to load dashboard data. Please try again later.',
        }


def get_teacher_dashboard_data(user):
    """
    Get all dashboard data for a teacher user.
    
    Args:
        user: The authenticated User instance (teacher)
    
    Returns:
        dict: Dashboard context data for teachers
    """
    try:
        from exams.models import Exam, ExamAttempt

        # Get exams created by this teacher
        my_exams = Exam.objects.filter(created_by=user)
        total_exams_created = my_exams.count()
        published_exams = my_exams.filter(status='published').count()

        # Get recent submissions needing grading
        pending_grading = ExamAttempt.objects.filter(
            exam__created_by=user,
            status=ExamAttempt.Status.SUBMITTED,
        ).select_related('exam', 'student').order_by('-submitted_at')[:10]

        pending_grading_data = [
            {
                'student_name': attempt.student.full_name,
                'exam_title': attempt.exam.title,
                'submitted_at': attempt.submitted_at,
                'attempt_id': str(attempt.id),
            }
            for attempt in pending_grading
        ]

        return {
            'total_exams_created': total_exams_created,
            'published_exams': published_exams,
            'pending_grading': pending_grading_data,
            'pending_grading_count': len(pending_grading_data),
            'active_page': 'dashboard',
        }

    except Exception as exc:
        logger.error(f"Error fetching teacher dashboard data for user {user}: {exc}")
        return {
            'total_exams_created': 0,
            'published_exams': 0,
            'pending_grading': [],
            'pending_grading_count': 0,
            'active_page': 'dashboard',
            'error': 'Unable to load dashboard data. Please try again later.',
        }
