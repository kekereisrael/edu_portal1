"""
Celery tasks for the analytics app.
Handles data aggregation, report generation, and AI-powered insights.
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Q
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def aggregate_daily_analytics():
    """
    Aggregate daily analytics for all active schools.
    Runs daily at 1 AM.
    """
    from schools.models import School

    schools = School.objects.filter(is_active=True)

    for school in schools:
        try:
            aggregate_school_analytics.delay(str(school.id))
        except Exception as exc:
            logger.error(f"Failed to queue analytics for school {school.id}: {exc}")

    logger.info(f"Daily analytics aggregation queued for {schools.count()} schools")


@shared_task
def aggregate_school_analytics(school_id):
    """Aggregate analytics for a specific school."""
    from analytics.models import SchoolAnalytics
    from accounts.models import User
    from exams.models import ExamAttempt, Result
    from materials.models import MaterialProgress

    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Active users yesterday
        active_students = User.objects.filter(
            school_id=school_id,
            role='student',
            last_login__date=yesterday,
        ).count()

        active_teachers = User.objects.filter(
            school_id=school_id,
            role='teacher',
            last_login__date=yesterday,
        ).count()

        # Exam statistics for yesterday
        exam_stats = ExamAttempt.objects.filter(
            school_id=school_id,
            started_at__date=yesterday,
        ).aggregate(
            total_attempts=Count('id'),
            completed=Count('id', filter=Q(status='graded')),
        )

        # Average scores
        avg_score = Result.objects.filter(
            attempt__school_id=school_id,
            graded_at__date=yesterday,
        ).aggregate(avg=Avg('percentage'))['avg']

        # Material engagement
        material_views = MaterialProgress.objects.filter(
            material__school_id=school_id,
            last_accessed__date=yesterday,
        ).count()

        # Create or update analytics record
        SchoolAnalytics.objects.update_or_create(
            school_id=school_id,
            date=yesterday,
            defaults={
                'active_students': active_students,
                'active_teachers': active_teachers,
                'total_exam_attempts': exam_stats['total_attempts'] or 0,
                'completed_exams': exam_stats['completed'] or 0,
                'average_score': avg_score or 0,
                'material_views': material_views,
                'total_active_users': active_students + active_teachers,
            }
        )

        logger.info(f"School analytics aggregated for school {school_id}, date {yesterday}")
    except Exception as exc:
        logger.error(f"Failed to aggregate school analytics: {exc}")


@shared_task
def aggregate_student_analytics(student_id):
    """Aggregate analytics for a specific student."""
    from analytics.models import StudentAnalytics
    from exams.models import Result
    from materials.models import MaterialProgress
    from accounts.models import User

    try:
        student = User.objects.get(id=student_id)
        today = timezone.now().date()

        # Overall exam performance
        results = Result.objects.filter(attempt__student=student)
        total_exams = results.count()
        passed_exams = results.filter(is_passed=True).count()
        avg_score = results.aggregate(avg=Avg('percentage'))['avg'] or 0

        # Study time (from material progress)
        total_study_minutes = MaterialProgress.objects.filter(
            user=student,
        ).aggregate(total=Sum('time_spent_minutes'))['total'] or 0

        # Streak calculation
        streak = _calculate_study_streak(student)

        StudentAnalytics.objects.update_or_create(
            student=student,
            defaults={
                'total_exams_taken': total_exams,
                'exams_passed': passed_exams,
                'average_score': round(avg_score, 2),
                'total_study_minutes': total_study_minutes,
                'current_streak': streak,
                'last_activity_date': today,
                'pass_rate': round(passed_exams / total_exams * 100, 2) if total_exams > 0 else 0,
            }
        )

        logger.info(f"Student analytics updated for {student_id}")
    except Exception as exc:
        logger.error(f"Failed to aggregate student analytics: {exc}")


@shared_task
def aggregate_subject_analytics(subject_id):
    """Aggregate analytics for a specific subject."""
    from analytics.models import SubjectAnalytics
    from exams.models import Exam, Result
    from subjects.models import Subject, Enrollment
    from materials.models import Material

    try:
        subject = Subject.objects.get(id=subject_id)

        # Enrollment stats
        total_enrolled = Enrollment.objects.filter(
            subject=subject,
            status='active',
        ).count()

        # Exam performance
        exams = Exam.objects.filter(subject=subject)
        results = Result.objects.filter(attempt__exam__in=exams)

        avg_score = results.aggregate(avg=Avg('percentage'))['avg'] or 0
        pass_rate = 0
        if results.exists():
            passed = results.filter(is_passed=True).count()
            pass_rate = round(passed / results.count() * 100, 2)

        # Material stats
        total_materials = Material.objects.filter(subject=subject).count()

        SubjectAnalytics.objects.update_or_create(
            subject=subject,
            defaults={
                'total_enrolled': total_enrolled,
                'average_score': round(avg_score, 2),
                'pass_rate': pass_rate,
                'total_exams': exams.count(),
                'total_materials': total_materials,
                'last_updated': timezone.now(),
            }
        )

        logger.info(f"Subject analytics updated for {subject_id}")
    except Exception as exc:
        logger.error(f"Failed to aggregate subject analytics: {exc}")


@shared_task
def generate_weekly_reports():
    """
    Generate weekly summary reports for all schools.
    Runs every Monday at 6 AM.
    """
    from schools.models import School
    from analytics.models import SchoolAnalytics
    from notifications.models import Notification

    today = timezone.now().date()
    week_start = today - timedelta(days=7)

    schools = School.objects.filter(is_active=True)

    for school in schools:
        try:
            # Get weekly stats
            weekly_stats = SchoolAnalytics.objects.filter(
                school=school,
                date__gte=week_start,
                date__lt=today,
            ).aggregate(
                total_active=Sum('total_active_users'),
                total_exams=Sum('total_exam_attempts'),
                avg_score=Avg('average_score'),
            )

            # Create notification for school admins
            from accounts.models import User
            admins = User.objects.filter(
                school=school,
                role='school_admin',
                is_active=True,
            )

            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    school=school,
                    title='Weekly School Report',
                    message=(
                        f"This week: {weekly_stats['total_active'] or 0} active users, "
                        f"{weekly_stats['total_exams'] or 0} exam attempts, "
                        f"Average score: {weekly_stats['avg_score'] or 0:.1f}%"
                    ),
                    notification_type='weekly_report',
                    channels=['in_app', 'email'],
                    priority='normal',
                )

        except Exception as exc:
            logger.error(f"Failed to generate weekly report for school {school.id}: {exc}")

    logger.info(f"Weekly reports generated for {schools.count()} schools")


@shared_task
def track_ai_usage(school_id, user_id, feature, tokens_used=0, cost=0):
    """Track AI/LLM usage for billing and analytics."""
    from analytics.models import AIUsageRecord

    try:
        AIUsageRecord.objects.create(
            school_id=school_id,
            user_id=user_id,
            feature=feature,
            tokens_used=tokens_used,
            estimated_cost=cost,
            timestamp=timezone.now(),
        )
    except Exception as exc:
        logger.error(f"Failed to track AI usage: {exc}")


def _calculate_study_streak(student):
    """Calculate the current consecutive days study streak."""
    from materials.models import MaterialProgress
    from exams.models import ExamAttempt

    today = timezone.now().date()
    streak = 0
    current_date = today

    while True:
        # Check if student was active on this date
        had_material_activity = MaterialProgress.objects.filter(
            user=student,
            last_accessed__date=current_date,
        ).exists()

        had_exam_activity = ExamAttempt.objects.filter(
            student=student,
            started_at__date=current_date,
        ).exists()

        if had_material_activity or had_exam_activity:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            break

        # Safety limit
        if streak > 365:
            break

    return streak
