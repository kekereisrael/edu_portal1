"""
Models for the parents app.

ParentProfile — extended profile for parent users (contact info, occupation).
ParentStudentLink lives in schools.models to keep school-scoped data together.
"""

import uuid
from django.conf import settings
from django.db import models


class ParentProfile(models.Model):
    """
    Extended profile for parent/guardian users.

    One ParentProfile per User (global, not school-scoped).
    The school-scoped parent↔student relationship is in
    schools.ParentStudentLink.
    """

    class Occupation(models.TextChoices):
        EMPLOYED      = 'employed',      'Employed'
        SELF_EMPLOYED = 'self_employed',  'Self-Employed'
        BUSINESS      = 'business',      'Business Owner'
        CIVIL_SERVANT = 'civil_servant',  'Civil Servant'
        RETIRED       = 'retired',       'Retired'
        UNEMPLOYED    = 'unemployed',    'Unemployed'
        OTHER         = 'other',         'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='parent_profile',
    )

    # ── Contact ───────────────────────────────────────────────────────────────
    phone_alt = models.CharField(
        max_length=20, blank=True, null=True,
        help_text='Alternative phone number',
    )
    home_address = models.TextField(blank=True, null=True)
    city         = models.CharField(max_length=100, blank=True, null=True)
    state        = models.CharField(max_length=100, blank=True, null=True)
    country      = models.CharField(max_length=100, default='Nigeria')

    # ── Personal ──────────────────────────────────────────────────────────────
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='parents/profile_pictures/',
        blank=True,
        null=True,
    )
    occupation      = models.CharField(
        max_length=20,
        choices=Occupation.choices,
        blank=True,
        null=True,
    )
    employer_name   = models.CharField(max_length=200, blank=True, null=True)
    national_id     = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='NIN / Passport / Voter card number',
    )

    # ── Notification preferences ──────────────────────────────────────────────
    receive_sms_alerts   = models.BooleanField(default=True)
    receive_email_alerts = models.BooleanField(default=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'parent profile'
        verbose_name_plural = 'parent profiles'

    def __str__(self):
        return f'Parent profile of {self.user.get_full_name() or self.user.email}'

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email

    @property
    def phone(self):
        return self.user.phone
