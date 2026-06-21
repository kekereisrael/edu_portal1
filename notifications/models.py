"""
Models for the notifications app.
"""

import uuid
from django.conf import settings
from django.db import models

from core.models import BaseModel


class NotificationTemplate(BaseModel):
    """Reusable notification templates with variables."""

    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'
        PUSH = 'push', 'Push Notification'
        IN_APP = 'in_app', 'In-App'
        SMS = 'sms', 'SMS'

    name = models.CharField(max_length=100, unique=True)
    subject_template = models.CharField(max_length=200)
    body_template = models.TextField()
    channel = models.CharField(max_length=10, choices=Channel.choices)
    variables = models.JSONField(
        default=list, help_text='Expected template variables, e.g. ["student_name", "exam_title"]'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'notification template'
        verbose_name_plural = 'notification templates'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_channel_display()})'

    def render(self, context):
        """Render template with context variables."""
        subject = self.subject_template.format(**context)
        body = self.body_template.format(**context)
        return subject, body


class Notification(BaseModel):
    """Individual notification sent to a user."""

    class NotificationType(models.TextChoices):
        INFO = 'info', 'Information'
        WARNING = 'warning', 'Warning'
        SUCCESS = 'success', 'Success'
        ERROR = 'error', 'Error'

    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'
        PUSH = 'push', 'Push Notification'
        IN_APP = 'in_app', 'In-App'
        SMS = 'sms', 'SMS'

    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        db_index=True,
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=10, choices=NotificationType.choices, default=NotificationType.INFO
    )
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.IN_APP
    )
    related_object_type = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='e.g. "exam", "result", "payment"'
    )
    related_object_id = models.UUIDField(null=True, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'notification'
        verbose_name_plural = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['recipient', 'is_read', 'created_at'],
                name='idx_notif_recipient_read',
            ),
            models.Index(
                fields=['school', 'created_at'],
                name='idx_notif_school_created',
            ),
        ]

    def __str__(self):
        return f'{self.title} -> {self.recipient.email}'

    def mark_read(self):
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at', 'updated_at'])


class BulkNotification(BaseModel):
    """Track bulk notification sends (school-wide announcements)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENDING = 'sending', 'Sending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='bulk_notifications',
        db_index=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    target_role = models.CharField(
        max_length=20, blank=True, null=True,
        help_text='Filter recipients by role. Null = all members.'
    )
    target_classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bulk_notifications',
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_bulk_notifications',
    )
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'bulk notification'
        verbose_name_plural = 'bulk notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.status})'


class DeviceToken(BaseModel):
    """FCM/APNs device tokens for push notifications."""

    class Platform(models.TextChoices):
        FCM = 'fcm', 'Firebase Cloud Messaging'
        APNS = 'apns', 'Apple Push Notification Service'
        WEB = 'web', 'Web Push'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens',
        db_index=True,
    )
    token = models.TextField()
    platform = models.CharField(max_length=10, choices=Platform.choices)
    device_name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'device token'
        verbose_name_plural = 'device tokens'
        unique_together = ['user', 'token']

    def __str__(self):
        return f'{self.user.email} - {self.get_platform_display()}'
