"""
Celery tasks for the subscriptions app.
Handles subscription lifecycle, trial management, and usage tracking.
"""

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_expiring_subscriptions():
    """
    Check for subscriptions expiring within 7 days and send reminders.
    Runs daily.
    """
    from subscriptions.models import Subscription

    expiry_threshold = timezone.now() + timedelta(days=7)

    expiring = Subscription.objects.filter(
        status='active',
        end_date__lte=expiry_threshold,
        end_date__gt=timezone.now(),
    ).select_related('school', 'plan')

    for subscription in expiring:
        try:
            days_remaining = (subscription.end_date - timezone.now()).days
            send_subscription_expiry_reminder.delay(
                str(subscription.id),
                days_remaining
            )
        except Exception as exc:
            logger.error(f"Failed to process expiring subscription {subscription.id}: {exc}")

    logger.info(f"Found {expiring.count()} expiring subscriptions")


@shared_task
def expire_trial_subscriptions():
    """
    Expire trial subscriptions that have passed their end date.
    Runs daily at midnight.
    """
    from subscriptions.models import Subscription

    expired_trials = Subscription.objects.filter(
        status='trial',
        end_date__lt=timezone.now(),
    )

    count = 0
    for subscription in expired_trials:
        subscription.status = 'expired'
        subscription.save(update_fields=['status', 'updated_at'])
        count += 1

        # Notify school admins
        send_trial_expired_notification.delay(str(subscription.id))

    logger.info(f"Expired {count} trial subscriptions")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_subscription_expiry_reminder(self, subscription_id, days_remaining):
    """Send subscription expiry reminder email."""
    try:
        from subscriptions.models import Subscription
        from accounts.models import User

        subscription = Subscription.objects.select_related('school', 'plan').get(
            id=subscription_id
        )

        admins = User.objects.filter(
            school=subscription.school,
            role='school_admin',
            is_active=True,
        )

        for admin in admins:
            send_mail(
                subject=f'Subscription Expiring in {days_remaining} Days',
                message=(
                    f"Hi {admin.first_name},\n\n"
                    f"Your {subscription.plan.name} subscription for "
                    f"{subscription.school.name} will expire in {days_remaining} days.\n\n"
                    f"Renew now to avoid service interruption.\n\n"
                    f"Best regards,\nThe Examind Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin.email],
                fail_silently=False,
            )

        logger.info(f"Expiry reminder sent for subscription {subscription_id}")
    except Exception as exc:
        logger.error(f"Failed to send expiry reminder: {exc}")
        self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_trial_expired_notification(self, subscription_id):
    """Send notification when trial has expired."""
    try:
        from subscriptions.models import Subscription
        from accounts.models import User

        subscription = Subscription.objects.select_related('school', 'plan').get(
            id=subscription_id
        )

        admins = User.objects.filter(
            school=subscription.school,
            role='school_admin',
            is_active=True,
        )

        for admin in admins:
            send_mail(
                subject='Your Trial Has Expired',
                message=(
                    f"Hi {admin.first_name},\n\n"
                    f"Your free trial for {subscription.school.name} has expired.\n\n"
                    f"Subscribe now to continue using all features:\n"
                    f"- Unlimited exams\n"
                    f"- AI-powered analytics\n"
                    f"- Advanced reporting\n\n"
                    f"Best regards,\nThe Examind Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin.email],
                fail_silently=False,
            )

        logger.info(f"Trial expired notification sent for subscription {subscription_id}")
    except Exception as exc:
        logger.error(f"Failed to send trial expired notification: {exc}")
        self.retry(exc=exc)


@shared_task
def record_daily_usage(school_id):
    """Record daily usage metrics for a school."""
    from subscriptions.models import UsageRecord
    from accounts.models import User
    from exams.models import ExamAttempt

    try:
        today = timezone.now().date()

        # Count active users today
        active_users = User.objects.filter(
            school_id=school_id,
            last_login__date=today,
        ).count()

        # Count exam attempts today
        exam_attempts = ExamAttempt.objects.filter(
            school_id=school_id,
            started_at__date=today,
        ).count()

        UsageRecord.objects.create(
            school_id=school_id,
            metric='daily_active_users',
            value=active_users,
            recorded_at=timezone.now(),
        )

        UsageRecord.objects.create(
            school_id=school_id,
            metric='daily_exam_attempts',
            value=exam_attempts,
            recorded_at=timezone.now(),
        )

        logger.info(f"Daily usage recorded for school {school_id}")
    except Exception as exc:
        logger.error(f"Failed to record daily usage: {exc}")


@shared_task
def process_referral_reward(referral_id):
    """Process referral reward when conditions are met."""
    from subscriptions.models import Referral, ReferralReward

    try:
        referral = Referral.objects.get(id=referral_id)

        if referral.status == 'converted':
            # Create reward for referrer
            ReferralReward.objects.create(
                referral=referral,
                reward_type='credit',
                amount=referral.reward_amount or 1000,  # Default reward
                status='pending',
            )

            logger.info(f"Referral reward created for referral {referral_id}")
    except Exception as exc:
        logger.error(f"Failed to process referral reward: {exc}")
