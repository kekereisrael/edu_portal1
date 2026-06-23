"""
Custom User model and profile models for the accounts app.
"""

import uuid
import secrets
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager that uses email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_platform_admin', True)
        extra_fields.setdefault('role', User.Role.PLATFORM_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User model with email-based authentication and role support."""

    class Role(models.TextChoices):
        PLATFORM_ADMIN = 'platform_admin', 'Platform Admin'
        SCHOOL_ADMIN = 'school_admin', 'School Admin'
        TEACHER = 'teacher', 'Teacher'
        STUDENT = 'student', 'Student'
        PARENT = 'parent', 'Parent'

    # Remove username field, use email instead
    username = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField('email address', unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_platform_admin = models.BooleanField(default=False, db_index=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.email})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def is_school_admin(self):
        return self.role == self.Role.SCHOOL_ADMIN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_parent(self):
        return self.role == self.Role.PARENT


class Profile(models.Model):
    """Extended profile information for all users."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, default='Nigeria')

    class Meta:
        verbose_name = 'profile'
        verbose_name_plural = 'profiles'

    def __str__(self):
        return f'Profile of {self.user.full_name}'


class StudentProfile(models.Model):
    """
    Extended profile for students — admission number, guardian info,
    profile picture, and school-specific metadata.

    One StudentProfile per User (school-scoped via the school FK so that
    a student who transfers schools can have a profile per school).
    """

    class Gender(models.TextChoices):
        MALE   = 'male',   'Male'
        FEMALE = 'female', 'Female'
        OTHER  = 'other',  'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='student_profiles',
        db_index=True,
    )
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='student_profiles',
        db_index=True,
    )

    # ── Academic identity ─────────────────────────────────────────────────────
    admission_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='School-assigned admission / registration number',
    )
    date_of_admission = models.DateField(blank=True, null=True)

    # ── Personal info ─────────────────────────────────────────────────────────
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True,
    )
    profile_picture = models.ImageField(
        upload_to='students/profile_pictures/',
        blank=True,
        null=True,
    )
    home_address = models.TextField(blank=True, null=True)
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    nationality = models.CharField(max_length=100, default='Nigerian')
    religion = models.CharField(max_length=50, blank=True, null=True)

    # ── Guardian / parent contact ─────────────────────────────────────────────
    guardian_name  = models.CharField(max_length=200, blank=True, null=True)
    guardian_phone = models.CharField(max_length=20,  blank=True, null=True)
    guardian_email = models.EmailField(blank=True, null=True)
    guardian_relationship = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='e.g. Father, Mother, Uncle, Guardian',
    )
    guardian_address = models.TextField(blank=True, null=True)

    # ── Medical / emergency ───────────────────────────────────────────────────
    blood_group = models.CharField(max_length=5, blank=True, null=True)
    genotype    = models.CharField(max_length=5, blank=True, null=True)
    medical_conditions = models.TextField(
        blank=True, null=True,
        help_text='Known allergies, conditions, or special needs',
    )
    emergency_contact_name  = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20,  blank=True, null=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'student profile'
        verbose_name_plural = 'student profiles'
        unique_together = ['user', 'school']
        ordering = ['user__last_name', 'user__first_name']
        indexes = [
            models.Index(fields=['school', 'admission_number'], name='idx_sp_school_admission'),
        ]

    def __str__(self):
        return (
            f'{self.user.get_full_name()} '
            f'[{self.admission_number or "no-admission#"}] '
            f'@ {self.school.name}'
        )


class UserSession(models.Model):
    """Track active user sessions for device management."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    token_jti = models.CharField(max_length=255, unique=True, db_index=True)
    device_type = models.CharField(
        max_length=50,
        choices=[
            ('web', 'Web Browser'),
            ('mobile_android', 'Android'),
            ('mobile_ios', 'iOS'),
        ],
        default='web',
    )
    device_name = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'user session'
        verbose_name_plural = 'user sessions'
        ordering = ['-last_activity']

    def __str__(self):
        return f'{self.user.email} - {self.device_type} ({self.ip_address})'


class LoginAttempt(models.Model):
    """Record login attempts for security monitoring."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField()
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=50, blank=True, null=True)
    attempted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'login attempt'
        verbose_name_plural = 'login attempts'
        ordering = ['-attempted_at']

    def __str__(self):
        status = 'Success' if self.success else 'Failed'
        return f'{self.email} - {status} at {self.attempted_at}'


class EmailVerificationToken(models.Model):
    """Store email verification tokens for secure email verification flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='email_verification_tokens'
    )
    token = models.CharField(
        max_length=64, unique=True, db_index=True, default=secrets.token_urlsafe
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'email verification token'
        verbose_name_plural = 'email verification tokens'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_used'], name='idx_email_verify_user_used'),
            models.Index(fields=['expires_at'], name='idx_email_verify_expires'),
        ]

    def __str__(self):
        return f'Verification token for {self.user.email}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    def mark_used(self):
        """Mark token as used and verify the user's email."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])
        # Mark user as verified
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])

    @classmethod
    def create_for_user(cls, user):
        """Create a new verification token, invalidating any existing ones."""
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        return cls.objects.create(
            user=user,
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )


class PasswordResetToken(models.Model):
    """Store password reset tokens with expiry for secure password reset flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='password_reset_tokens'
    )
    token = models.CharField(
        max_length=64, unique=True, db_index=True, default=secrets.token_urlsafe
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(
        help_text='IP address that requested the reset'
    )

    class Meta:
        verbose_name = 'password reset token'
        verbose_name_plural = 'password reset tokens'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_used'], name='idx_pwd_reset_user_used'),
            models.Index(fields=['expires_at'], name='idx_pwd_reset_expires'),
        ]

    def __str__(self):
        return f'Password reset token for {self.user.email}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=1)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    def mark_used(self):
        """Mark token as used."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])

    @classmethod
    def create_for_user(cls, user, ip_address):
        """Create a new reset token, invalidating any existing ones."""
        # Check rate limiting: max 3 reset requests per hour
        recent_count = cls.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timezone.timedelta(hours=1),
        ).count()
        if recent_count >= 3:
            raise ValueError('Too many password reset requests. Please try again later.')

        # Invalidate existing tokens
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        return cls.objects.create(
            user=user,
            ip_address=ip_address,
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
