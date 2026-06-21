"""
Core models - Abstract base models for the project.
"""

import uuid
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model with created_at and updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Abstract base model with UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """Abstract base model combining UUID PK and timestamps."""

    class Meta:
        abstract = True


class SchoolScopedModel(BaseModel):
    """Abstract base model for school-scoped (multi-tenant) models."""

    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='%(class)ss',
        db_index=True,
    )

    class Meta:
        abstract = True
