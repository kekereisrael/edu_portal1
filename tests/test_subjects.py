"""
Tests for the subjects app.
Covers subject CRUD, enrollment, and timetable management.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()


class SubjectModelTests(TestCase):
    """Tests for Subject model."""

    def setUp(self):
        from schools.models import School
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )
        self.teacher = User.objects.create_user(
            email='teacher@test.com',
            password='TestPass123!',
            first_name='Teacher',
            last_name='User',
            role='teacher',
            school=self.school,
        )

    def test_create_subject(self):
        """Test creating a subject."""
        from subjects.models import Subject
        subject = Subject.objects.create(
            school=self.school,
            name='Mathematics',
            code='MATH101',
            description='Introduction to Mathematics',
        )
        self.assertEqual(subject.name, 'Mathematics')
        self.assertEqual(subject.code, 'MATH101')
        self.assertEqual(subject.school, self.school)

    def test_subject_str_representation(self):
        """Test subject string representation."""
        from subjects.models import Subject
        subject = Subject.objects.create(
            school=self.school,
            name='Physics',
            code='PHY101',
        )
        self.assertIn('Physics', str(subject))

    def test_create_topic(self):
        """Test creating a topic under a subject."""
        from subjects.models import Subject, Topic
        subject = Subject.objects.create(
            school=self.school,
            name='Mathematics',
            code='MATH101',
        )
        topic = Topic.objects.create(
            subject=subject,
            school=self.school,
            name='Algebra',
            order=1,
        )
        self.assertEqual(topic.subject, subject)
        self.assertEqual(topic.name, 'Algebra')


class EnrollmentModelTests(TestCase):
    """Tests for Enrollment model."""

    def setUp(self):
        from schools.models import School
        from subjects.models import Subject
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )
        self.student = User.objects.create_user(
            email='student@test.com',
            password='TestPass123!',
            first_name='Student',
            last_name='User',
            role='student',
            school=self.school,
        )
        self.subject = Subject.objects.create(
            school=self.school,
            name='Mathematics',
            code='MATH101',
        )

    def test_enroll_student(self):
        """Test enrolling a student in a subject."""
        from subjects.models import Enrollment
        enrollment = Enrollment.objects.create(
            student=self.student,
            subject=self.subject,
            school=self.school,
            status='active',
        )
        self.assertEqual(enrollment.student, self.student)
        self.assertEqual(enrollment.subject, self.subject)
        self.assertEqual(enrollment.status, 'active')

    def test_unique_enrollment(self):
        """Test that a student can't be enrolled twice in the same subject."""
        from subjects.models import Enrollment
        from django.db import IntegrityError
        Enrollment.objects.create(
            student=self.student,
            subject=self.subject,
            school=self.school,
            status='active',
        )
        with self.assertRaises(IntegrityError):
            Enrollment.objects.create(
                student=self.student,
                subject=self.subject,
                school=self.school,
                status='active',
            )


class SubjectAPITests(APITestCase):
    """Tests for Subject API endpoints."""

    def setUp(self):
        from schools.models import School
        self.client = APIClient()
        self.school = School.objects.create(
            name='Test School',
            code='TST-001',
            email='school@test.com',
            is_active=True,
        )
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='TestPass123!',
            first_name='Admin',
            last_name='User',
            role='school_admin',
            school=self.school,
        )
        self.teacher = User.objects.create_user(
            email='teacher@test.com',
            password='TestPass123!',
            first_name='Teacher',
            last_name='User',
            role='teacher',
            school=self.school,
        )

    def test_list_subjects_authenticated(self):
        """Test listing subjects as authenticated user."""
        from subjects.models import Subject
        Subject.objects.create(
            school=self.school,
            name='Mathematics',
            code='MATH101',
        )
        self.client.force_authenticate(user=self.admin)
        self.client.credentials(HTTP_X_SCHOOL_ID=str(self.school.id))
        response = self.client.get('/api/v1/subjects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_subject_as_admin(self):
        """Test creating a subject as school admin."""
        self.client.force_authenticate(user=self.admin)
        self.client.credentials(HTTP_X_SCHOOL_ID=str(self.school.id))
        data = {
            'name': 'Chemistry',
            'code': 'CHEM101',
            'description': 'Introduction to Chemistry',
        }
        response = self.client.post('/api/v1/subjects/', data)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_create_subject_as_student_forbidden(self):
        """Test that students cannot create subjects."""
        student = User.objects.create_user(
            email='student@test.com',
            password='TestPass123!',
            first_name='Student',
            last_name='User',
            role='student',
            school=self.school,
        )
        self.client.force_authenticate(user=student)
        self.client.credentials(HTTP_X_SCHOOL_ID=str(self.school.id))
        data = {
            'name': 'Chemistry',
            'code': 'CHEM101',
        }
        response = self.client.post('/api/v1/subjects/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
