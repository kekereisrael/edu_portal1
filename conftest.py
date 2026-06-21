"""
conftest.py - Shared pytest fixtures for the educational portal tests.
"""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def school(db):
    """Create a test school."""
    from schools.models import School
    return School.objects.create(
        name='Test School',
        code='TST-001',
        email='school@test.com',
        is_active=True,
    )


@pytest.fixture
def admin_user(db, school):
    """Create a school admin user."""
    return User.objects.create_user(
        email='admin@test.com',
        password='TestPass123!',
        first_name='Admin',
        last_name='User',
        role='school_admin',
        school=school,
    )


@pytest.fixture
def teacher_user(db, school):
    """Create a teacher user."""
    return User.objects.create_user(
        email='teacher@test.com',
        password='TestPass123!',
        first_name='Teacher',
        last_name='User',
        role='teacher',
        school=school,
    )


@pytest.fixture
def student_user(db, school):
    """Create a student user."""
    return User.objects.create_user(
        email='student@test.com',
        password='TestPass123!',
        first_name='Student',
        last_name='User',
        role='student',
        school=school,
    )


@pytest.fixture
def api_client():
    """Create an API test client."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_admin_client(api_client, admin_user, school):
    """Create an authenticated API client for admin."""
    api_client.force_authenticate(user=admin_user)
    api_client.credentials(HTTP_X_SCHOOL_ID=str(school.id))
    return api_client


@pytest.fixture
def authenticated_teacher_client(api_client, teacher_user, school):
    """Create an authenticated API client for teacher."""
    api_client.force_authenticate(user=teacher_user)
    api_client.credentials(HTTP_X_SCHOOL_ID=str(school.id))
    return api_client


@pytest.fixture
def authenticated_student_client(api_client, student_user, school):
    """Create an authenticated API client for student."""
    api_client.force_authenticate(user=student_user)
    api_client.credentials(HTTP_X_SCHOOL_ID=str(school.id))
    return api_client


@pytest.fixture
def subject(db, school):
    """Create a test subject."""
    from subjects.models import Subject
    return Subject.objects.create(
        school=school,
        name='Mathematics',
        code='MATH101',
        description='Introduction to Mathematics',
    )


@pytest.fixture
def exam(db, school, subject, teacher_user):
    """Create a test exam."""
    from exams.models import Exam
    return Exam.objects.create(
        school=school,
        subject=subject,
        created_by=teacher_user,
        title='Test Exam',
        exam_type='quiz',
        duration_minutes=30,
        total_marks=100,
        pass_percentage=50,
        status='published',
    )
