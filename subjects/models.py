"""
Models for the subjects app - Subject management, enrollment, and timetabling.
"""

import uuid
from django.conf import settings
from django.db import models

from core.models import BaseModel, SchoolScopedModel


class Subject(SchoolScopedModel):
    """Academic subject offered by a school."""

    name = models.CharField(max_length=200)
    code = models.CharField(
        max_length=20, help_text='Subject code, e.g. MATH101'
    )
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(
        'schools.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects',
    )
    credit_units = models.IntegerField(
        default=1, help_text='Credit units/weight for this subject'
    )
    is_elective = models.BooleanField(
        default=False, help_text='Whether this is an elective subject'
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'subject'
        verbose_name_plural = 'subjects'
        unique_together = ['school', 'code']
        ordering = ['name']
        indexes = [
            models.Index(fields=['school', 'is_active'], name='idx_subject_school_active'),
            models.Index(fields=['school', 'department'], name='idx_subject_school_dept'),
        ]

    def __str__(self):
        return f'{self.code} - {self.name} ({self.school.name})'


class Topic(BaseModel):
    """Topic/chapter within a subject. Supports hierarchical structure."""

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='topics', db_index=True
    )
    parent_topic = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtopics',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    order = models.IntegerField(
        default=0, help_text='Display order within parent'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'topic'
        verbose_name_plural = 'topics'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['subject', 'order'], name='idx_topic_subject_order'),
        ]

    def __str__(self):
        if self.parent_topic:
            return f'{self.parent_topic.name} > {self.name}'
        return f'{self.subject.code} - {self.name}'

    @property
    def school(self):
        return self.subject.school

    @property
    def depth(self):
        """Calculate depth in the topic hierarchy."""
        depth = 0
        current = self.parent_topic
        while current:
            depth += 1
            current = current.parent_topic
        return depth


class SubjectTeacherAssignment(BaseModel):
    """Assignment of a teacher to a subject for a specific class and term."""

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='teacher_assignments', db_index=True
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subject_assignments',
        db_index=True,
    )
    classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.CASCADE,
        related_name='subject_assignments',
        db_index=True,
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='subject_assignments',
        db_index=True,
    )
    is_primary = models.BooleanField(
        default=True, help_text='Whether this is the primary teacher for this subject/class'
    )

    class Meta:
        verbose_name = 'subject teacher assignment'
        verbose_name_plural = 'subject teacher assignments'
        unique_together = ['subject', 'teacher', 'classroom', 'term']
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['teacher', 'term'], name='idx_assignment_teacher_term'
            ),
        ]

    def __str__(self):
        return f'{self.teacher.full_name} -> {self.subject.code} ({self.classroom.name})'

    @property
    def school(self):
        return self.subject.school


class Enrollment(BaseModel):
    """Student enrollment in a subject for a specific class and term."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        DROPPED = 'dropped', 'Dropped'
        COMPLETED = 'completed', 'Completed'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        db_index=True,
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='enrollments', db_index=True
    )
    classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.CASCADE,
        related_name='enrollments',
        db_index=True,
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='enrollments',
        db_index=True,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    dropped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'enrollment'
        verbose_name_plural = 'enrollments'
        unique_together = ['student', 'subject', 'term']
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(
                fields=['student', 'term', 'status'], name='idx_enrollment_student_term'
            ),
            models.Index(
                fields=['subject', 'term', 'status'], name='idx_enrollment_subject_term'
            ),
        ]

    def __str__(self):
        return f'{self.student.full_name} enrolled in {self.subject.code} ({self.term.name})'

    @property
    def school(self):
        return self.subject.school

    def drop(self):
        """Drop the enrollment."""
        from django.utils import timezone
        self.status = self.Status.DROPPED
        self.dropped_at = timezone.now()
        self.save(update_fields=['status', 'dropped_at', 'updated_at'])


class Prerequisite(BaseModel):
    """Subject prerequisites - defines which subjects must be completed first."""

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='prerequisites', db_index=True
    )
    required_subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='prerequisite_for'
    )
    minimum_grade = models.CharField(
        max_length=5, blank=True, null=True,
        help_text='Minimum grade required, e.g. "C" or "50"'
    )

    class Meta:
        verbose_name = 'prerequisite'
        verbose_name_plural = 'prerequisites'
        unique_together = ['subject', 'required_subject']

    def __str__(self):
        grade_info = f' (min: {self.minimum_grade})' if self.minimum_grade else ''
        return f'{self.subject.code} requires {self.required_subject.code}{grade_info}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.subject == self.required_subject:
            raise ValidationError('A subject cannot be a prerequisite of itself.')
        if self.subject.school != self.required_subject.school:
            raise ValidationError('Prerequisites must be within the same school.')


class ClassSubject(BaseModel):
    """Many-to-many: which subjects are taught in which classes per term."""

    classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.CASCADE,
        related_name='class_subjects',
        db_index=True,
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='class_subjects', db_index=True
    )
    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='class_subjects',
        db_index=True,
    )
    is_compulsory = models.BooleanField(
        default=True, help_text='Whether all students in this class must take this subject'
    )

    class Meta:
        verbose_name = 'class subject'
        verbose_name_plural = 'class subjects'
        unique_together = ['classroom', 'subject', 'term']

    def __str__(self):
        return f'{self.classroom.name} - {self.subject.code} ({self.term.name})'

    @property
    def school(self):
        return self.subject.school


class Timetable(SchoolScopedModel):
    """Timetable definition for a school term."""

    term = models.ForeignKey(
        'schools.Term',
        on_delete=models.CASCADE,
        related_name='timetables',
        db_index=True,
    )
    name = models.CharField(
        max_length=100, help_text='e.g. "First Term 2025 Timetable"'
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'timetable'
        verbose_name_plural = 'timetables'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.school.name})'


class TimetableSlot(BaseModel):
    """Individual time slot in a timetable."""

    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, 'Monday'
        TUESDAY = 1, 'Tuesday'
        WEDNESDAY = 2, 'Wednesday'
        THURSDAY = 3, 'Thursday'
        FRIDAY = 4, 'Friday'
        SATURDAY = 5, 'Saturday'
        SUNDAY = 6, 'Sunday'

    timetable = models.ForeignKey(
        Timetable, on_delete=models.CASCADE, related_name='slots', db_index=True
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='timetable_slots'
    )
    classroom = models.ForeignKey(
        'schools.ClassRoom',
        on_delete=models.CASCADE,
        related_name='timetable_slots',
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='timetable_slots',
    )
    day_of_week = models.IntegerField(
        choices=DayOfWeek.choices, db_index=True
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_name = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='Physical room/location name'
    )

    class Meta:
        verbose_name = 'timetable slot'
        verbose_name_plural = 'timetable slots'
        ordering = ['day_of_week', 'start_time']
        indexes = [
            models.Index(
                fields=['timetable', 'day_of_week'], name='idx_slot_timetable_day'
            ),
            models.Index(
                fields=['teacher', 'day_of_week'], name='idx_slot_teacher_day'
            ),
            models.Index(
                fields=['classroom', 'day_of_week'], name='idx_slot_class_day'
            ),
        ]

    def __str__(self):
        return (
            f'{self.get_day_of_week_display()} {self.start_time}-{self.end_time}: '
            f'{self.subject.code} ({self.classroom.name})'
        )

    @property
    def school(self):
        return self.timetable.school

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError('Start time must be before end time.')
