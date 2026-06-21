"""
Models for the communications app - Announcements and messaging.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel, SchoolScopedModel


class Announcement(SchoolScopedModel):
    """School-wide or class-wide announcements."""

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='announcements',
    )
    target_role = models.CharField(
        max_length=20, blank=True, null=True,
        help_text='Target audience role. Null = all members.',
    )
    target_classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements',
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )
    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'announcement'
        verbose_name_plural = 'announcements'
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['school', 'published_at'], name='idx_announce_school_pub'),
        ]

    def __str__(self):
        return f'{self.title} ({self.school.name})'

    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        if self.published_at and now < self.published_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True


class MessageThread(SchoolScopedModel):
    """Message thread/conversation."""

    class ThreadType(models.TextChoices):
        DIRECT = 'direct', 'Direct Message'
        GROUP = 'group', 'Group Chat'

    subject = models.CharField(max_length=200)
    thread_type = models.CharField(
        max_length=10, choices=ThreadType.choices, default=ThreadType.DIRECT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_threads',
    )
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'message thread'
        verbose_name_plural = 'message threads'
        ordering = ['-last_message_at']

    def __str__(self):
        return f'{self.subject} ({self.get_thread_type_display()})'


class ThreadParticipant(BaseModel):
    """Participant in a message thread."""

    class Role(models.TextChoices):
        MEMBER = 'member', 'Member'
        ADMIN = 'admin', 'Admin'

    thread = models.ForeignKey(
        MessageThread, on_delete=models.CASCADE, related_name='participants', db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='thread_participations',
        db_index=True,
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'thread participant'
        verbose_name_plural = 'thread participants'
        unique_together = ['thread', 'user']

    def __str__(self):
        return f'{self.user.full_name} in {self.thread.subject}'

    @property
    def unread_count(self):
        qs = self.thread.messages.all()
        if self.last_read_at:
            qs = qs.filter(created_at__gt=self.last_read_at)
        return qs.exclude(sender=self.user).count()


class Message(BaseModel):
    """Individual message in a thread."""

    thread = models.ForeignKey(
        MessageThread, on_delete=models.CASCADE, related_name='messages', db_index=True
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    content = models.TextField()
    attachment = models.FileField(upload_to='messages/attachments/', blank=True, null=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'message'
        verbose_name_plural = 'messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at'], name='idx_message_thread_created'),
        ]

    def __str__(self):
        return f'{self.sender.full_name}: {self.content[:50]}'
