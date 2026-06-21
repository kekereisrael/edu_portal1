"""
Custom validators for the educational portal.
Provides input validation, file validation, and data integrity checks.
"""

import re
import os
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible


@deconstructible
class FileSizeValidator:
    """Validate that file size doesn't exceed the maximum allowed size."""

    def __init__(self, max_size_mb=10):
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def __call__(self, value):
        if value.size > self.max_size_bytes:
            raise ValidationError(
                f'File size ({value.size / (1024*1024):.1f}MB) exceeds '
                f'maximum allowed size ({self.max_size_mb}MB).'
            )

    def __eq__(self, other):
        return isinstance(other, FileSizeValidator) and self.max_size_mb == other.max_size_mb


@deconstructible
class SafeFileNameValidator:
    """Validate that filename doesn't contain dangerous characters."""

    DANGEROUS_PATTERNS = [
        r'\.\.',  # Directory traversal
        r'[<>:"|?*]',  # Windows invalid chars
        r'[\x00-\x1f]',  # Control characters
        r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)',  # Windows reserved names
    ]

    def __call__(self, value):
        filename = os.path.basename(value.name) if hasattr(value, 'name') else str(value)
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                raise ValidationError(
                    f'Filename "{filename}" contains invalid characters.'
                )


@deconstructible
class ImageFileValidator:
    """Validate image files - extension and content type."""

    ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']
    ALLOWED_CONTENT_TYPES = [
        'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'
    ]

    def __call__(self, value):
        ext = os.path.splitext(value.name)[1][1:].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f'File extension "{ext}" is not allowed. '
                f'Allowed: {", ".join(self.ALLOWED_EXTENSIONS)}'
            )

        if hasattr(value, 'content_type') and value.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                f'Content type "{value.content_type}" is not allowed for images.'
            )


@deconstructible
class DocumentFileValidator:
    """Validate document files for materials upload."""

    ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'csv']
    MAX_SIZE_MB = 50

    def __call__(self, value):
        ext = os.path.splitext(value.name)[1][1:].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f'File extension "{ext}" is not allowed. '
                f'Allowed: {", ".join(self.ALLOWED_EXTENSIONS)}'
            )

        if value.size > self.MAX_SIZE_MB * 1024 * 1024:
            raise ValidationError(
                f'File size exceeds maximum of {self.MAX_SIZE_MB}MB.'
            )


@deconstructible
class PhoneNumberValidator:
    """Validate phone numbers (Nigerian format primarily)."""

    PATTERNS = [
        r'^\+234[0-9]{10}$',  # Nigerian international format
        r'^0[789][01][0-9]{8}$',  # Nigerian local format
        r'^\+[1-9][0-9]{7,14}$',  # General international format
    ]

    def __call__(self, value):
        if not value:
            return

        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        for pattern in self.PATTERNS:
            if re.match(pattern, cleaned):
                return

        raise ValidationError(
            'Invalid phone number format. Use international format (e.g., +234XXXXXXXXXX).'
        )


@deconstructible
class StrongPasswordValidator:
    """
    Validate password strength beyond Django's built-in validators.
    Requires mix of uppercase, lowercase, digits, and special characters.
    """

    def __init__(self, min_length=8, require_uppercase=True, require_lowercase=True,
                 require_digit=True, require_special=True):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special

    def __call__(self, value):
        errors = []

        if len(value) < self.min_length:
            errors.append(f'Password must be at least {self.min_length} characters.')

        if self.require_uppercase and not re.search(r'[A-Z]', value):
            errors.append('Password must contain at least one uppercase letter.')

        if self.require_lowercase and not re.search(r'[a-z]', value):
            errors.append('Password must contain at least one lowercase letter.')

        if self.require_digit and not re.search(r'[0-9]', value):
            errors.append('Password must contain at least one digit.')

        if self.require_special and not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', value):
            errors.append('Password must contain at least one special character.')

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            f'Password must be at least {self.min_length} characters and contain '
            'uppercase, lowercase, digit, and special characters.'
        )


@deconstructible
class SchoolCodeValidator:
    """Validate school registration codes."""

    def __call__(self, value):
        if not re.match(r'^[A-Z]{2,5}-[0-9]{4,8}$', value):
            raise ValidationError(
                'School code must be in format: XX-XXXX (2-5 uppercase letters, '
                'dash, 4-8 digits). Example: SCH-12345'
            )


def validate_json_schema(value, schema):
    """
    Validate a JSON value against a simple schema definition.
    
    Args:
        value: The JSON data to validate
        schema: Dict defining expected structure {field: type}
    """
    if not isinstance(value, dict):
        raise ValidationError('Value must be a JSON object.')

    for field, expected_type in schema.items():
        if field not in value:
            raise ValidationError(f'Missing required field: {field}')
        if not isinstance(value[field], expected_type):
            raise ValidationError(
                f'Field "{field}" must be of type {expected_type.__name__}.'
            )


def validate_exam_duration(value):
    """Validate exam duration is within reasonable bounds."""
    if value < 5:
        raise ValidationError('Exam duration must be at least 5 minutes.')
    if value > 480:
        raise ValidationError('Exam duration cannot exceed 8 hours (480 minutes).')


def validate_percentage(value):
    """Validate a percentage value (0-100)."""
    if value < 0 or value > 100:
        raise ValidationError('Percentage must be between 0 and 100.')


def validate_positive_decimal(value):
    """Validate that a decimal value is positive."""
    if value <= 0:
        raise ValidationError('Value must be greater than zero.')
