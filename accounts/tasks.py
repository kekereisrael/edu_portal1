"""
Celery tasks for the accounts app.
Handles email sending, token cleanup, and user-related async operations.
"""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id, token):
    """Send email verification link to user."""
    try:
        from accounts.models import User
        user = User.objects.get(id=user_id)

        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"

        subject = 'Verify Your Email Address'
        message = (
            f"Hi {user.first_name},\n\n"
            f"Please verify your email address by clicking the link below:\n"
            f"{verification_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you didn't create an account, please ignore this email."
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(f"Verification email sent to {user.email}")
    except Exception as exc:
        logger.error(f"Failed to send verification email: {exc}")
        self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id, token):
    """Send password reset link to user."""
    try:
        from accounts.models import User
        user = User.objects.get(id=user_id)

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        subject = 'Reset Your Password'
        message = (
            f"Hi {user.first_name},\n\n"
            f"You requested a password reset. Click the link below:\n"
            f"{reset_url}\n\n"
            f"This link expires in 1 hour.\n\n"
            f"If you didn't request this, please ignore this email."
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(f"Password reset email sent to {user.email}")
    except Exception as exc:
        logger.error(f"Failed to send password reset email: {exc}")
        self.retry(exc=exc)


@shared_task
def cleanup_expired_tokens():
    """Remove expired verification and password reset tokens."""
    from accounts.models import EmailVerificationToken, PasswordResetToken

    now = timezone.now()

    expired_verification = EmailVerificationToken.objects.filter(
        expires_at__lt=now
    ).delete()

    expired_reset = PasswordResetToken.objects.filter(
        expires_at__lt=now
    ).delete()

    logger.info(
        f"Cleaned up {expired_verification[0]} expired verification tokens "
        f"and {expired_reset[0]} expired reset tokens"
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, user_id):
    """Send welcome email to newly registered user."""
    try:
        from accounts.models import User
        user = User.objects.get(id=user_id)

        subject = 'Welcome to Examind!'
        message = (
            f"Hi {user.first_name},\n\n"
            f"Welcome to Examind! Your account has been created successfully.\n\n"
            f"Get started by:\n"
            f"1. Completing your profile\n"
            f"2. Joining your school\n"
            f"3. Exploring available subjects\n\n"
            f"If you need help, visit our support center.\n\n"
            f"Best regards,\nThe Examind Team"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(f"Welcome email sent to {user.email}")
    except Exception as exc:
        logger.error(f"Failed to send welcome email: {exc}")
        self.retry(exc=exc)


@shared_task
def deactivate_inactive_users():
    """Deactivate users who haven't logged in for 365 days."""
    from accounts.models import User

    threshold = timezone.now() - timedelta(days=365)
    inactive_users = User.objects.filter(
        last_login__lt=threshold,
        is_active=True,
        is_staff=False,
    )

    count = inactive_users.update(is_active=False)
    logger.info(f"Deactivated {count} inactive users")
