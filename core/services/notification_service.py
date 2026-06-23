"""
Notification service layer.
Database-based notification system - no Redis dependency.
All notifications are stored in the database and delivered safely.
"""

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def create_notification(user, title, message, notification_type='info', school=None,
                       channel='in_app', related_object_type=None, related_object_id=None):
    """
    Create a notification for a user (DB-based, no Redis).
    
    Args:
        user: User instance to notify
        title: Notification title
        message: Notification body
        notification_type: One of 'info', 'warning', 'success', 'error'
        school: Optional school instance
        channel: Delivery channel ('in_app', 'email', 'push', 'sms')
        related_object_type: Optional related object type string
        related_object_id: Optional related object UUID
    
    Returns:
        Notification instance or None on failure
    """
    try:
        from notifications.models import Notification

        notification = Notification.objects.create(
            recipient=user,
            school=school,
            title=title,
            message=message,
            notification_type=notification_type,
            channel=channel,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
        )

        logger.info(f"Notification created for user {user.email}: {title}")
        return notification

    except Exception as exc:
        logger.error(f"Failed to create notification for user {user}: {exc}")
        return None


def get_user_notifications(user, unread_only=False, limit=20):
    """
    Get notifications for a user.
    
    Args:
        user: User instance
        unread_only: If True, only return unread notifications
        limit: Maximum number of notifications to return
    
    Returns:
        QuerySet of Notification objects
    """
    try:
        from notifications.models import Notification

        qs = Notification.objects.filter(recipient=user)

        if unread_only:
            qs = qs.filter(is_read=False)

        return qs.order_by('-created_at')[:limit]

    except Exception as exc:
        logger.error(f"Failed to fetch notifications for user {user}: {exc}")
        from notifications.models import Notification
        return Notification.objects.none()


def get_unread_count(user):
    """
    Get the count of unread notifications for a user.
    
    Args:
        user: User instance
    
    Returns:
        int: Number of unread notifications
    """
    try:
        from notifications.models import Notification
        return Notification.objects.filter(recipient=user, is_read=False).count()
    except Exception as exc:
        logger.error(f"Failed to get unread count for user {user}: {exc}")
        return 0


def mark_notification_read(notification_id, user):
    """
    Mark a specific notification as read.
    
    Args:
        notification_id: UUID of the notification
        user: User instance (for ownership verification)
    
    Returns:
        bool: True if successful
    """
    try:
        from notifications.models import Notification

        notification = Notification.objects.get(id=notification_id, recipient=user)
        notification.mark_read()
        return True

    except Exception as exc:
        logger.error(f"Failed to mark notification {notification_id} as read: {exc}")
        return False


def mark_all_read(user):
    """
    Mark all notifications as read for a user.
    
    Args:
        user: User instance
    
    Returns:
        int: Number of notifications marked as read
    """
    try:
        from notifications.models import Notification

        count = Notification.objects.filter(
            recipient=user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

        return count

    except Exception as exc:
        logger.error(f"Failed to mark all notifications as read for user {user}: {exc}")
        return 0


def notify_exam_result(student, exam, score, percentage):
    """
    Send a notification about an exam result.
    
    Args:
        student: Student user instance
        exam: Exam instance
        score: Numeric score
        percentage: Percentage score
    """
    title = f'Result Available: {exam.title}'
    message = f'Your result for "{exam.title}" is now available. Score: {percentage}%'

    return create_notification(
        user=student,
        title=title,
        message=message,
        notification_type='success',
        school=exam.school,
        related_object_type='exam',
        related_object_id=exam.id,
    )


def notify_exam_reminder(student, exam, minutes_before=30):
    """
    Send an exam reminder notification.
    
    Args:
        student: Student user instance
        exam: Exam instance
        minutes_before: Minutes before exam starts
    """
    title = f'Exam Reminder: {exam.title}'
    message = f'Your exam "{exam.title}" starts in {minutes_before} minutes.'

    return create_notification(
        user=student,
        title=title,
        message=message,
        notification_type='warning',
        school=exam.school,
        related_object_type='exam',
        related_object_id=exam.id,
    )
