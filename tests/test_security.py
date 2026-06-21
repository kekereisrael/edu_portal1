"""
Tests for the core security module.
Covers throttling, middleware, validators, and exception handling.
"""

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()


class SecurityHeadersMiddlewareTests(TestCase):
    """Tests for SecurityHeaders middleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_security_headers_added(self):
        """Test that security headers are added to response."""
        from core.security import SecurityHeaders

        def get_response(request):
            return HttpResponse('OK')

        middleware = SecurityHeaders(get_response)
        request = self.factory.get('/')
        response = middleware(request)

        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-XSS-Protection'], '1; mode=block')
        self.assertEqual(response['Referrer-Policy'], 'strict-origin-when-cross-origin')


class IPBlockingMiddlewareTests(TestCase):
    """Tests for IP blocking middleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_get_client_ip_direct(self):
        """Test extracting client IP from direct connection."""
        from core.security import IPBlockingMiddleware
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        ip = IPBlockingMiddleware.get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')

    def test_get_client_ip_forwarded(self):
        """Test extracting client IP from X-Forwarded-For header."""
        from core.security import IPBlockingMiddleware
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 192.168.1.1'
        ip = IPBlockingMiddleware.get_client_ip(request)
        self.assertEqual(ip, '10.0.0.1')


class RequestSizeLimitMiddlewareTests(TestCase):
    """Tests for request size limit middleware."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_normal_request_passes(self):
        """Test that normal-sized requests pass through."""
        from core.security import RequestSizeLimitMiddleware

        def get_response(request):
            return HttpResponse('OK')

        middleware = RequestSizeLimitMiddleware(get_response)
        request = self.factory.post('/api/v1/subjects/')
        request.META['CONTENT_LENGTH'] = '1024'  # 1KB
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_oversized_request_rejected(self):
        """Test that oversized requests are rejected."""
        from core.security import RequestSizeLimitMiddleware

        def get_response(request):
            return HttpResponse('OK')

        middleware = RequestSizeLimitMiddleware(get_response)
        request = self.factory.post('/api/v1/subjects/')
        request.META['CONTENT_LENGTH'] = str(100 * 1024 * 1024)  # 100MB
        response = middleware(request)
        self.assertEqual(response.status_code, 413)


class ValidatorTests(TestCase):
    """Tests for custom validators."""

    def test_file_size_validator_passes(self):
        """Test file size validator with valid file."""
        from core.validators import FileSizeValidator
        from unittest.mock import Mock

        validator = FileSizeValidator(max_size_mb=10)
        mock_file = Mock()
        mock_file.size = 5 * 1024 * 1024  # 5MB
        # Should not raise
        validator(mock_file)

    def test_file_size_validator_fails(self):
        """Test file size validator with oversized file."""
        from core.validators import FileSizeValidator
        from django.core.exceptions import ValidationError
        from unittest.mock import Mock

        validator = FileSizeValidator(max_size_mb=10)
        mock_file = Mock()
        mock_file.size = 15 * 1024 * 1024  # 15MB
        with self.assertRaises(ValidationError):
            validator(mock_file)

    def test_phone_number_validator_valid(self):
        """Test phone number validator with valid numbers."""
        from core.validators import PhoneNumberValidator

        validator = PhoneNumberValidator()
        # Should not raise for valid numbers
        validator('+2348012345678')
        validator('08012345678')

    def test_phone_number_validator_invalid(self):
        """Test phone number validator with invalid numbers."""
        from core.validators import PhoneNumberValidator
        from django.core.exceptions import ValidationError

        validator = PhoneNumberValidator()
        with self.assertRaises(ValidationError):
            validator('12345')

    def test_strong_password_validator(self):
        """Test strong password validator."""
        from core.validators import StrongPasswordValidator
        from django.core.exceptions import ValidationError

        validator = StrongPasswordValidator()

        # Valid password
        validator('StrongP@ss1')

        # Too short
        with self.assertRaises(ValidationError):
            validator('Sh@1')

        # No uppercase
        with self.assertRaises(ValidationError):
            validator('weakpass@1')

        # No special char
        with self.assertRaises(ValidationError):
            validator('WeakPass1')

    def test_exam_duration_validator(self):
        """Test exam duration validator."""
        from core.validators import validate_exam_duration
        from django.core.exceptions import ValidationError

        # Valid duration
        validate_exam_duration(60)

        # Too short
        with self.assertRaises(ValidationError):
            validate_exam_duration(3)

        # Too long
        with self.assertRaises(ValidationError):
            validate_exam_duration(600)


class ExceptionHandlerTests(TestCase):
    """Tests for custom exception handler."""

    def test_school_context_required_exception(self):
        """Test SchoolContextRequired exception."""
        from core.exceptions import SchoolContextRequired
        exc = SchoolContextRequired()
        self.assertEqual(exc.status_code, 400)
        self.assertIn('School context', str(exc.detail))

    def test_subscription_required_exception(self):
        """Test SubscriptionRequired exception."""
        from core.exceptions import SubscriptionRequired
        exc = SubscriptionRequired()
        self.assertEqual(exc.status_code, 402)

    def test_storage_quota_exceeded_exception(self):
        """Test StorageQuotaExceeded exception."""
        from core.exceptions import StorageQuotaExceeded
        exc = StorageQuotaExceeded()
        self.assertEqual(exc.status_code, 413)

    def test_exam_not_available_exception(self):
        """Test ExamNotAvailable exception."""
        from core.exceptions import ExamNotAvailable
        exc = ExamNotAvailable()
        self.assertEqual(exc.status_code, 403)
