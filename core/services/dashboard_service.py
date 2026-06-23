"""
Dashboard service layer.
Handles all business logic for the student/teacher/school-admin dashboard.
"""

import logging
from django.db.models import Count, Avg, Q, Sum
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


def get_school_admin_dashboard_data(school):
    """
    Get aggregated dashboard data for a school administrator.

    Args:
        school: The School instance (from request.school)

    Returns:
        dict: School-wide statistics and recent activity
    """
    try:
        from schools.models import (
            SchoolMembership, ClassRoom, ClassLevel,
            AcademicSession, SchoolSettings,
        )
        from subjects.models import Subject
        from exams.models import Exam, ExamAttempt

        role = SchoolMembership.SchoolRole

        # ── Member counts ────────────────────────────────────────────────────
        membership_qs = SchoolMembership.objects.filter(school=school, is_active=True)
        role_counts = membership_qs.values('role').annotate(total=Count('id'))
        role_map = {r['role']: r['total'] for r in role_counts}

        total_students = role_map.get(role.STUDENT, 0)
        total_teachers = role_map.get(role.TEACHER, 0)
        total_admins   = role_map.get(role.SCHOOL_ADMIN, 0)
        total_parents  = role_map.get(role.PARENT, 0)
        total_members  = membership_qs.count()

        # ── Academic structure ───────────────────────────────────────────────
        total_classrooms   = ClassRoom.objects.filter(school=school).count()
        total_class_levels = ClassLevel.objects.filter(school=school, is_active=True).count()
        total_subjects     = Subject.objects.filter(school=school).count()

        # ── Current academic session ─────────────────────────────────────────
        current_session = AcademicSession.objects.filter(
            school=school, is_current=True
        ).first()
        current_session_data = None
        if current_session:
            current_session_data = {
                'id': str(current_session.id),
                'name': current_session.name,
                'start_date': current_session.start_date,
                'end_date': current_session.end_date,
            }

        # ── Exam statistics ──────────────────────────────────────────────────
        school_exams = Exam.objects.filter(school=school)
        total_exams     = school_exams.count()
        published_exams = school_exams.filter(status='published').count()
        draft_exams     = school_exams.filter(status='draft').count()

        # Attempts in the last 30 days
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_attempts_count = ExamAttempt.objects.filter(
            exam__school=school,
            created_at__gte=thirty_days_ago,
        ).count()

        # Average score across all graded attempts in this school
        avg_score = ExamAttempt.objects.filter(
            exam__school=school,
            status=ExamAttempt.Status.GRADED,
            percentage__isnull=False,
        ).aggregate(avg=Avg('percentage'))['avg']

        # ── Recent exam attempts (last 10) ───────────────────────────────────
        recent_attempts = (
            ExamAttempt.objects
            .filter(exam__school=school)
            .select_related('student', 'exam')
            .order_by('-created_at')[:10]
        )
        recent_activity = [
            {
                'student_name': a.student.get_full_name() or a.student.email,
                'exam_title': a.exam.title,
                'status': a.status,
                'score': float(a.score) if a.score is not None else None,
                'percentage': float(a.percentage) if a.percentage is not None else None,
                'created_at': a.created_at,
            }
            for a in recent_attempts
        ]

        # ── School settings / profile ────────────────────────────────────────
        try:
            settings_obj = school.settings
            principal_name = settings_obj.principal_name
            grading_system = settings_obj.grading_system
            timezone_name  = settings_obj.timezone
        except SchoolSettings.DoesNotExist:
            principal_name = None
            grading_system = None
            timezone_name  = 'Africa/Lagos'

        return {
            'school': {
                'id': str(school.id),
                'name': school.name,
                'email': school.email,
                'logo': school.logo.url if school.logo else None,
                'is_active': school.is_active,
                'principal_name': principal_name,
                'grading_system': grading_system,
                'timezone': timezone_name,
            },
            'members': {
                'total': total_members,
                'students': total_students,
                'teachers': total_teachers,
                'admins': total_admins,
                'parents': total_parents,
            },
            'academic': {
                'total_classrooms': total_classrooms,
                'total_class_levels': total_class_levels,
                'total_subjects': total_subjects,
                'current_session': current_session_data,
            },
            'exams': {
                'total': total_exams,
                'published': published_exams,
                'draft': draft_exams,
                'recent_attempts_30d': recent_attempts_count,
                'average_score': round(float(avg_score), 1) if avg_score else 0,
            },
            'recent_activity': recent_activity,
        }

    except Exception as exc:
        logger.error(f"Error fetching school admin dashboard data for school {school}: {exc}")
        return {
            'school': {},
            'members': {
                'total': 0, 'students': 0, 'teachers': 0,
                'admins': 0, 'parents': 0,
            },
            'academic': {
                'total_classrooms': 0, 'total_class_levels': 0,
                'total_subjects': 0, 'current_session': None,
            },
            'exams': {
                'total': 0, 'published': 0, 'draft': 0,
                'recent_attempts_30d': 0, 'average_score': 0,
            },
            'recent_activity': [],
            'error': 'Unable to load dashboard data. Please try again later.',
        }
