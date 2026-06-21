"""
Custom User model and profile models for the accounts app.
"""

import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


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
