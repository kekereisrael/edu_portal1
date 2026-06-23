"""
Models for the schools app - Multi-tenancy support.
"""

import uuid
import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone
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


# ─────────────────────────────────────────────────────────────────────────────
# ACADEMIC SESSION  (replaces the old AcademicYear for Nigerian school context)
# ─────────────────────────────────────────────────────────────────────────────

class AcademicSession(models.Model):
    """
    Academic session for a school, e.g. '2024/2025'.
    Nigerian schools run September–July with three terms per session.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='academic_sessions', db_index=True
    )
    name = models.CharField(max_length=50, help_text='e.g. 2024/2025')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'academic session'
        verbose_name_plural = 'academic sessions'
        ordering = ['-start_date']
        unique_together = ['school', 'name']

    def __str__(self):
        return f'{self.school.name} – {self.name}'

    def save(self, *args, **kwargs):
        # Ensure only one current session per school
        if self.is_current:
            AcademicSession.objects.filter(
                school=self.school, is_current=True
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# ACADEMIC YEAR  (kept for backward-compat with existing migrations/subjects)
# ─────────────────────────────────────────────────────────────────────────────

class AcademicYear(models.Model):
    """Academic year definition per school (legacy – use AcademicSession for new code)."""

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


# ─────────────────────────────────────────────────────────────────────────────
# CLASS LEVEL  (JSS1–JSS3, SSS1–SSS3)
# ─────────────────────────────────────────────────────────────────────────────

class ClassLevel(models.Model):
    """
    Defines the six standard Nigerian secondary school class levels:
    JSS1, JSS2, JSS3, SSS1, SSS2, SSS3.
    Each school gets its own set so they can customise display names.
    """

    class LevelCode(models.TextChoices):
        JSS1 = 'JSS1', 'JSS 1'
        JSS2 = 'JSS2', 'JSS 2'
        JSS3 = 'JSS3', 'JSS 3'
        SSS1 = 'SSS1', 'SSS 1'
        SSS2 = 'SSS2', 'SSS 2'
        SSS3 = 'SSS3', 'SSS 3'

    class Category(models.TextChoices):
        JUNIOR = 'junior', 'Junior Secondary'
        SENIOR = 'senior', 'Senior Secondary'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='class_levels', db_index=True
    )
    code = models.CharField(
        max_length=10, choices=LevelCode.choices, db_index=True
    )
    display_name = models.CharField(
        max_length=50,
        blank=True,
        help_text='Custom display name, e.g. "Junior Secondary School 1". '
                  'Leave blank to use the default.',
    )
    category = models.CharField(
        max_length=10, choices=Category.choices, db_index=True
    )
    order = models.PositiveSmallIntegerField(
        default=0, help_text='Sort order (1=JSS1 … 6=SSS3)'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'class level'
        verbose_name_plural = 'class levels'
        unique_together = ['school', 'code']
        ordering = ['order', 'code']

    def __str__(self):
        return f'{self.get_code_display()} ({self.school.name})'

    @property
    def name(self):
        return self.display_name or self.get_code_display()

    def save(self, *args, **kwargs):
        # Auto-set category and order from code
        junior_codes = {
            self.LevelCode.JSS1, self.LevelCode.JSS2, self.LevelCode.JSS3
        }
        order_map = {
            self.LevelCode.JSS1: 1,
            self.LevelCode.JSS2: 2,
            self.LevelCode.JSS3: 3,
            self.LevelCode.SSS1: 4,
            self.LevelCode.SSS2: 5,
            self.LevelCode.SSS3: 6,
        }
        if self.code in junior_codes:
            self.category = self.Category.JUNIOR
        else:
            self.category = self.Category.SENIOR
        if not self.order:
            self.order = order_map.get(self.code, 0)
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# SCHOOL SETTINGS  (enhanced with principal_name + current_session)
# ─────────────────────────────────────────────────────────────────────────────

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
    # ── School Profile fields ────────────────────────────────────────────────
    principal_name = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Full name of the school principal / head teacher'
    )
    current_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_for_settings',
        help_text='The currently active academic session',
    )
    motto = models.CharField(max_length=255, blank=True, null=True)
    # ── Operational settings ─────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# DEPARTMENT
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# CLASSROOM  (enhanced: links to ClassLevel)
# ─────────────────────────────────────────────────────────────────────────────

class ClassRoom(models.Model):
    """
    A class section within a school, e.g. 'JSS 1A'.
    Links to a ClassLevel (JSS1–SSS3) and an AcademicYear.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='classrooms', db_index=True
    )
    name = models.CharField(max_length=50, help_text='e.g. JSS 1A')
    grade_level = models.CharField(max_length=20, db_index=True)
    # New: explicit link to ClassLevel
    class_level = models.ForeignKey(
        ClassLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classrooms',
        db_index=True,
    )
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
        return self.student_assignments.filter(is_active=True).count()

    @property
    def students(self):
        """Return queryset of active students in this classroom."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        student_ids = self.student_assignments.filter(
            is_active=True
        ).values_list('student_id', flat=True)
        return User.objects.filter(id__in=student_ids)


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT CLASS ASSIGNMENT  (enroll a student into a class for a session)
# ─────────────────────────────────────────────────────────────────────────────

class StudentClassAssignment(models.Model):
    """
    Assigns a student to a specific classroom for an academic session.
    Replaces the loose SchoolMembership-based approach for class enrollment.
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TRANSFERRED = 'transferred', 'Transferred'
        GRADUATED = 'graduated', 'Graduated'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='student_class_assignments',
        db_index=True,
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='class_assignments',
        db_index=True,
    )
    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name='student_assignments',
        db_index=True,
    )
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name='student_assignments',
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_assignments_made',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'student class assignment'
        verbose_name_plural = 'student class assignments'
        # A student can only be in one class per session
        unique_together = ['student', 'academic_session']
        ordering = ['-assigned_at']
        indexes = [
            models.Index(
                fields=['school', 'academic_session', 'status'],
                name='idx_sca_school_session_status',
            ),
            models.Index(
                fields=['classroom', 'status'],
                name='idx_sca_classroom_status',
            ),
        ]

    def __str__(self):
        return (
            f'{self.student.get_full_name()} → {self.classroom.name} '
            f'({self.academic_session.name})'
        )


# ─────────────────────────────────────────────────────────────────────────────
# STORAGE USAGE
# ─────────────────────────────────────────────────────────────────────────────

class StorageUsage(models.Model):
    """Track storage consumption per school for quota enforcement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        School, on_delete=models.CASCADE, related_name='storage_usage'
    )
    used_bytes = models.BigIntegerField(
        default=0, help_text='Total storage used in bytes'
    )
    file_count = models.IntegerField(
        default=0, help_text='Total number of files stored'
    )
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'storage usage'
        verbose_name_plural = 'storage usages'

    def __str__(self):
        return f'{self.school.name} - {self.used_bytes_display}'

    @property
    def used_bytes_display(self):
        """Human-readable storage usage."""
        if self.used_bytes < 1024:
            return f'{self.used_bytes} B'
        elif self.used_bytes < 1024 ** 2:
            return f'{self.used_bytes / 1024:.1f} KB'
        elif self.used_bytes < 1024 ** 3:
            return f'{self.used_bytes / (1024 ** 2):.1f} MB'
        return f'{self.used_bytes / (1024 ** 3):.2f} GB'

    @property
    def used_gb(self):
        """Storage used in GB."""
        return self.used_bytes / (1024 ** 3)

    def add_file(self, file_size_bytes):
        """Record a new file upload."""
        self.used_bytes += file_size_bytes
        self.file_count += 1
        self.save(update_fields=['used_bytes', 'file_count', 'last_calculated_at'])

    def remove_file(self, file_size_bytes):
        """Record a file deletion."""
        self.used_bytes = max(0, self.used_bytes - file_size_bytes)
        self.file_count = max(0, self.file_count - 1)
        self.save(update_fields=['used_bytes', 'file_count', 'last_calculated_at'])

    def is_within_quota(self, additional_bytes=0):
        """Check if school is within storage quota based on their plan."""
        try:
            subscription = self.school.subscription
            max_storage_bytes = subscription.plan.max_storage_gb * (1024 ** 3)
            return (self.used_bytes + additional_bytes) <= max_storage_bytes
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# SCHOOL REGISTRATION  (Phase 7A — public signup + onboarding wizard)
# ─────────────────────────────────────────────────────────────────────────────

class SchoolRegistration(models.Model):
    """
    Tracks a school's registration/onboarding progress before the School
    record is fully activated.

    Flow:
      1. POST /register/  → creates SchoolRegistration (status=pending_verification)
                            + sends verification email
      2. POST /register/verify-email/  → status=email_verified
      3. POST /register/onboarding/step-1/ … step-4/  → status=onboarding_*
      4. POST /register/complete/  → creates School + SchoolSettings + owner User
                                     status=completed
    """

    class Status(models.TextChoices):
        PENDING_VERIFICATION = 'pending_verification', 'Pending Email Verification'
        EMAIL_VERIFIED       = 'email_verified',       'Email Verified'
        ONBOARDING_STEP_1    = 'onboarding_step_1',    'Onboarding – Basic Info'
        ONBOARDING_STEP_2    = 'onboarding_step_2',    'Onboarding – Logo & Branding'
        ONBOARDING_STEP_3    = 'onboarding_step_3',    'Onboarding – Academic Setup'
        ONBOARDING_STEP_4    = 'onboarding_step_4',    'Onboarding – Admin Account'
        COMPLETED            = 'completed',            'Completed'
        REJECTED             = 'rejected',             'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Contact / identity ────────────────────────────────────────────────────
    school_name    = models.CharField(max_length=200)
    school_email   = models.EmailField(unique=True, db_index=True)
    phone          = models.CharField(max_length=20, blank=True, null=True)
    address        = models.TextField(blank=True, null=True)
    city           = models.CharField(max_length=100, blank=True, null=True)
    state          = models.CharField(max_length=100, blank=True, null=True)
    country        = models.CharField(max_length=100, default='Nigeria')
    website        = models.URLField(blank=True, null=True)

    # ── Principal / head teacher ──────────────────────────────────────────────
    principal_name  = models.CharField(max_length=200, blank=True, null=True)
    principal_email = models.EmailField(blank=True, null=True)
    principal_phone = models.CharField(max_length=20, blank=True, null=True)

    # ── Branding (step 2) ─────────────────────────────────────────────────────
    logo   = models.ImageField(upload_to='school_registrations/logos/', blank=True, null=True)
    motto  = models.CharField(max_length=255, blank=True, null=True)

    # ── Academic setup (step 3) ───────────────────────────────────────────────
    academic_year_start_month = models.IntegerField(default=9)
    grading_system = models.CharField(
        max_length=20,
        choices=SchoolSettings.GradingSystem.choices,
        default=SchoolSettings.GradingSystem.PERCENTAGE,
    )
    timezone = models.CharField(max_length=50, default='Africa/Lagos')

    # ── Admin account (step 4) ────────────────────────────────────────────────
    admin_first_name = models.CharField(max_length=100, blank=True, null=True)
    admin_last_name  = models.CharField(max_length=100, blank=True, null=True)
    admin_email      = models.EmailField(blank=True, null=True)
    # Password is stored hashed only after step 4; cleared after school is created
    admin_password_hash = models.CharField(max_length=255, blank=True, null=True)

    # ── Workflow ──────────────────────────────────────────────────────────────
    status     = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_VERIFICATION,
        db_index=True,
    )
    # FK to the created School (set when status=completed)
    school     = models.OneToOneField(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registration',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'school registration'
        verbose_name_plural = 'school registrations'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.school_name} ({self.school_email}) – {self.status}'

    @property
    def is_email_verified(self):
        return self.status not in (
            self.Status.PENDING_VERIFICATION,
            self.Status.REJECTED,
        )

    @property
    def onboarding_progress(self):
        """Return 0-100 progress percentage."""
        progress_map = {
            self.Status.PENDING_VERIFICATION: 0,
            self.Status.EMAIL_VERIFIED:       20,
            self.Status.ONBOARDING_STEP_1:    40,
            self.Status.ONBOARDING_STEP_2:    60,
            self.Status.ONBOARDING_STEP_3:    80,
            self.Status.ONBOARDING_STEP_4:    90,
            self.Status.COMPLETED:            100,
        }
        return progress_map.get(self.status, 0)


class SchoolVerificationToken(models.Model):
    """
    One-time email verification token for a SchoolRegistration.
    Expires in 48 hours.  Invalidated on use.
    """

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey(
        SchoolRegistration,
        on_delete=models.CASCADE,
        related_name='verification_tokens',
    )
    token        = models.CharField(
        max_length=64, unique=True, db_index=True, default=secrets.token_urlsafe
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField()
    is_used      = models.BooleanField(default=False)
    used_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'school verification token'
        verbose_name_plural = 'school verification tokens'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['registration', 'is_used'], name='idx_svt_reg_used'),
            models.Index(fields=['expires_at'],               name='idx_svt_expires'),
        ]

    def __str__(self):
        return f'Verification token for {self.registration.school_email}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=48)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    def mark_used(self):
        """Mark token as used and advance registration to email_verified."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])
        reg = self.registration
        if reg.status == SchoolRegistration.Status.PENDING_VERIFICATION:
            reg.status = SchoolRegistration.Status.EMAIL_VERIFIED
            reg.save(update_fields=['status', 'updated_at'])

    @classmethod
    def create_for_registration(cls, registration):
        """Invalidate old tokens and create a fresh one."""
        cls.objects.filter(registration=registration, is_used=False).update(is_used=True)
        return cls.objects.create(
            registration=registration,
            expires_at=timezone.now() + timezone.timedelta(hours=48),
        )
