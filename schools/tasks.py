"""
Celery tasks for the schools app.
Handles storage calculations, school analytics, and maintenance.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def calculate_storage_usage():
    """Calculate and update storage usage for all schools."""
    from schools.models import School, StorageUsage

    schools = School.objects.filter(is_active=True)

    for school in schools:
        try:
            # Calculate total storage from materials
            from materials.models import Material
            from django.db.models import Sum

            total_size = Material.objects.filter(
                school=school
            ).aggregate(
                total=Sum('file_size')
            )['total'] or 0

            # Update or create storage usage record
            StorageUsage.objects.update_or_create(
                school=school,
                defaults={
                    'used_bytes': total_size,
                    'last_calculated': timezone.now(),
                }
            )
        except Exception as exc:
            logger.error(f"Failed to calculate storage for school {school.id}: {exc}")

    logger.info(f"Storage usage calculated for {schools.count()} schools")


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_storage_warning(self, school_id, usage_percentage):
    """Send storage quota warning to school admins."""
    try:
        from schools.models import School
        from accounts.models import User
        from django.core.mail import send_mail
        from django.conf import settings

        school = School.objects.get(id=school_id)
        admins = User.objects.filter(
            school=school,
            role='school_admin',
            is_active=True,
        )

        for admin in admins:
            send_mail(
                subject=f'Storage Warning - {school.name}',
                message=(
                    f"Hi {admin.first_name},\n\n"
                    f"Your school's storage usage is at {usage_percentage}%.\n"
                    f"Please consider upgrading your plan or removing unused files.\n\n"
                    f"Best regards,\nThe Examind Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin.email],
                fail_silently=False,
            )

        logger.info(f"Storage warning sent to admins of school {school.name}")
    except Exception as exc:
        logger.error(f"Failed to send storage warning: {exc}")
        self.retry(exc=exc)


@shared_task
def generate_school_report(school_id, report_type='monthly'):
    """Generate a comprehensive school report."""
    from schools.models import School

    try:
        school = School.objects.get(id=school_id)

        # Gather statistics
        from accounts.models import User
        from exams.models import Exam, ExamAttempt
        from subjects.models import Subject
        from materials.models import Material

        stats = {
            'school': str(school.id),
            'report_type': report_type,
            'generated_at': timezone.now().isoformat(),
            'total_students': User.objects.filter(school=school, role='student').count(),
            'total_teachers': User.objects.filter(school=school, role='teacher').count(),
            'total_subjects': Subject.objects.filter(school=school).count(),
            'total_exams': Exam.objects.filter(school=school).count(),
            'total_materials': Material.objects.filter(school=school).count(),
            'total_attempts': ExamAttempt.objects.filter(school=school).count(),
        }

        logger.info(f"School report generated for {school.name}: {stats}")
        return stats

    except Exception as exc:
        logger.error(f"Failed to generate school report: {exc}")
        raise
