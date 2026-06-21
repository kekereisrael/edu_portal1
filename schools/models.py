"""
Models for the schools app - Multi-tenancy support.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class School(models.Model):
    """School/tenant model for multi-tenancy."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, default='Nigeria')
    logo = models.ImageField(upload_to='schools/logos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_schools',
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'school'
        verbose_name_plural = 'schools'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while School.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f'{original_slug}-{counter}'
                counter += 1
        super().save(*args, **kwargs)


class SchoolMembership(models.Model):
    """Tracks which users belong to which schools and their roles."""

    class SchoolRole(models.TextChoices):
        SCHOOL_ADMIN = 'school_admin', 'School Admin'
        TEACHER = 'teacher', 'Teacher'
        STUDENT = 'student', 'Student'
        PARENT = 'parent', 'Parent'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='memberships', db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='school_memberships',
        db_index=True,
    )
    role = models.CharField(
        max_length=20, choices=SchoolRole.choices, db_index=True
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'school membership'
        verbose_name_plural = 'school memberships'
        unique_together = ['school', 'user']
        ordering = ['-joined_at']

    def __str__(self):
        return f'{self.user.email} - {self.school.name} ({self.role})'


class SchoolSettings(models.Model):
    """Per-school configuration settings."""

    class GradingSystem(models.TextChoices):
        LETTER = 'letter', 'Letter Grade (A-F)'
        PERCENTAGE = 'percentage', 'Percentage'
        GPA = 'gpa', 'GPA (4.0 Scale)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        School, on_delete=models.CASCADE, related_name='settings'
    )
    timezone = models.CharField(max_length=50, default='Africa/Lagos')
    grading_system = models.CharField(
        max_length=20, choices=GradingSystem.choices, default=GradingSystem.PERCENTAGE
    )
    grading_scale = models.JSONField(
        default=dict,
        blank=True,
        help_text='Custom grade boundaries, e.g. {"A": 70, "B": 60, "C": 50, "D": 40, "F": 0}',
    )
    academic_year_start_month = models.IntegerField(default=9)
    allow_parent_access = models.BooleanField(default=True)
    exam_proctoring_enabled = models.BooleanField(default=False)
    max_login_attempts = models.IntegerField(default=5)
    session_timeout_minutes = models.IntegerField(default=60)

    class Meta:
        verbose_name = 'school settings'
        verbose_name_plural = 'school settings'

    def __str__(self):
        return f'Settings for {self.school.name}'


class AcademicYear(models.Model):
    """Academic year definition per school."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='academic_years', db_index=True
    )
    name = models.CharField(max_length=50, help_text='e.g. 2025/2026')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'academic year'
        verbose_name_plural = 'academic years'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.school.name} - {self.name}'

    def save(self, *args, **kwargs):
        # Ensure only one current academic year per school
        if self.is_current:
            AcademicYear.objects.filter(
                school=self.school, is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class Term(models.Model):
    """Term/semester within an academic year."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='terms', db_index=True
    )
    name = models.CharField(max_length=50, help_text='e.g. First Term')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, db_index=True)
    order = models.IntegerField()

    class Meta:
        verbose_name = 'term'
        verbose_name_plural = 'terms'
        ordering = ['order']

    def __str__(self):
        return f'{self.academic_year.name} - {self.name}'

    def save(self, *args, **kwargs):
        # Ensure only one current term per academic year
        if self.is_current:
            Term.objects.filter(
                academic_year=self.academic_year, is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    @property
    def school(self):
        return self.academic_year.school


class Department(models.Model):
    """Academic department within a school."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='departments', db_index=True
    )
    name = models.CharField(max_length=100)
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'department'
        verbose_name_plural = 'departments'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.school.name})'


class ClassRoom(models.Model):
    """Class/section within a school."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='classrooms', db_index=True
    )
    name = models.CharField(max_length=50, help_text='e.g. JSS 1A')
    grade_level = models.CharField(max_length=20, db_index=True)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.CASCADE, related_name='classrooms', db_index=True
    )
    class_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_teacher_of',
    )
    max_students = models.IntegerField(default=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'classroom'
        verbose_name_plural = 'classrooms'
        ordering = ['grade_level', 'name']

    def __str__(self):
        return f'{self.name} ({self.school.name})'

    @property
    def student_count(self):
        from accounts.models import User
        return SchoolMembership.objects.filter(
            school=self.school,
            role=SchoolMembership.SchoolRole.STUDENT,
            is_active=True,
        ).count()
