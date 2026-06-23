# Generated migration for Phase 7A — School Registration & Onboarding

import django.db.models.deletion
import secrets
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0003_phase6a_academic_structure"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolRegistration",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("school_name", models.CharField(max_length=200)),
                (
                    "school_email",
                    models.EmailField(db_index=True, max_length=254, unique=True),
                ),
                (
                    "phone",
                    models.CharField(blank=True, max_length=20, null=True),
                ),
                ("address", models.TextField(blank=True, null=True)),
                (
                    "city",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "state",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "country",
                    models.CharField(default="Nigeria", max_length=100),
                ),
                ("website", models.URLField(blank=True, null=True)),
                (
                    "principal_name",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                (
                    "principal_email",
                    models.EmailField(blank=True, max_length=254, null=True),
                ),
                (
                    "principal_phone",
                    models.CharField(blank=True, max_length=20, null=True),
                ),
                (
                    "logo",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="school_registrations/logos/",
                    ),
                ),
                (
                    "motto",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "academic_year_start_month",
                    models.IntegerField(default=9),
                ),
                (
                    "grading_system",
                    models.CharField(
                        choices=[
                            ("letter", "Letter Grade (A-F)"),
                            ("percentage", "Percentage"),
                            ("gpa", "GPA (4.0 Scale)"),
                        ],
                        default="percentage",
                        max_length=20,
                    ),
                ),
                (
                    "timezone",
                    models.CharField(default="Africa/Lagos", max_length=50),
                ),
                (
                    "admin_first_name",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "admin_last_name",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "admin_email",
                    models.EmailField(blank=True, max_length=254, null=True),
                ),
                (
                    "admin_password_hash",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            (
                                "pending_verification",
                                "Pending Email Verification",
                            ),
                            ("email_verified", "Email Verified"),
                            ("onboarding_step_1", "Onboarding \u2013 Basic Info"),
                            (
                                "onboarding_step_2",
                                "Onboarding \u2013 Logo & Branding",
                            ),
                            (
                                "onboarding_step_3",
                                "Onboarding \u2013 Academic Setup",
                            ),
                            (
                                "onboarding_step_4",
                                "Onboarding \u2013 Admin Account",
                            ),
                            ("completed", "Completed"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending_verification",
                        max_length=30,
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "completed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "school",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="registration",
                        to="schools.school",
                    ),
                ),
            ],
            options={
                "verbose_name": "school registration",
                "verbose_name_plural": "school registrations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SchoolVerificationToken",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "token",
                    models.CharField(
                        db_index=True,
                        default=secrets.token_urlsafe,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("is_used", models.BooleanField(default=False)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "registration",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verification_tokens",
                        to="schools.schoolregistration",
                    ),
                ),
            ],
            options={
                "verbose_name": "school verification token",
                "verbose_name_plural": "school verification tokens",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["registration", "is_used"],
                        name="idx_svt_reg_used",
                    ),
                    models.Index(
                        fields=["expires_at"],
                        name="idx_svt_expires",
                    ),
                ],
            },
        ),
    ]
