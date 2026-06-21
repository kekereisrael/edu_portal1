"""
Models for the materials app - Learning materials, progress tracking, and engagement.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel, SchoolScopedModel


class Material(SchoolScopedModel):
    """Learning material (document, video, audio, etc.)."""

    class MaterialType(models.TextChoices):
        DOCUMENT = 'document', 'Document'
        VIDEO = 'video', 'Video'
        AUDIO = 'audio', 'Audio'
        LINK = 'link', 'External Link'
        SCORM = 'scorm', 'SCORM Package'
        INTERACTIVE = 'interactive', 'Interactive'
        IMAGE = 'image', 'Image'

    subject = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='materials',
        db_index=True,
    )
    topic = models.ForeignKey(
        'subjects.Topic',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materials',
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materials',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    material_type = models.CharField(
        max_length=20, choices=MaterialType.choices, db_index=True
    )
    file = models.FileField(upload_to='materials/', blank=True, null=True)
    file_url = models.URLField(blank=True, null=True, help_text='External link URL')
    file_size_bytes = models.BigIntegerField(default=0)
    duration_seconds = models.IntegerField(
        null=True, blank=True, help_text='Duration for video/audio in seconds'
    )
    is_published = models.BooleanField(default=False, db_index=True)
    order = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_materials',
    )

    class Meta:
        verbose_name = 'material'
        verbose_name_plural = 'materials'
        ordering = ['order', '-created_at']
        indexes = [
            models.Index(fields=['school', 'subject', 'is_published'], name='idx_material_school_subj_pub'),
            models.Index(fields=['school', 'material_type'], name='idx_material_school_type'),
        ]

    def __str__(self):
        return f'{self.title} ({self.get_material_type_display()})'

    @property
    def file_size_display(self):
        if self.file_size_bytes < 1024:
            return f'{self.file_size_bytes} B'
        elif self.file_size_bytes < 1024 ** 2:
            return f'{self.file_size_bytes / 1024:.1f} KB'
        elif self.file_size_bytes < 1024 ** 3:
            return f'{self.file_size_bytes / (1024 ** 2):.1f} MB'
        return f'{self.file_size_bytes / (1024 ** 3):.2f} GB'


class MaterialProgress(BaseModel):
    """Track student progress on a material."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='material_progress',
        db_index=True,
    )
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name='progress_records', db_index=True
    )
    progress_percent = models.IntegerField(default=0)
    last_position = models.IntegerField(
        default=0, help_text='Last position in seconds for video/audio'
    )
    completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.IntegerField(default=0)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'material progress'
        verbose_name_plural = 'material progress records'
        unique_together = ['student', 'material']
        indexes = [
            models.Index(fields=['student', 'completed'], name='idx_progress_student_complete'),
        ]

    def __str__(self):
        return f'{self.student.full_name} - {self.material.title}: {self.progress_percent}%'

    def update_progress(self, percent, position=None, time_spent=0):
        """Update progress, marking complete if 100%."""
        from django.utils import timezone
        self.progress_percent = min(100, percent)
        if position is not None:
            self.last_position = position
        self.time_spent_seconds += time_spent
        if self.progress_percent >= 100 and not self.completed:
            self.completed = True
            self.completed_at = timezone.now()
        self.save()


class MaterialComment(BaseModel):
    """Student/teacher comments on materials."""

    material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name='comments', db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='material_comments',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies'
    )
    content = models.TextField()
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'material comment'
        verbose_name_plural = 'material comments'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.user.full_name} on {self.material.title}: {self.content[:50]}'


class MaterialBookmark(BaseModel):
    """Student bookmarks for quick access."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookmarks',
    )
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name='bookmarks'
    )
    note = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'material bookmark'
        verbose_name_plural = 'material bookmarks'
        unique_together = ['student', 'material']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.full_name} bookmarked {self.material.title}'


class MaterialRating(BaseModel):
    """Student ratings for materials."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='material_ratings',
    )
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name='ratings'
    )
    rating = models.IntegerField(
        help_text='Rating from 1 to 5'
    )
    review = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'material rating'
        verbose_name_plural = 'material ratings'
        unique_together = ['student', 'material']

    def __str__(self):
        return f'{self.student.full_name} rated {self.material.title}: {self.rating}/5'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.rating < 1 or self.rating > 5:
            raise ValidationError('Rating must be between 1 and 5.')
