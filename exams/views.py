"""
Views for the exams app.
Phase 6C additions: Practice Mode, Mock Exams, Weak Topic Detection, Recommendations.
"""

import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import SchoolQuerysetMixin, SchoolCreateMixin
from core.permissions import HasSchoolContext, IsSchoolAdminOrTeacher, IsStudent

from .models import Exam, Question, ExamAttempt, ExamAnswer, ExamResult
from .serializers import (
    ExamSerializer, ExamCreateSerializer, ExamDetailSerializer,
    QuestionSerializer, QuestionStudentSerializer,
    ExamAttemptSerializer, ExamAttemptDetailSerializer,
    ExamAnswerSerializer, BulkSubmitSerializer,
    ExamResultSerializer, StartExamSerializer,
)

logger = logging.getLogger(__name__)


# ============ Exams ============

class ExamListCreateView(SchoolQuerysetMixin, generics.ListCreateAPIView):
    """List all exams or create a new one."""

    queryset = Exam.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'term', 'created_by']
    filterset_fields = ['subject', 'term', 'exam_type', 'status']
    search_fields = ['title']
    ordering_fields = ['title', 'created_at', 'start_date']

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
        if hasattr(self.request, 'school_membership') and self.request.school_membership:
            if self.request.school_membership.role == 'student':
                qs = qs.filter(status=Exam.Status.PUBLISHED)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, created_by=self.request.user)


class ExamDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an exam."""

    queryset = Exam.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'term', 'created_by']

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ExamDetailSerializer
        return ExamCreateSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


class ExamPublishView(APIView):
    """Publish an exam."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, pk):
        exam = get_object_or_404(Exam, id=pk, school=request.school)
        if exam.questions.filter(is_active=True).count() == 0:
            return Response(
                {'detail': 'Cannot publish an exam with no questions.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.publish()
        return Response({'message': 'Exam published successfully.', 'status': exam.status})

    def delete(self, request, pk):
        exam = get_object_or_404(Exam, id=pk, school=request.school)
        exam.status = Exam.Status.DRAFT
        exam.save(update_fields=['status', 'updated_at'])
        return Response({'message': 'Exam unpublished (set to draft).'})


# ============ Questions ============

class QuestionListCreateView(generics.ListCreateAPIView):
    """List or create questions for an exam."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_serializer_class(self):
        return QuestionSerializer

    def get_queryset(self):
        exam_id = self.kwargs.get('exam_id')
        return Question.objects.filter(
            exam_id=exam_id,
            exam__school=self.request.school,
        ).select_related('topic').order_by('order', 'created_at')

    def perform_create(self, serializer):
        exam = get_object_or_404(
            Exam, id=self.kwargs['exam_id'], school=self.request.school
        )
        question = serializer.save(exam=exam)
        # Recalculate total marks
        exam.recalculate_total_marks()
        return question


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question."""

    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        return Question.objects.filter(exam__school=self.request.school)

    def perform_update(self, serializer):
        question = serializer.save()
        question.exam.recalculate_total_marks()

    def perform_destroy(self, instance):
        exam = instance.exam
        instance.delete()
        exam.recalculate_total_marks()


# ============ Exam Attempts (CBT) ============

class StartExamView(APIView):
    """Start an exam attempt."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, pk):
        exam = get_object_or_404(
            Exam, id=pk, school=request.school
        )

        # Validate exam availability
        if not exam.is_available:
            return Response(
                {'detail': 'This exam is not currently available.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check max attempts
        if exam.max_attempts > 0:
            attempt_count = ExamAttempt.objects.filter(
                exam=exam, student=request.user
            ).exclude(status=ExamAttempt.Status.ABANDONED).count()
            if attempt_count >= exam.max_attempts:
                return Response(
                    {'detail': f'You have reached the maximum number of attempts ({exam.max_attempts}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check for existing in-progress attempt
        existing = ExamAttempt.objects.filter(
            exam=exam, student=request.user, status=ExamAttempt.Status.IN_PROGRESS
        ).first()
        if existing:
            # Return existing attempt
            serializer = ExamAttemptSerializer(existing)
            questions = exam.questions.filter(is_active=True).order_by('order')
            if exam.shuffle_questions:
                questions = questions.order_by('?')
            return Response({
                'attempt': serializer.data,
                'questions': QuestionStudentSerializer(questions, many=True).data,
                'resumed': True,
            })

        # Create new attempt
        attempt_number = ExamAttempt.objects.filter(
            exam=exam, student=request.user
        ).count() + 1

        attempt = ExamAttempt.objects.create(
            exam=exam,
            student=request.user,
            attempt_number=attempt_number,
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        # Get questions
        questions = exam.questions.filter(is_active=True).order_by('order')
        if exam.shuffle_questions:
            questions = questions.order_by('?')

        # Pre-create answer slots
        ExamAnswer.objects.bulk_create([
            ExamAnswer(attempt=attempt, question=q)
            for q in questions
        ])

        serializer = ExamAttemptSerializer(attempt)
        return Response({
            'attempt': serializer.data,
            'questions': QuestionStudentSerializer(questions, many=True).data,
            'resumed': False,
        }, status=status.HTTP_201_CREATED)


class SaveAnswerView(APIView):
    """Save/update a single answer during exam."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            ExamAttempt,
            id=attempt_id,
            student=request.user,
            status=ExamAttempt.Status.IN_PROGRESS,
        )

        # Check time
        if attempt.is_timed_out:
            attempt.submit(auto=True)
            return Response(
                {'detail': 'Time expired. Exam auto-submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question_id = request.data.get('question_id')
        selected_answer = request.data.get('selected_answer', '')
        is_marked = request.data.get('is_marked_for_review', False)
        time_spent = request.data.get('time_spent_seconds', 0)

        question = get_object_or_404(
            Question, id=question_id, exam=attempt.exam, is_active=True
        )

        answer, created = ExamAnswer.objects.get_or_create(
            attempt=attempt, question=question,
            defaults={'selected_answer': selected_answer}
        )
        if not created:
            answer.selected_answer = selected_answer
            answer.is_marked_for_review = is_marked
            answer.time_spent_seconds = time_spent
            answer.answered_at = timezone.now()
            answer.save()

        return Response({'saved': True, 'question_id': str(question_id)})


class SubmitExamView(APIView):
    """Submit an exam attempt."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            ExamAttempt,
            id=attempt_id,
            student=request.user,
        )

        if attempt.status not in (ExamAttempt.Status.IN_PROGRESS,):
            return Response(
                {'detail': 'This attempt has already been submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save any final answers from bulk payload
        answers_data = request.data.get('answers', [])
        for ans in answers_data:
            try:
                question = Question.objects.get(id=ans['question_id'], exam=attempt.exam)
                ExamAnswer.objects.update_or_create(
                    attempt=attempt, question=question,
                    defaults={
                        'selected_answer': ans.get('selected_answer', ''),
                        'is_marked_for_review': ans.get('is_marked_for_review', False),
                        'time_spent_seconds': ans.get('time_spent_seconds', 0),
                        'answered_at': timezone.now(),
                    }
                )
            except Question.DoesNotExist:
                pass

        # Submit and grade
        attempt.submit(auto=False)

        # Create ExamResult record
        result, _ = ExamResult.objects.get_or_create(
            attempt=attempt,
            defaults={
                'student': attempt.student,
                'exam': attempt.exam,
                'score': attempt.score or 0,
                'percentage': attempt.percentage or 0,
                'passed': attempt.passed or False,
            }
        )

        response_data = ExamAttemptSerializer(attempt).data
        if attempt.exam.show_result_immediately:
            response_data['result'] = ExamResultSerializer(result).data

        return Response(response_data)


class MyAttemptsView(generics.ListAPIView):
    """List current user's exam attempts."""

    serializer_class = ExamAttemptSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['exam', 'status']

    def get_queryset(self):
        return ExamAttempt.objects.filter(
            student=self.request.user,
            exam__school=self.request.school,
        ).select_related('exam', 'exam__subject').order_by('-started_at')


class AttemptDetailView(generics.RetrieveAPIView):
    """Get details of a specific attempt (with answers if allowed)."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_serializer_class(self):
        return ExamAttemptDetailSerializer

    def get_queryset(self):
        return ExamAttempt.objects.filter(
            student=self.request.user,
            exam__school=self.request.school,
        )


class ExamAttemptsListView(generics.ListAPIView):
    """List all attempts for an exam (teacher/admin view)."""

    serializer_class = ExamAttemptSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    filterset_fields = ['status', 'passed']

    def get_queryset(self):
        exam_id = self.kwargs.get('exam_id')
        return ExamAttempt.objects.filter(
            exam_id=exam_id,
            exam__school=self.request.school,
        ).select_related('student', 'exam').order_by('-started_at')


# ============ Results ============

class ExamResultListView(generics.ListAPIView):
    """List results for an exam."""

    serializer_class = ExamResultSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    filterset_fields = ['passed', 'grade']

    def get_queryset(self):
        exam_id = self.kwargs.get('exam_id')
        return ExamResult.objects.filter(
            exam_id=exam_id,
            exam__school=self.request.school,
        ).select_related('student', 'exam').order_by('-percentage')


class MyResultsView(generics.ListAPIView):
    """Get current student's results."""

    serializer_class = ExamResultSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['exam__subject', 'passed']

    def get_queryset(self):
        return ExamResult.objects.filter(
            student=self.request.user,
            exam__school=self.request.school,
        ).select_related('exam', 'exam__subject').order_by('-created_at')


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 6B — Question Bank Views
# ═════════════════════════════════════════════════════════════════════════════

from .models import (
    ExamCategory, QuestionCategory, QuestionTag,
    QuestionBank, BankQuestion, ExamBankQuestion,
)
from .serializers import (
    ExamCategorySerializer,
    QuestionCategorySerializer, QuestionTagSerializer,
    QuestionBankSerializer, QuestionBankCreateSerializer,
    BankQuestionSerializer, BankQuestionCreateSerializer,
    ExamBankQuestionSerializer,
    QuestionImportSerializer, QuestionBulkJSONSerializer,
    GenerateExamFromBankSerializer,
)
from core.services.question_import_service import (
    import_from_csv, import_from_excel, import_from_json,
)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Exam Categories
# ─────────────────────────────────────────────────────────────────────────────

class ExamCategoryListView(generics.ListAPIView):
    """
    GET /bank/exam-categories/
    List all exam categories (WAEC, NECO, JAMB, etc.).
    Public categories are visible to all; school-specific ones are filtered.
    """

    serializer_class = ExamCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['is_public', 'is_active']
    search_fields = ['name', 'code']

    def get_queryset(self):
        return ExamCategory.objects.filter(is_active=True).order_by('name')


# ─────────────────────────────────────────────────────────────────────────────
# Question Categories & Tags
# ─────────────────────────────────────────────────────────────────────────────

class QuestionCategoryListCreateView(generics.ListCreateAPIView):
    """List or create question categories for the current school."""

    serializer_class = QuestionCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return QuestionCategory.objects.filter(school=self.request.school)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class QuestionCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question category."""

    serializer_class = QuestionCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        return QuestionCategory.objects.filter(school=self.request.school)


class QuestionTagListCreateView(generics.ListCreateAPIView):
    """List or create question tags for the current school."""

    serializer_class = QuestionTagSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    search_fields = ['name']

    def get_queryset(self):
        return QuestionTag.objects.filter(school=self.request.school)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class QuestionTagDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question tag."""

    serializer_class = QuestionTagSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        return QuestionTag.objects.filter(school=self.request.school)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Question Banks
# ─────────────────────────────────────────────────────────────────────────────

class QuestionBankListCreateView(generics.ListCreateAPIView):
    """
    GET  /bank/                  – List all question banks for the school.
    POST /bank/                  – Create a new question bank.
    Supports ?subject=, ?exam_category=, ?class_level=, ?is_shared= filters.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['subject', 'exam_category', 'class_level', 'is_active', 'is_shared']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionBankCreateSerializer
        return QuestionBankSerializer

    def get_queryset(self):
        return QuestionBank.objects.filter(
            school=self.request.school
        ).select_related('subject', 'exam_category', 'class_level', 'created_by')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, created_by=self.request.user)


class QuestionBankDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a question bank."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return QuestionBankCreateSerializer
        return QuestionBankSerializer

    def get_queryset(self):
        return QuestionBank.objects.filter(school=self.request.school)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 + 4 — Bank Questions (with search & filter)
# ─────────────────────────────────────────────────────────────────────────────

class BankQuestionListCreateView(generics.ListCreateAPIView):
    """
    GET  /bank/<bank_id>/questions/   – List questions in a bank.
    POST /bank/<bank_id>/questions/   – Add a question to the bank.

    TASK 4 filters: ?difficulty=, ?question_type=, ?topic=, ?exam_category=,
                    ?exam_year=, ?tags=, ?search=
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['difficulty', 'question_type', 'topic', 'exam_category', 'exam_year', 'is_active']
    search_fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'explanation']
    ordering_fields = ['difficulty', 'marks', 'created_at', 'times_used']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BankQuestionCreateSerializer
        return BankQuestionSerializer

    def get_bank(self):
        return get_object_or_404(
            QuestionBank,
            pk=self.kwargs['bank_id'],
            school=self.request.school,
        )

    def get_queryset(self):
        bank = self.get_bank()
        qs = BankQuestion.objects.filter(bank=bank).select_related(
            'topic', 'category', 'exam_category'
        ).prefetch_related('tags')

        # Extra filters
        tags = self.request.query_params.getlist('tags')
        if tags:
            qs = qs.filter(tags__name__in=tags).distinct()

        return qs

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        bank = self.get_bank()
        serializer.save(bank=bank)


class BankQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a single bank question."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return BankQuestionCreateSerializer
        return BankQuestionSerializer

    def get_queryset(self):
        return BankQuestion.objects.filter(
            bank__school=self.request.school
        ).select_related('topic', 'category', 'exam_category').prefetch_related('tags')


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — Question Import (CSV / Excel / JSON)
# ─────────────────────────────────────────────────────────────────────────────

class QuestionImportView(APIView):
    """
    POST /bank/<bank_id>/import/
    Import questions from a CSV or Excel file.
    Multipart form: { file, format (csv|excel), import_batch }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, bank_id):
        bank = get_object_or_404(QuestionBank, pk=bank_id, school=request.school)
        serializer = QuestionImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = serializer.validated_data['file']
        fmt = serializer.validated_data['format']
        batch = serializer.validated_data.get('import_batch') or None

        if fmt == 'csv':
            result = import_from_csv(file_obj, bank, import_batch=batch)
        else:
            result = import_from_excel(file_obj, bank, import_batch=batch)

        http_status = (
            status.HTTP_201_CREATED if result['created'] > 0
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=http_status)


class QuestionBulkJSONImportView(APIView):
    """
    POST /bank/<bank_id>/import/json/
    Import questions from a JSON body.
    Body: { "questions": [...], "import_batch": "optional-label" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, bank_id):
        bank = get_object_or_404(QuestionBank, pk=bank_id, school=request.school)
        serializer = QuestionBulkJSONSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = import_from_json(
            serializer.validated_data['questions'],
            bank,
            import_batch=serializer.validated_data.get('import_batch') or None,
        )

        http_status = (
            status.HTTP_201_CREATED if result['created'] > 0
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=http_status)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 5 — Generate Exam from Question Bank
# ─────────────────────────────────────────────────────────────────────────────

class GenerateExamFromBankView(APIView):
    """
    POST /bank/generate-exam/
    Auto-generate an Exam by pulling questions from a QuestionBank.

    The teacher specifies:
      - bank_id, exam_title, num_questions
      - Optional filters: difficulty, topic, exam_category_code, question_type
      - Exam settings: duration_minutes, passing_score, exam_type, term_id

    The system:
      1. Queries BankQuestion with the given filters
      2. Randomly (or sequentially) selects num_questions
      3. Creates an Exam record
      4. Creates ExamBankQuestion snapshots (linked to the Exam)
      5. Returns the new Exam
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request):
        from schools.models import Term, ClassLevel
        from subjects.models import Topic, Subject

        serializer = GenerateExamFromBankSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Resolve bank
        bank = get_object_or_404(QuestionBank, pk=data['bank_id'], school=request.school)

        # Build question queryset with filters
        qs = BankQuestion.objects.filter(bank=bank, is_active=True)

        if data.get('difficulty'):
            qs = qs.filter(difficulty=data['difficulty'])

        if data.get('topic_id'):
            qs = qs.filter(topic_id=data['topic_id'])

        if data.get('exam_category_code'):
            qs = qs.filter(exam_category__code=data['exam_category_code'])

        if data.get('question_type'):
            qs = qs.filter(question_type=data['question_type'])

        if data.get('class_level_id'):
            qs = qs.filter(bank__class_level_id=data['class_level_id'])

        total_available = qs.count()
        num_questions = min(data['num_questions'], total_available)

        if num_questions == 0:
            return Response(
                {'detail': 'No questions match the given filters. Please adjust your criteria.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Select questions
        if data.get('randomise', True):
            selected = list(qs.order_by('?')[:num_questions])
        else:
            selected = list(qs.order_by('created_at')[:num_questions])

        # Resolve optional term
        term = None
        if data.get('term_id'):
            term = Term.objects.filter(
                id=data['term_id'], academic_year__school=request.school
            ).first()

        # Create the Exam
        exam = Exam.objects.create(
            school=request.school,
            title=data['exam_title'],
            subject=bank.subject,
            created_by=request.user,
            exam_type=data.get('exam_type', Exam.ExamType.CBT),
            status=Exam.Status.DRAFT,
            duration_minutes=data.get('duration_minutes', 60),
            passing_score=data.get('passing_score', 50.0),
            term=term,
        )

        # Create ExamBankQuestion snapshots
        total_marks = 0
        for order, bq in enumerate(selected, start=1):
            marks = data.get('marks_per_question') or bq.marks
            ExamBankQuestion.objects.create(
                exam=exam,
                bank_question=bq,
                order=order,
                marks=marks,
            )
            total_marks += marks

        # Update total_marks on the exam
        exam.total_marks = total_marks
        exam.save(update_fields=['total_marks', 'updated_at'])

        return Response(
            {
                'exam': ExamSerializer(exam).data,
                'questions_added': len(selected),
                'total_available': total_available,
                'total_marks': total_marks,
            },
            status=status.HTTP_201_CREATED,
        )


class ExamBankQuestionListView(generics.ListAPIView):
    """
    GET /exams/<exam_id>/bank-questions/
    List all bank-question snapshots linked to an exam.
    """

    serializer_class = ExamBankQuestionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        exam_id = self.kwargs['exam_id']
        return ExamBankQuestion.objects.filter(
            exam_id=exam_id,
            exam__school=self.request.school,
        ).select_related('bank_question').order_by('order')


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 6C — Practice Mode, Mock Exams & Student Improvement
# ═════════════════════════════════════════════════════════════════════════════

from .models import (
    PracticeSession, PracticeAnswer,
    MockExamSession, MockExamAnswer,
    TopicPerformance,
)
from .serializers import (
    StartPracticeSerializer, PracticeAnswerSubmitSerializer,
    PracticeAnswerSerializer, PracticeSessionSerializer, PracticeSessionDetailSerializer,
    StartMockExamSerializer, MockAnswerSubmitSerializer, BulkMockSubmitSerializer,
    MockExamAnswerSerializer, MockExamSessionSerializer, MockExamSessionDetailSerializer,
    TopicPerformanceSerializer, RecommendationQuerySerializer,
)
from core.services.recommendation_service import get_recommendations, get_subject_breakdown


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Practice Mode
# ─────────────────────────────────────────────────────────────────────────────

class StartPracticeView(APIView):
    """
    POST /practice/start/
    Start a new practice session from a question bank.
    Returns the session + the selected questions (with correct answers hidden).
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request):
        serializer = StartPracticeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        bank = get_object_or_404(QuestionBank, pk=data['bank_id'], school=request.school)

        # Build question queryset with optional filters
        qs = BankQuestion.objects.filter(bank=bank, is_active=True)
        if data.get('topic_id'):
            qs = qs.filter(topic_id=data['topic_id'])
        if data.get('difficulty'):
            qs = qs.filter(difficulty=data['difficulty'])
        if data.get('question_type'):
            qs = qs.filter(question_type=data['question_type'])

        num = min(data['num_questions'], qs.count())
        if num == 0:
            return Response(
                {'detail': 'No questions match the given filters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selected = list(qs.order_by('?')[:num])

        # Resolve optional topic FK
        topic = None
        if data.get('topic_id'):
            from subjects.models import Topic
            topic = Topic.objects.filter(id=data['topic_id']).first()

        session = PracticeSession.objects.create(
            student=request.user,
            bank=bank,
            topic=topic,
            difficulty=data.get('difficulty') or None,
            question_type=data.get('question_type') or None,
            num_questions=num,
        )

        # Return questions without correct answers
        questions_data = [
            {
                'id': str(bq.id),
                'question_text': bq.question_text,
                'question_type': bq.question_type,
                'option_a': bq.option_a,
                'option_b': bq.option_b,
                'option_c': bq.option_c,
                'option_d': bq.option_d,
                'difficulty': bq.difficulty,
                'marks': bq.marks,
                'topic_id': str(bq.topic_id) if bq.topic_id else None,
            }
            for bq in selected
        ]

        return Response(
            {
                'session': PracticeSessionSerializer(session).data,
                'questions': questions_data,
                'total_questions': num,
            },
            status=status.HTTP_201_CREATED,
        )


class SubmitPracticeAnswerView(APIView):
    """
    POST /practice/<session_id>/answer/
    Submit a single answer and receive instant feedback.
    Returns: is_correct, correct_answer, explanation.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, session_id):
        session = get_object_or_404(
            PracticeSession,
            id=session_id,
            student=request.user,
            status=PracticeSession.Status.ACTIVE,
        )

        serializer = PracticeAnswerSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        bq = get_object_or_404(
            BankQuestion,
            id=data['bank_question_id'],
            bank=session.bank,
            is_active=True,
        )

        # Create answer (auto-graded in model.save())
        answer = PracticeAnswer.objects.create(
            session=session,
            bank_question=bq,
            selected_answer=data.get('selected_answer', ''),
            time_spent_seconds=data.get('time_spent_seconds', 0),
        )

        # Update TopicPerformance if question has a topic
        if bq.topic_id:
            TopicPerformance.record_answer(
                student=request.user,
                topic=bq.topic,
                subject=bq.bank.subject,
                school=request.school,
                is_correct=bool(answer.is_correct),
            )

        return Response(
            PracticeAnswerSerializer(answer).data,
            status=status.HTTP_201_CREATED,
        )


class CompletePracticeView(APIView):
    """
    POST /practice/<session_id>/complete/
    Mark a practice session as completed.
    Returns the full session summary with all answers.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, session_id):
        session = get_object_or_404(
            PracticeSession,
            id=session_id,
            student=request.user,
        )
        if session.status == PracticeSession.Status.ACTIVE:
            session.complete()
        return Response(PracticeSessionDetailSerializer(session).data)


class MyPracticeSessionsView(generics.ListAPIView):
    """
    GET /practice/my/
    List the current student's practice sessions.
    """

    serializer_class = PracticeSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['status', 'bank']

    def get_queryset(self):
        return PracticeSession.objects.filter(
            student=self.request.user,
            bank__school=self.request.school,
        ).select_related('bank', 'bank__subject', 'topic').order_by('-created_at')


class PracticeSessionDetailView(generics.RetrieveAPIView):
    """
    GET /practice/<session_id>/
    Get a practice session with all answers (review mode).
    """

    serializer_class = PracticeSessionDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return PracticeSession.objects.filter(
            student=self.request.user,
            bank__school=self.request.school,
        ).prefetch_related('practice_answers__bank_question')


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Mock Exam Mode
# ─────────────────────────────────────────────────────────────────────────────

class StartMockExamView(APIView):
    """
    POST /mock/start/
    Start a new timed mock exam session from a question bank.
    Returns the session + questions (correct answers hidden).
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request):
        serializer = StartMockExamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        bank = get_object_or_404(QuestionBank, pk=data['bank_id'], school=request.school)

        # Build question queryset
        qs = BankQuestion.objects.filter(bank=bank, is_active=True)
        if data.get('topic_id'):
            qs = qs.filter(topic_id=data['topic_id'])
        if data.get('difficulty'):
            qs = qs.filter(difficulty=data['difficulty'])

        num = min(data['num_questions'], qs.count())
        if num == 0:
            return Response(
                {'detail': 'No questions match the given filters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if data.get('shuffle_questions', True):
            selected = list(qs.order_by('?')[:num])
        else:
            selected = list(qs.order_by('created_at')[:num])

        # Resolve optional FKs
        topic = None
        if data.get('topic_id'):
            from subjects.models import Topic
            topic = Topic.objects.filter(id=data['topic_id']).first()

        exam_category = None
        if data.get('exam_category_id'):
            exam_category = ExamCategory.objects.filter(id=data['exam_category_id']).first()

        session = MockExamSession.objects.create(
            student=request.user,
            bank=bank,
            exam_category=exam_category,
            topic=topic,
            difficulty=data.get('difficulty') or None,
            num_questions=num,
            duration_minutes=data['duration_minutes'],
            passing_score=data['passing_score'],
            shuffle_questions=data.get('shuffle_questions', True),
        )

        # Pre-create answer slots
        MockExamAnswer.objects.bulk_create([
            MockExamAnswer(session=session, bank_question=bq)
            for bq in selected
        ])

        questions_data = [
            {
                'id': str(bq.id),
                'question_text': bq.question_text,
                'question_type': bq.question_type,
                'option_a': bq.option_a,
                'option_b': bq.option_b,
                'option_c': bq.option_c,
                'option_d': bq.option_d,
                'difficulty': bq.difficulty,
                'marks': bq.marks,
            }
            for bq in selected
        ]

        return Response(
            {
                'session': MockExamSessionSerializer(session).data,
                'questions': questions_data,
                'total_questions': num,
            },
            status=status.HTTP_201_CREATED,
        )


class SaveMockAnswerView(APIView):
    """
    POST /mock/<session_id>/save/
    Save/update a single answer during a mock exam (no feedback returned).
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, session_id):
        session = get_object_or_404(
            MockExamSession,
            id=session_id,
            student=request.user,
            status=MockExamSession.Status.IN_PROGRESS,
        )

        # Auto-submit if timed out
        if session.is_timed_out:
            session.submit(auto=True)
            return Response(
                {'detail': 'Time expired. Mock exam auto-submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = MockAnswerSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        bq = get_object_or_404(
            BankQuestion,
            id=data['bank_question_id'],
            bank=session.bank,
        )

        answer, _ = MockExamAnswer.objects.get_or_create(
            session=session,
            bank_question=bq,
        )
        answer.selected_answer = data.get('selected_answer', '')
        answer.is_marked_for_review = data.get('is_marked_for_review', False)
        answer.time_spent_seconds = data.get('time_spent_seconds', 0)
        answer.answered_at = timezone.now()
        answer.save()

        return Response({'saved': True, 'question_id': str(bq.id)})


class SubmitMockExamView(APIView):
    """
    POST /mock/<session_id>/submit/
    Submit the mock exam. Grades all answers and returns full score summary + review.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, session_id):
        session = get_object_or_404(
            MockExamSession,
            id=session_id,
            student=request.user,
        )

        if session.status not in (MockExamSession.Status.IN_PROGRESS,):
            return Response(
                {'detail': 'This mock exam has already been submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Save any final bulk answers
        answers_data = request.data.get('answers', [])
        for ans in answers_data:
            try:
                bq = BankQuestion.objects.get(id=ans['bank_question_id'], bank=session.bank)
                obj, _ = MockExamAnswer.objects.get_or_create(session=session, bank_question=bq)
                obj.selected_answer = ans.get('selected_answer', '')
                obj.is_marked_for_review = ans.get('is_marked_for_review', False)
                obj.time_spent_seconds = ans.get('time_spent_seconds', 0)
                obj.answered_at = timezone.now()
                obj.save()
            except BankQuestion.DoesNotExist:
                pass

        session.submit(auto=False)

        # Update TopicPerformance for all answered questions with topics
        for ans in session.mock_answers.select_related('bank_question__topic', 'bank_question__bank__subject'):
            bq = ans.bank_question
            if bq.topic_id and ans.is_correct is not None:
                TopicPerformance.record_answer(
                    student=request.user,
                    topic=bq.topic,
                    subject=bq.bank.subject,
                    school=request.school,
                    is_correct=bool(ans.is_correct),
                )

        return Response(MockExamSessionDetailSerializer(session).data)


class MyMockExamSessionsView(generics.ListAPIView):
    """
    GET /mock/my/
    List the current student's mock exam sessions.
    """

    serializer_class = MockExamSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['status', 'bank', 'exam_category']

    def get_queryset(self):
        return MockExamSession.objects.filter(
            student=self.request.user,
            bank__school=self.request.school,
        ).select_related('bank', 'bank__subject', 'exam_category', 'topic').order_by('-created_at')


class MockExamSessionDetailView(generics.RetrieveAPIView):
    """
    GET /mock/<session_id>/
    Get a mock exam session with full answer review (available after submission).
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_serializer_class(self):
        session = self.get_object()
        if session.status in (MockExamSession.Status.SUBMITTED, MockExamSession.Status.TIMED_OUT):
            return MockExamSessionDetailSerializer
        return MockExamSessionSerializer

    def get_queryset(self):
        return MockExamSession.objects.filter(
            student=self.request.user,
            bank__school=self.request.school,
        ).prefetch_related('mock_answers__bank_question')


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — Weak Topic Detection
# ─────────────────────────────────────────────────────────────────────────────

class MyTopicPerformanceView(generics.ListAPIView):
    """
    GET /performance/topics/
    List the current student's topic performance records.
    Supports ?subject=, ?strength_level= filters.
    Ordered by accuracy ascending (weakest first).
    """

    serializer_class = TopicPerformanceSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['subject', 'strength_level']

    def get_queryset(self):
        return TopicPerformance.objects.filter(
            student=self.request.user,
            school=self.request.school,
        ).select_related('topic', 'subject').order_by('accuracy_percent')


class WeakTopicsView(generics.ListAPIView):
    """
    GET /performance/topics/weak/
    Return only weak topics (accuracy < 50%) for the current student.
    """

    serializer_class = TopicPerformanceSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['subject']

    def get_queryset(self):
        return TopicPerformance.objects.filter(
            student=self.request.user,
            school=self.request.school,
            strength_level=TopicPerformance.StrengthLevel.WEAK,
        ).select_related('topic', 'subject').order_by('accuracy_percent')


class StrongTopicsView(generics.ListAPIView):
    """
    GET /performance/topics/strong/
    Return only strong topics (accuracy ≥ 75%) for the current student.
    """

    serializer_class = TopicPerformanceSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['subject']

    def get_queryset(self):
        return TopicPerformance.objects.filter(
            student=self.request.user,
            school=self.request.school,
            strength_level=TopicPerformance.StrengthLevel.STRONG,
        ).select_related('topic', 'subject').order_by('-accuracy_percent')


class SubjectPerformanceBreakdownView(APIView):
    """
    GET /performance/subjects/<subject_id>/
    Detailed weak/strong breakdown for a single subject.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get(self, request, subject_id):
        from subjects.models import Subject
        subject = get_object_or_404(Subject, id=subject_id, school=request.school)
        data = get_subject_breakdown(
            student=request.user,
            school=request.school,
            subject=subject,
        )
        return Response(data)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 4 — Study Recommendations
# ─────────────────────────────────────────────────────────────────────────────

class StudyRecommendationsView(APIView):
    """
    GET /performance/recommendations/
    Return personalised study recommendations for the current student.

    Query params:
      ?subject_id=<uuid>   — narrow to a single subject
      ?limit=5             — max items per bucket (default 5)
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get(self, request):
        serializer = RecommendationQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        params = serializer.validated_data

        subject = None
        if params.get('subject_id'):
            from subjects.models import Subject
            subject = Subject.objects.filter(
                id=params['subject_id'], school=request.school
            ).first()

        recommendations = get_recommendations(
            student=request.user,
            school=request.school,
            subject=subject,
            limit=params.get('limit', 5),
        )
        return Response(recommendations)
