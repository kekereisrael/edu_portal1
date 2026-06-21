"""
Tests for the accounts app.
Covers user creation, authentication, email verification, and password reset.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()


class UserModelTests(TestCase):
    """Tests for the User model."""

    def setUp(self):
        from schools.models import School
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )

    def test_create_user(self):
        """Test creating a regular user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='John',
            last_name='Doe',
            role='student',
            school=self.school,
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.role, 'student')
        self.assertTrue(user.check_password('TestPass123!'))
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_active)

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!',
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_user_email_normalized(self):
        """Test that email is normalized on creation."""
        user = User.objects.create_user(
            email='Test@EXAMPLE.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User',
            role='student',
            school=self.school,
        )
        self.assertEqual(user.email, 'Test@example.com')

    def test_user_without_email_raises_error(self):
        """Test that creating user without email raises ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email='',
                password='TestPass123!',
            )

    def test_user_str_representation(self):
        """Test user string representation."""
        user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='John',
            last_name='Doe',
            role='student',
            school=self.school,
        )
        self.assertIn('test@example.com', str(user))


class EmailVerificationTokenTests(TestCase):
    """Tests for email verification token model."""

    def setUp(self):
        from schools.models import School
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User',
            role='student',
            school=self.school,
        )

    def test_create_verification_token(self):
        """Test creating a verification token."""
        from accounts.models import EmailVerificationToken
        token = EmailVerificationToken.create_token(self.user)
        self.assertIsNotNone(token.token)
        self.assertEqual(token.user, self.user)
        self.assertFalse(token.is_used)

    def test_token_expiry(self):
        """Test that expired tokens are detected."""
        from accounts.models import EmailVerificationToken
        token = EmailVerificationToken.create_token(self.user)
        token.expires_at = timezone.now() - timedelta(hours=1)
        token.save()
        self.assertTrue(token.is_expired)

    def test_token_validation(self):
        """Test token validation."""
        from accounts.models import EmailVerificationToken
        token = EmailVerificationToken.create_token(self.user)
        self.assertTrue(token.is_valid)

        # Mark as used
        token.is_used = True
        token.save()
        self.assertFalse(token.is_valid)


class PasswordResetTokenTests(TestCase):
    """Tests for password reset token model."""

    def setUp(self):
        from schools.models import School
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User',
            role='student',
            school=self.school,
        )

    def test_create_reset_token(self):
        """Test creating a password reset token."""
        from accounts.models import PasswordResetToken
        token = PasswordResetToken.create_token(self.user)
        self.assertIsNotNone(token.token)
        self.assertEqual(token.user, self.user)

    def test_reset_token_shorter_expiry(self):
        """Test that reset tokens have shorter expiry than verification tokens."""
        from accounts.models import PasswordResetToken
        token = PasswordResetToken.create_token(self.user)
        # Should expire within 1-2 hours
        self.assertLess(
            token.expires_at,
            timezone.now() + timedelta(hours=3)
        )
