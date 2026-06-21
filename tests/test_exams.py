"""
Tests for the exams app.
Covers exam creation, attempts, auto-grading, and results.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta

User = get_user_model()


class ExamModelTests(TestCase):
    """Tests for Exam model."""

    def setUp(self):
        from schools.models import School
        from subjects.models import Subject
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
        self.subject = Subject.objects.create(
            school=self.school,
            name='Mathematics',
            code='MATH101',
        )

    def test_create_exam(self):
        """Test creating an exam."""
        from exams.models import Exam
        exam = Exam.objects.create(
            school=self.school,
            subject=self.subject,
            created_by=self.teacher,
            title='Midterm Exam',
            description='Mathematics midterm examination',
            exam_type='midterm',
            duration_minutes=120,
            total_marks=100,
            pass_percentage=50,
            status='draft',
        )
        self.assertEqual(exam.title, 'Midterm Exam')
        self.assertEqual(exam.duration_minutes, 120)
        self.assertEqual(exam.status, 'draft')

    def test_exam_str_representation(self):
        """Test exam string representation."""
        from exams.models import Exam
        exam = Exam.objects.create(
            school=self.school,
            subject=self.subject,
            created_by=self.teacher,
            title='Final Exam',
            exam_type='final',
            duration_minutes=180,
            total_marks=100,
            status='draft',
        )
        self.assertIn('Final Exam', str(exam))

    def test_create_question(self):
        """Test creating a question for an exam."""
        from exams.models import Exam, Question
        exam = Exam.objects.create(
            school=self.school,
            subject=self.subject,
            created_by=self.teacher,
            title='Quiz 1',
            exam_type='quiz',
            duration_minutes=30,
            total_marks=20,
            status='draft',
        )
        question = Question.objects.create(
            exam=exam,
            school=self.school,
            question_type='mcq',
            text='What is 2 + 2?',
            marks=5,
            order=1,
        )
        self.assertEqual(question.exam, exam)
        self.assertEqual(question.marks, 5)

    def test_create_question_options(self):
        """Test creating options for MCQ questions."""
        from exams.models import Exam, Question, QuestionOption
        exam = Exam.objects.create(
            school=self.school,
            subject=self.subject,
            created_by=self.teacher,
            title='Quiz 1',
            exam_type='quiz',
            duration_minutes=30,
            total_marks=20,
            status='draft',
        )
        question = Question.objects.create(
            exam=exam,
            school=self.school,
            question_type='mcq',
            text='What is 2 + 2?',
            marks=5,
            order=1,
        )
        option_a = QuestionOption.objects.create(
            question=question,
            text='3',
            is_correct=False,
            order=1,
        )
        option_b = QuestionOption.objects.create(
            question=question,
            text='4',
            is_correct=True,
            order=2,
        )
        self.assertFalse(option_a.is_correct)
        self.assertTrue(option_b.is_correct)


class ExamAttemptTests(TestCase):
    """Tests for exam attempt and grading."""

    def setUp(self):
        from schools.models import School
        from subjects.models import Subject
        from exams.models import Exam, Question, QuestionOption

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
        self.exam = Exam.objects.create(
            school=self.school,
            subject=self.subject,
            created_by=self.teacher,
            title='Quiz 1',
            exam_type='quiz',
            duration_minutes=30,
            total_marks=10,
            pass_percentage=50,
            status='published',
        )
        self.question = Question.objects.create(
            exam=self.exam,
            school=self.school,
            question_type='mcq',
            text='What is 2 + 2?',
            marks=10,
            order=1,
        )
        self.correct_option = QuestionOption.objects.create(
            question=self.question,
            text='4',
            is_correct=True,
            order=1,
        )
        self.wrong_option = QuestionOption.objects.create(
            question=self.question,
            text='5',
            is_correct=False,
            order=2,
        )

    def test_start_exam_attempt(self):
        """Test starting an exam attempt."""
        from exams.models import ExamAttempt
        attempt = ExamAttempt.objects.create(
            exam=self.exam,
            student=self.student,
            school=self.school,
            status='in_progress',
            started_at=timezone.now(),
        )
        self.assertEqual(attempt.status, 'in_progress')
        self.assertEqual(attempt.student, self.student)

    def test_submit_answer(self):
        """Test submitting an answer."""
        from exams.models import ExamAttempt, Answer
        attempt = ExamAttempt.objects.create(
            exam=self.exam,
            student=self.student,
            school=self.school,
            status='in_progress',
            started_at=timezone.now(),
        )
        answer = Answer.objects.create(
            attempt=attempt,
            question=self.question,
            selected_option=self.correct_option,
        )
        self.assertEqual(answer.selected_option, self.correct_option)

    def test_exam_time_expired(self):
        """Test detecting expired exam time."""
        from exams.models import ExamAttempt
        attempt = ExamAttempt.objects.create(
            exam=self.exam,
            student=self.student,
            school=self.school,
            status='in_progress',
            started_at=timezone.now() - timedelta(minutes=60),  # Started 60 min ago
        )
        # Exam duration is 30 minutes, so it should be expired
        expiry_time = attempt.started_at + timedelta(minutes=self.exam.duration_minutes)
        self.assertLess(expiry_time, timezone.now())


class ExamAPITests(APITestCase):
    """Tests for Exam API endpoints."""

    def setUp(self):
        from schools.models import School
        from subjects.models import Subject

        self.client = APIClient()
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

    def test_list_exams_as_teacher(self):
        """Test listing exams as teacher."""
        from exams.models import Exam
        Exam.objects.create(
            school=self.school,
            subject=self.subject,
            created_by=self.teacher,
            title='Test Exam',
            exam_type='quiz',
            duration_minutes=30,
            total_marks=20,
            status='published',
        )
        self.client.force_authenticate(user=self.teacher)
        self.client.credentials(HTTP_X_SCHOOL_ID=str(self.school.id))
        response = self.client.get('/api/v1/exams/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_exam_as_teacher(self):
        """Test creating an exam as teacher."""
        self.client.force_authenticate(user=self.teacher)
        self.client.credentials(HTTP_X_SCHOOL_ID=str(self.school.id))
        data = {
            'subject': str(self.subject.id),
            'title': 'New Exam',
            'exam_type': 'quiz',
            'duration_minutes': 45,
            'total_marks': 30,
            'status': 'draft',
        }
        response = self.client.post('/api/v1/exams/', data)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])

    def test_student_cannot_create_exam(self):
        """Test that students cannot create exams."""
        self.client.force_authenticate(user=self.student)
        self.client.credentials(HTTP_X_SCHOOL_ID=str(self.school.id))
        data = {
            'subject': str(self.subject.id),
            'title': 'Unauthorized Exam',
            'exam_type': 'quiz',
            'duration_minutes': 30,
            'total_marks': 20,
        }
        response = self.client.post('/api/v1/exams/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
