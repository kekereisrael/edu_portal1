"""
Test configuration and shared fixtures for the educational portal.
"""

import pytest
from django.test import TestCase, RequestFactory
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from uuid import uuid4

User = get_user_model()


class BaseTestCase(TestCase):
    """Base test case with common setup for all tests."""

    def setUp(self):
        """Set up test data common to all tests."""
        self.factory = RequestFactory()
        self.school = self._create_school()
        self.admin_user = self._create_user('admin@test.com', 'school_admin')
        self.teacher_user = self._create_user('teacher@test.com', 'teacher')
        self.student_user = self._create_user('student@test.com', 'student')

    def _create_school(self):
        """Create a test school."""
        from schools.models import School
        return School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )

    def _create_user(self, email, role):
        """Create a test user with the given role."""
        user = User.objects.create_user(
            email=email,
            password='TestPass123!',
            first_name=role.capitalize(),
            last_name='User',
            role=role,
            school=self.school,
        )
        return user


class BaseAPITestCase(APITestCase):
    """Base API test case with authentication helpers."""

    def setUp(self):
        """Set up test data and API client."""
        self.client = APIClient()
        self.school = self._create_school()
        self.admin_user = self._create_user('admin@test.com', 'school_admin')
        self.teacher_user = self._create_user('teacher@test.com', 'teacher')
        self.student_user = self._create_user('student@test.com', 'student')

    def _create_school(self):
        """Create a test school."""
        from schools.models import School
        return School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )

    def _create_user(self, email, role):
        """Create a test user."""
        user = User.objects.create_user(
            email=email,
            password='TestPass123!',
            first_name=role.capitalize(),
            last_name='User',
            role=role,
            school=self.school,
        )
        return user

    def authenticate_as(self, user):
        """Authenticate the API client as the given user."""
        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_X_SCHOOL_ID=str(self.school.id))

    def authenticate_as_admin(self):
        """Authenticate as school admin."""
        self.authenticate_as(self.admin_user)

    def authenticate_as_teacher(self):
        """Authenticate as teacher."""
        self.authenticate_as(self.teacher_user)

    def authenticate_as_student(self):
        """Authenticate as student."""
        self.authenticate_as(self.student_user)
