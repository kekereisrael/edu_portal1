"""
Views for the exams app.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import SchoolQuerysetMixin, SchoolCreateMixin
from core.permissions import HasSchoolContext, IsSchoolAdminOrTeacher, IsStudent

from .models import (
    QuestionBank, QuestionTag, Exam, ExamTemplate, ExamGroup,
    Question, QuestionOption, ExamAttempt, Answer, Result,
)
from .serializers import (
    QuestionBankSerializer, QuestionTagSerializer,
    ExamSerializer, ExamCreateSerializer, ExamDetailSerializer,
    ExamTemplateSerializer, ExamGroupSerializer,
    QuestionSerializer, QuestionCreateSerializer, QuestionStudentSerializer,
    ExamAttemptSerializer, ExamAttemptDetailSerializer,
    AnswerSerializer, SubmitAnswerSerializer, GradeAnswerSerializer,
    ResultSerializer, ResultCreateSerializer,
)


# ============ Exams ============

class ExamListCreateView(SchoolQuerysetMixin, generics.ListCreateAPIView):
    """List all exams or create a new one."""

    queryset = Exam.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'term', 'classroom', 'created_by']
    filterset_fields = ['subject', 'term', 'classroom', 'exam_type', 'is_published']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'start_time', 'created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ExamCreateSerializer
        return ExamSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def get_queryset(self):
        qs = super().get_queryset()
        # Students only see published exams
        if hasattr(self.request, 'school_membership'):
            if self.request.school_membership and self.request.school_membership.role == 'student':
                qs = qs.filter(is_published=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, created_by=self.request.user)


class ExamDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an exam."""

    queryset = Exam.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'term', 'classroom', 'created_by']

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ExamDetailSerializer
        return ExamCreateSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


class ExamPublishView(APIView):
    """Publish or unpublish an exam."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, pk):
        exam = get_object_or_404(Exam, id=pk, school=request.school)
        if exam.questions.count() == 0:
            return Response(
                {'detail': 'Cannot publish an exam with no questions.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.is_published = True
        exam.save(update_fields=['is_published', 'updated_at'])
        return Response({'message': 'Exam published successfully.'})

    def delete(self, request, pk):
        exam = get_object_or_404(Exam, id=pk, school=request.school)
        exam.is_published = False
        exam.save(update_fields=['is_published', 'updated_at'])
        return Response({'message': 'Exam unpublished successfully.'})


# ============ Questions ============

class QuestionListCreateView(generics.ListCreateAPIView):
    """List or create questions for an exam."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionCreateSerializer
        return QuestionSerializer

    def get_queryset(self):
        exam_id = self.kwargs.get('exam_id')
        return Question.objects.filter(
            exam_id=exam_id,
            exam__school=self.request.school,
        ).prefetch_related('options', 'tags')

    def perform_create(self, serializer):
        exam = get_object_or_404(
            Exam, id=self.kwargs['exam_id'], school=self.request.school
        )
        serializer.save(exam=exam)


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question."""

    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        return Question.objects.filter(
            exam__school=self.request.school
        ).prefetch_related('options', 'tags')


# ============ Exam Attempts ============

class StartExamView(APIView):
    """Start an exam attempt."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, exam_id):
        exam = get_object_or_404(
            Exam, id=exam_id, school=request.school, is_published=True
        )

        # Check if exam is available
        if not exam.is_available:
            return Response(
                {'detail': 'This exam is not currently available.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check max attempts
        existing_attempts = ExamAttempt.objects.filter(
            exam=exam, student=request.user
        ).count()

        if exam.max_attempts != -1 and existing_attempts >= exam.max_attempts:
            return Response(
                {'detail': f'Maximum attempts ({exam.max_attempts}) reached.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for in-progress attempt
        in_progress = ExamAttempt.objects.filter(
            exam=exam, student=request.user, status=ExamAttempt.Status.IN_PROGRESS
        ).first()

        if in_progress:
            # Check if timed out
            if in_progress.is_timed_out:
                in_progress.timeout()
            else:
                # Return existing attempt
                questions = exam.questions.all().prefetch_related('options')
                return Response({
                    'attempt': ExamAttemptSerializer(in_progress).data,
                    'questions': QuestionStudentSerializer(questions, many=True).data,
                })

        # Create new attempt
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or \
                     request.META.get('REMOTE_ADDR', '127.0.0.1')

        attempt = ExamAttempt.objects.create(
            exam=exam,
            student=request.user,
            school=request.school,
            attempt_number=existing_attempts + 1,
            ip_address=ip_address,
        )

        # Get questions (shuffled if configured)
        questions = exam.questions.all().prefetch_related('options')
        if exam.shuffle_questions:
            questions = questions.order_by('?')

        return Response(
            {
                'attempt': ExamAttemptSerializer(attempt).data,
                'questions': QuestionStudentSerializer(questions, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


class SaveAnswerView(APIView):
    """Save an answer during an exam (auto-save)."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            ExamAttempt,
            id=attempt_id,
            student=request.user,
            status=ExamAttempt.Status.IN_PROGRESS,
        )

        # Check timeout
        if attempt.is_timed_out:
            attempt.timeout()
            return Response(
                {'detail': 'Exam time has expired. Your answers have been submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question = get_object_or_404(
            Question, id=serializer.validated_data['question_id'], exam=attempt.exam
        )

        selected_option_id = serializer.validated_data.get('selected_option_id')
        text_answer = serializer.validated_data.get('text_answer')

        selected_option = None
        if selected_option_id:
            selected_option = get_object_or_404(
                QuestionOption, id=selected_option_id, question=question
            )

        # Create or update answer
        answer, created = Answer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                'selected_option': selected_option,
                'text_answer': text_answer or '',
            },
        )

        return Response(
            AnswerSerializer(answer).data,
            status=status.HTTP_200_OK,
        )


class SubmitExamView(APIView):
    """Submit an exam attempt for grading."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            ExamAttempt,
            id=attempt_id,
            student=request.user,
            status=ExamAttempt.Status.IN_PROGRESS,
        )

        attempt.submit()

        response_data = {
            'message': 'Exam submitted successfully.',
            'attempt': ExamAttemptSerializer(attempt).data,
        }

        # Include results if configured to show immediately
        if attempt.exam.show_results_immediately:
            response_data['score'] = float(attempt.score) if attempt.score else 0
            response_data['percentage'] = float(attempt.percentage) if attempt.percentage else 0
            response_data['passed'] = attempt.passed

        return Response(response_data)


class ExamAttemptListView(generics.ListAPIView):
    """List exam attempts (teacher: all for an exam, student: own attempts)."""

    serializer_class = ExamAttemptSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['status', 'student']

    def get_queryset(self):
        exam_id = self.kwargs.get('exam_id')
        qs = ExamAttempt.objects.filter(
            exam_id=exam_id, school=self.request.school
        ).select_related('exam', 'student')

        # Students can only see their own attempts
        if hasattr(self.request, 'school_membership'):
            if self.request.school_membership and self.request.school_membership.role == 'student':
                qs = qs.filter(student=self.request.user)

        return qs


class ExamAttemptDetailView(generics.RetrieveAPIView):
    """Get detailed attempt with answers."""

    serializer_class = ExamAttemptDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        qs = ExamAttempt.objects.filter(
            school=self.request.school
        ).select_related('exam', 'student').prefetch_related('answers__question')

        # Students can only see their own attempts
        if hasattr(self.request, 'school_membership'):
            if self.request.school_membership and self.request.school_membership.role == 'student':
                qs = qs.filter(student=self.request.user)

        return qs


class GradeAnswerView(APIView):
    """Manually grade an answer (for essays, short answers)."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, answer_id):
        answer = get_object_or_404(
            Answer,
            id=answer_id,
            attempt__school=request.school,
        )

        serializer = GradeAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        answer.manual_grade(
            marks=serializer.validated_data['marks'],
            graded_by=request.user,
            feedback=serializer.validated_data.get('feedback', ''),
        )

        # Recalculate attempt score
        attempt = answer.attempt
        total_score = attempt.answers.filter(
            marks_awarded__isnull=False
        ).aggregate(total=models.Sum('marks_awarded'))['total'] or 0

        attempt.score = total_score
        if attempt.exam.total_marks > 0:
            attempt.percentage = (total_score / attempt.exam.total_marks) * 100

        # Check if all answers are graded
        ungraded = attempt.answers.filter(marks_awarded__isnull=True).count()
        if ungraded == 0:
            attempt.status = ExamAttempt.Status.GRADED

        attempt.save(update_fields=['score', 'percentage', 'status', 'updated_at'])

        return Response({
            'message': 'Answer graded successfully.',
            'answer': AnswerSerializer(answer).data,
        })


# ============ Question Banks ============

class QuestionBankListCreateView(SchoolQuerysetMixin, SchoolCreateMixin, generics.ListCreateAPIView):
    """List or create question banks."""

    queryset = QuestionBank.objects.all()
    serializer_class = QuestionBankSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    select_related_fields = ['subject', 'created_by']
    filterset_fields = ['subject']

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, created_by=self.request.user)


class QuestionBankDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question bank."""

    queryset = QuestionBank.objects.all()
    serializer_class = QuestionBankSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]


class QuestionBankQuestionsView(generics.ListCreateAPIView):
    """List or add questions to a question bank."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionCreateSerializer
        return QuestionSerializer

    def get_queryset(self):
        bank_id = self.kwargs.get('bank_id')
        return Question.objects.filter(
            question_bank_id=bank_id,
            question_bank__school=self.request.school,
        ).prefetch_related('options', 'tags')

    def perform_create(self, serializer):
        bank = get_object_or_404(
            QuestionBank, id=self.kwargs['bank_id'], school=self.request.school
        )
        serializer.save(question_bank=bank)


# ============ Question Tags ============

class QuestionTagListCreateView(SchoolQuerysetMixin, SchoolCreateMixin, generics.ListCreateAPIView):
    """List or create question tags."""

    queryset = QuestionTag.objects.all()
    serializer_class = QuestionTagSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    filterset_fields = ['tag_type']


# ============ Exam Templates ============

class ExamTemplateListCreateView(SchoolQuerysetMixin, SchoolCreateMixin, generics.ListCreateAPIView):
    """List or create exam templates."""

    queryset = ExamTemplate.objects.all()
    serializer_class = ExamTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, created_by=self.request.user)


class ExamTemplateDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an exam template."""

    queryset = ExamTemplate.objects.all()
    serializer_class = ExamTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]


# ============ Exam Groups ============

class ExamGroupListCreateView(SchoolQuerysetMixin, SchoolCreateMixin, generics.ListCreateAPIView):
    """List or create exam groups."""

    queryset = ExamGroup.objects.all()
    serializer_class = ExamGroupSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    filterset_fields = ['term']


# ============ Results ============

class ResultListCreateView(SchoolQuerysetMixin, generics.ListCreateAPIView):
    """List or create results."""

    queryset = Result.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['student', 'subject', 'term']
    filterset_fields = ['subject', 'term', 'student', 'is_published', 'grade']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ResultCreateSerializer
        return ResultSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def get_queryset(self):
        qs = super().get_queryset()
        # Students only see published results for themselves
        if hasattr(self.request, 'school_membership'):
            if self.request.school_membership and self.request.school_membership.role == 'student':
                qs = qs.filter(student=self.request.user, is_published=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class ResultDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a result."""

    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    select_related_fields = ['student', 'subject', 'term']


class PublishResultsView(APIView):
    """Bulk publish results for a term/subject."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request):
        term_id = request.data.get('term_id')
        subject_id = request.data.get('subject_id')

        if not term_id:
            return Response(
                {'detail': 'term_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = {'school': request.school, 'term_id': term_id, 'is_published': False}
        if subject_id:
            filters['subject_id'] = subject_id

        count = Result.objects.filter(**filters).update(
            is_published=True,
            published_at=timezone.now(),
            published_by=request.user,
        )

        return Response({
            'message': f'{count} results published successfully.',
            'published_count': count,
        })


class MyResultsView(generics.ListAPIView):
    """Get current student's results."""

    serializer_class = ResultSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['subject', 'term']

    def get_queryset(self):
        return Result.objects.filter(
            student=self.request.user,
            school=self.request.school,
            is_published=True,
        ).select_related('subject', 'term')
