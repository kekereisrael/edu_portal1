"""
Models for the analytics app.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel, SchoolScopedModel


class StudentAnalytics(BaseModel):
    """Aggregated student performance metrics per term."""

    class Trend(models.TextChoices):
        IMPROVING = 'improving', 'Improving'
        STABLE = 'stable', 'Stable'
        DECLINING = 'declining', 'Declining'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='analytics',
        db_index=True,
    )
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='student_analytics', db_index=True
    )
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='student_analytics', db_index=True
    )
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_exams_taken = models.IntegerField(default=0)
    total_materials_completed = models.IntegerField(default=0)
    total_time_spent_minutes = models.IntegerField(default=0)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rank_in_class = models.IntegerField(null=True, blank=True)
    improvement_trend = models.CharField(
        max_length=20, choices=Trend.choices, null=True, blank=True
    )
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'student analytics'
        verbose_name_plural = 'student analytics'
        unique_together = ['student', 'school', 'term']

    def __str__(self):
        return f'{self.student.full_name} - {self.term.name}: avg {self.average_score}'


class SubjectAnalytics(BaseModel):
    """Subject-level performance metrics per term."""

    subject = models.ForeignKey(
        'subjects.Subject', on_delete=models.CASCADE, related_name='analytics', db_index=True
    )
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='subject_analytics', db_index=True
    )
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='subject_analytics', db_index=True
    )
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_students = models.IntegerField(default=0)
    highest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lowest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'subject analytics'
        verbose_name_plural = 'subject analytics'
        unique_together = ['subject', 'school', 'term']

    def __str__(self):
        return f'{self.subject.code} - {self.term.name}: avg {self.average_score}'


class SchoolAnalytics(BaseModel):
    """School-wide KPIs."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='analytics', db_index=True
    )
    term = models.ForeignKey(
        'schools.Term', on_delete=models.SET_NULL, null=True, blank=True, related_name='school_analytics'
    )
    total_students = models.IntegerField(default=0)
    total_teachers = models.IntegerField(default=0)
    total_subjects = models.IntegerField(default=0)
    total_exams_created = models.IntegerField(default=0)
    average_pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    storage_used_bytes = models.BigIntegerField(default=0)
    ai_credits_used = models.IntegerField(default=0)
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'school analytics'
        verbose_name_plural = 'school analytics'
        ordering = ['-last_calculated_at']

    def __str__(self):
        return f'{self.school.name} analytics'


class LearningPath(SchoolScopedModel):
    """Recommended learning sequences for students."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        PAUSED = 'paused', 'Paused'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learning_paths',
        db_index=True,
    )
    subject = models.ForeignKey(
        'subjects.Subject', on_delete=models.CASCADE, related_name='learning_paths'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_ai_generated = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        verbose_name = 'learning path'
        verbose_name_plural = 'learning paths'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} for {self.student.full_name}'

    @property
    def progress_percent(self):
        total = self.steps.count()
        if total == 0:
            return 0
        completed = self.steps.filter(is_completed=True).count()
        return int((completed / total) * 100)


class LearningPathStep(BaseModel):
    """Steps within a learning path."""

    class StepType(models.TextChoices):
        MATERIAL = 'material', 'Study Material'
        EXAM = 'exam', 'Take Exam'
        TOPIC_REVIEW = 'topic_review', 'Review Topic'
        PRACTICE = 'practice', 'Practice Exercise'

    learning_path = models.ForeignKey(
        LearningPath, on_delete=models.CASCADE, related_name='steps', db_index=True
    )
    order = models.IntegerField()
    step_type = models.CharField(max_length=20, choices=StepType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    related_material = models.ForeignKey(
        'materials.Material', on_delete=models.SET_NULL, null=True, blank=True
    )
    related_exam = models.ForeignKey(
        'exams.Exam', on_delete=models.SET_NULL, null=True, blank=True
    )
    related_topic = models.ForeignKey(
        'subjects.Topic', on_delete=models.SET_NULL, null=True, blank=True
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'learning path step'
        verbose_name_plural = 'learning path steps'
        ordering = ['order']

    def __str__(self):
        return f'Step {self.order}: {self.title}'


class AIUsageRecord(BaseModel):
    """Track AI/LLM usage per school and user."""

    class UsageType(models.TextChoices):
        QUESTION_GENERATION = 'question_generation', 'Question Generation'
        ESSAY_GRADING = 'essay_grading', 'Essay Grading'
        TUTORING = 'tutoring', 'AI Tutoring'
        CONTENT_CREATION = 'content_creation', 'Content Creation'
        SUMMARIZATION = 'summarization', 'Summarization'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='ai_usage_records', db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_usage_records',
        db_index=True,
    )
    usage_type = models.CharField(max_length=30, choices=UsageType.choices, db_index=True)
    credits_consumed = models.IntegerField(default=1)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    model_used = models.CharField(max_length=50)
    estimated_cost_usd = models.DecimalField(
        max_digits=8, decimal_places=4, default=0
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'AI usage record'
        verbose_name_plural = 'AI usage records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'created_at'], name='idx_ai_usage_school_date'),
            models.Index(fields=['school', 'usage_type'], name='idx_ai_usage_school_type'),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.get_usage_type_display()} ({self.credits_consumed} credits)'
