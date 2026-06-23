"""
Serializers for the exams app.
Phase 6B additions: QuestionBank, BankQuestion, ExamCategory, import/generation.
Phase 6C additions: PracticeSession, PracticeAnswer, MockExamSession, MockExamAnswer,
                    TopicPerformance, Recommendations.
"""

from rest_framework import serializers
from django.utils import timezone

from .models import (
    Exam, Question, ExamAttempt, ExamAnswer, ExamResult,
    ExamCategory, QuestionCategory, QuestionTag,
    QuestionBank, BankQuestion, ExamBankQuestion,
    PracticeSession, PracticeAnswer,
    MockExamSession, MockExamAnswer,
    TopicPerformance,
)


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for questions (teacher view - includes correct answer)."""

    class Meta:
        model = Question
        fields = [
            'id', 'exam', 'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation', 'difficulty',
            'marks', 'order', 'is_active', 'topic',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class QuestionStudentSerializer(serializers.ModelSerializer):
    """Serializer for questions (student view - hides correct answer)."""

    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'difficulty', 'marks', 'order',
        ]


class ExamSerializer(serializers.ModelSerializer):
    """List serializer for exams."""

    question_count = serializers.ReadOnlyField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'subject', 'subject_name', 'subject_code',
            'created_by', 'created_by_name', 'exam_type', 'status',
            'duration_minutes', 'passing_score', 'total_marks',
            'question_count', 'shuffle_questions', 'shuffle_options',
            'show_result_immediately', 'allow_review', 'max_attempts',
            'start_date', 'end_date', 'term', 'is_available',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_marks']


class ExamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating exams."""

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'subject', 'exam_type', 'status',
            'instructions', 'duration_minutes', 'passing_score',
            'shuffle_questions', 'shuffle_options',
            'show_result_immediately', 'allow_review', 'max_attempts',
            'start_date', 'end_date', 'term',
        ]
        read_only_fields = ['id']

    def validate_passing_score(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError('Passing score must be between 0 and 100.')
        return value

    def validate_duration_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError('Duration must be at least 1 minute.')
        return value


class ExamDetailSerializer(ExamSerializer):
    """Detail serializer including questions (teacher view)."""

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['instructions', 'questions']


class ExamAnswerSerializer(serializers.ModelSerializer):
    """Serializer for submitting answers."""

    class Meta:
        model = ExamAnswer
        fields = [
            'id', 'question', 'selected_answer',
            'is_marked_for_review', 'time_spent_seconds',
        ]
        read_only_fields = ['id']


class ExamAnswerResultSerializer(serializers.ModelSerializer):
    """Serializer for answer results (shown after submission)."""

    question_text = serializers.CharField(source='question.question_text', read_only=True)
    correct_answer = serializers.CharField(source='question.correct_answer', read_only=True)
    explanation = serializers.CharField(source='question.explanation', read_only=True)
    marks = serializers.IntegerField(source='question.marks', read_only=True)

    class Meta:
        model = ExamAnswer
        fields = [
            'id', 'question', 'question_text', 'selected_answer',
            'correct_answer', 'is_correct', 'explanation', 'marks',
            'is_marked_for_review',
        ]


class ExamAttemptSerializer(serializers.ModelSerializer):
    """Serializer for exam attempts."""

    exam_title = serializers.CharField(source='exam.title', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    time_remaining_seconds = serializers.ReadOnlyField()

    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'student', 'student_name',
            'status', 'started_at', 'submitted_at', 'time_taken_seconds',
            'score', 'percentage', 'passed', 'total_questions',
            'correct_answers', 'wrong_answers', 'skipped_answers',
            'attempt_number', 'time_remaining_seconds',
            'created_at',
        ]
        read_only_fields = [
            'id', 'student', 'started_at', 'submitted_at', 'time_taken_seconds',
            'score', 'percentage', 'passed', 'total_questions',
            'correct_answers', 'wrong_answers', 'skipped_answers',
            'attempt_number', 'created_at',
        ]


class ExamAttemptDetailSerializer(ExamAttemptSerializer):
    """Detail serializer including answers."""

    answers = ExamAnswerResultSerializer(many=True, read_only=True)
    exam_detail = ExamSerializer(source='exam', read_only=True)

    class Meta(ExamAttemptSerializer.Meta):
        fields = ExamAttemptSerializer.Meta.fields + ['answers', 'exam_detail']


class StartExamSerializer(serializers.Serializer):
    """Serializer for starting an exam."""
    exam_id = serializers.UUIDField()


class SubmitAnswerSerializer(serializers.Serializer):
    """Serializer for submitting a single answer."""
    question_id = serializers.UUIDField()
    selected_answer = serializers.CharField(allow_blank=True, required=False)
    is_marked_for_review = serializers.BooleanField(default=False)
    time_spent_seconds = serializers.IntegerField(default=0, min_value=0)


class BulkSubmitSerializer(serializers.Serializer):
    """Serializer for bulk answer submission (final submit)."""
    answers = SubmitAnswerSerializer(many=True)


class ExamResultSerializer(serializers.ModelSerializer):
    """Serializer for exam results."""

    exam_title = serializers.CharField(source='exam.title', read_only=True)
    subject_name = serializers.CharField(source='exam.subject.name', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    passing_score = serializers.DecimalField(
        source='exam.passing_score', max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = ExamResult
        fields = [
            'id', 'attempt', 'student', 'student_name', 'exam', 'exam_title',
            'subject_name', 'score', 'percentage', 'passed', 'grade',
            'rank', 'feedback', 'passing_score', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 6B — Question Bank Serializers
# ═════════════════════════════════════════════════════════════════════════════

class ExamCategorySerializer(serializers.ModelSerializer):
    """Serializer for ExamCategory (WAEC, NECO, JAMB, etc.)."""

    code_display = serializers.CharField(source='get_code_display', read_only=True)

    class Meta:
        model = ExamCategory
        fields = [
            'id', 'code', 'code_display', 'name', 'description',
            'is_public', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'code_display']


class QuestionCategorySerializer(serializers.ModelSerializer):
    """Serializer for QuestionCategory."""

    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)

    class Meta:
        model = QuestionCategory
        fields = ['id', 'name', 'parent', 'parent_name', 'description', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class QuestionTagSerializer(serializers.ModelSerializer):
    """Serializer for QuestionTag."""

    class Meta:
        model = QuestionTag
        fields = ['id', 'name', 'color', 'created_at']
        read_only_fields = ['id', 'created_at']


class QuestionBankSerializer(serializers.ModelSerializer):
    """List serializer for QuestionBank."""

    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    exam_category_name = serializers.CharField(source='exam_category.name', read_only=True, default=None)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True, default=None)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    question_count = serializers.ReadOnlyField()

    class Meta:
        model = QuestionBank
        fields = [
            'id', 'name', 'description',
            'subject', 'subject_name', 'subject_code',
            'exam_category', 'exam_category_name',
            'class_level', 'class_level_name',
            'created_by', 'created_by_name',
            'is_active', 'is_shared', 'question_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'question_count']


class QuestionBankCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a QuestionBank."""

    class Meta:
        model = QuestionBank
        fields = [
            'name', 'description', 'subject',
            'exam_category', 'class_level', 'is_shared',
        ]


class BankQuestionSerializer(serializers.ModelSerializer):
    """Full serializer for BankQuestion (teacher view — includes correct answer)."""

    tags = QuestionTagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=QuestionTag.objects.all(),
        write_only=True, required=False, source='tags',
    )
    topic_name = serializers.CharField(source='topic.name', read_only=True, default=None)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    exam_category_name = serializers.CharField(source='exam_category.name', read_only=True, default=None)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    type_display = serializers.CharField(source='get_question_type_display', read_only=True)

    class Meta:
        model = BankQuestion
        fields = [
            'id', 'bank',
            'question_text', 'question_type', 'type_display',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation',
            'difficulty', 'difficulty_display', 'marks',
            'topic', 'topic_name',
            'category', 'category_name',
            'tags', 'tag_ids',
            'exam_category', 'exam_category_name', 'exam_year',
            'image', 'is_active', 'times_used',
            'import_source', 'import_batch',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'times_used', 'import_source', 'import_batch',
            'created_at', 'updated_at',
        ]


class BankQuestionStudentSerializer(serializers.ModelSerializer):
    """Student-safe serializer — hides correct_answer and explanation."""

    class Meta:
        model = BankQuestion
        fields = [
            'id', 'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'difficulty', 'marks',
        ]


class BankQuestionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a BankQuestion."""

    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=QuestionTag.objects.all(),
        write_only=True, required=False, source='tags',
    )

    class Meta:
        model = BankQuestion
        fields = [
            'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation',
            'difficulty', 'marks',
            'topic', 'category', 'tag_ids',
            'exam_category', 'exam_year', 'image',
        ]

    def validate(self, attrs):
        qtype = attrs.get('question_type', BankQuestion.QuestionType.MCQ)
        if qtype == BankQuestion.QuestionType.MCQ:
            if not attrs.get('option_a') or not attrs.get('option_b'):
                raise serializers.ValidationError(
                    'MCQ questions require at least option_a and option_b.'
                )
            valid_answers = {'A', 'B', 'C', 'D'}
            if attrs.get('correct_answer', '').upper() not in valid_answers:
                raise serializers.ValidationError(
                    'MCQ correct_answer must be A, B, C, or D.'
                )
        elif qtype == BankQuestion.QuestionType.TRUE_FALSE:
            if attrs.get('correct_answer', '').lower() not in ('true', 'false'):
                raise serializers.ValidationError(
                    'True/False correct_answer must be "True" or "False".'
                )
        return attrs


class ExamBankQuestionSerializer(serializers.ModelSerializer):
    """Serializer for ExamBankQuestion (snapshot of a bank question in an exam)."""

    class Meta:
        model = ExamBankQuestion
        fields = [
            'id', 'exam', 'bank_question',
            'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation',
            'difficulty', 'marks', 'order', 'is_active',
            'created_at',
        ]
        read_only_fields = [
            'id', 'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation', 'difficulty',
            'created_at',
        ]


# ── Import serializers ────────────────────────────────────────────────────────

class QuestionImportSerializer(serializers.Serializer):
    """Serializer for file-based question import (CSV or Excel)."""

    file = serializers.FileField(required=True)
    format = serializers.ChoiceField(
        choices=[('csv', 'CSV'), ('excel', 'Excel (.xlsx)')],
        default='csv',
    )
    import_batch = serializers.CharField(required=False, allow_blank=True, default='')


class QuestionBulkJSONSerializer(serializers.Serializer):
    """Serializer for bulk JSON import of questions."""

    questions = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text='List of question dicts. Each must have question_text and correct_answer.',
    )
    import_batch = serializers.CharField(required=False, allow_blank=True, default='')


# ── Exam generation from bank ─────────────────────────────────────────────────

class GenerateExamFromBankSerializer(serializers.Serializer):
    """
    Serializer for generating an exam by pulling questions from a bank.
    Teacher specifies filters and the system auto-selects questions.
    """

    # Target exam
    exam_title = serializers.CharField(max_length=200)
    bank_id = serializers.UUIDField(required=True)

    # Filters
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    topic_id = serializers.UUIDField(required=False, allow_null=True)
    difficulty = serializers.ChoiceField(
        choices=[('', 'Any'), ('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        required=False, allow_blank=True, default='',
    )
    exam_category_code = serializers.CharField(required=False, allow_blank=True, default='')
    class_level_id = serializers.UUIDField(required=False, allow_null=True)
    question_type = serializers.ChoiceField(
        choices=[('', 'Any'), ('mcq', 'MCQ'), ('true_false', 'True/False'), ('short_answer', 'Short Answer')],
        required=False, allow_blank=True, default='',
    )

    # Quantity
    num_questions = serializers.IntegerField(min_value=1, max_value=200, default=20)
    marks_per_question = serializers.IntegerField(min_value=1, default=1)
    randomise = serializers.BooleanField(default=True)

    # Exam settings
    duration_minutes = serializers.IntegerField(min_value=1, default=60)
    passing_score = serializers.DecimalField(max_digits=5, decimal_places=2, default=50.0)
    exam_type = serializers.ChoiceField(
        choices=Exam.ExamType.choices, default=Exam.ExamType.CBT
    )
    term_id = serializers.UUIDField(required=False, allow_null=True)


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 6C — Practice Mode, Mock Exams & Student Improvement
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Practice Mode
# ─────────────────────────────────────────────────────────────────────────────

class StartPracticeSerializer(serializers.Serializer):
    """Input for starting a new practice session."""

    bank_id = serializers.UUIDField()
    topic_id = serializers.UUIDField(required=False, allow_null=True)
    difficulty = serializers.ChoiceField(
        choices=[('', 'Any'), ('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        required=False, allow_blank=True, default='',
    )
    question_type = serializers.ChoiceField(
        choices=[('', 'Any'), ('mcq', 'MCQ'), ('true_false', 'True/False'), ('short_answer', 'Short Answer')],
        required=False, allow_blank=True, default='',
    )
    num_questions = serializers.IntegerField(min_value=1, max_value=100, default=10)


class PracticeAnswerSubmitSerializer(serializers.Serializer):
    """Input for submitting a single practice answer (instant feedback)."""

    bank_question_id = serializers.UUIDField()
    selected_answer = serializers.CharField(allow_blank=True, required=False, default='')
    time_spent_seconds = serializers.IntegerField(min_value=0, default=0)


class PracticeAnswerSerializer(serializers.ModelSerializer):
    """Read serializer for a PracticeAnswer — includes instant feedback fields."""

    question_text = serializers.CharField(source='bank_question.question_text', read_only=True)
    question_type = serializers.CharField(source='bank_question.question_type', read_only=True)
    correct_answer = serializers.CharField(source='bank_question.correct_answer', read_only=True)
    explanation = serializers.CharField(source='bank_question.explanation', read_only=True)
    option_a = serializers.CharField(source='bank_question.option_a', read_only=True)
    option_b = serializers.CharField(source='bank_question.option_b', read_only=True)
    option_c = serializers.CharField(source='bank_question.option_c', read_only=True)
    option_d = serializers.CharField(source='bank_question.option_d', read_only=True)
    marks = serializers.IntegerField(source='bank_question.marks', read_only=True)

    class Meta:
        model = PracticeAnswer
        fields = [
            'id', 'bank_question', 'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'selected_answer', 'is_correct', 'correct_answer',
            'explanation', 'marks', 'time_spent_seconds', 'created_at',
        ]
        read_only_fields = ['id', 'is_correct', 'created_at']


class PracticeSessionSerializer(serializers.ModelSerializer):
    """Serializer for PracticeSession."""

    bank_name = serializers.CharField(source='bank.name', read_only=True)
    subject_name = serializers.CharField(source='bank.subject.name', read_only=True)
    subject_code = serializers.CharField(source='bank.subject.code', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default=None)
    total_answered = serializers.ReadOnlyField()
    total_correct = serializers.ReadOnlyField()
    score_percent = serializers.ReadOnlyField()

    class Meta:
        model = PracticeSession
        fields = [
            'id', 'bank', 'bank_name', 'subject_name', 'subject_code',
            'topic', 'topic_name', 'difficulty', 'question_type',
            'num_questions', 'status', 'completed_at',
            'total_answered', 'total_correct', 'score_percent',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PracticeSessionDetailSerializer(PracticeSessionSerializer):
    """Practice session with all answers (for review)."""

    answers = PracticeAnswerSerializer(source='practice_answers', many=True, read_only=True)

    class Meta(PracticeSessionSerializer.Meta):
        fields = PracticeSessionSerializer.Meta.fields + ['answers']


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Mock Exam Mode
# ─────────────────────────────────────────────────────────────────────────────

class StartMockExamSerializer(serializers.Serializer):
    """Input for starting a new mock exam session."""

    bank_id = serializers.UUIDField()
    exam_category_id = serializers.UUIDField(required=False, allow_null=True)
    topic_id = serializers.UUIDField(required=False, allow_null=True)
    difficulty = serializers.ChoiceField(
        choices=[('', 'Any'), ('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        required=False, allow_blank=True, default='',
    )
    num_questions = serializers.IntegerField(min_value=1, max_value=200, default=40)
    duration_minutes = serializers.IntegerField(min_value=1, max_value=360, default=60)
    passing_score = serializers.DecimalField(max_digits=5, decimal_places=2, default=50.0)
    shuffle_questions = serializers.BooleanField(default=True)


class MockAnswerSubmitSerializer(serializers.Serializer):
    """Input for saving/updating a single mock exam answer."""

    bank_question_id = serializers.UUIDField()
    selected_answer = serializers.CharField(allow_blank=True, required=False, default='')
    is_marked_for_review = serializers.BooleanField(default=False)
    time_spent_seconds = serializers.IntegerField(min_value=0, default=0)


class BulkMockSubmitSerializer(serializers.Serializer):
    """Input for final mock exam submission (bulk answers)."""

    answers = MockAnswerSubmitSerializer(many=True, default=list)


class MockExamAnswerSerializer(serializers.ModelSerializer):
    """Read serializer for MockExamAnswer — includes feedback after submission."""

    question_text = serializers.CharField(source='bank_question.question_text', read_only=True)
    question_type = serializers.CharField(source='bank_question.question_type', read_only=True)
    correct_answer = serializers.CharField(source='bank_question.correct_answer', read_only=True)
    explanation = serializers.CharField(source='bank_question.explanation', read_only=True)
    option_a = serializers.CharField(source='bank_question.option_a', read_only=True)
    option_b = serializers.CharField(source='bank_question.option_b', read_only=True)
    option_c = serializers.CharField(source='bank_question.option_c', read_only=True)
    option_d = serializers.CharField(source='bank_question.option_d', read_only=True)
    marks = serializers.IntegerField(source='bank_question.marks', read_only=True)
    difficulty = serializers.CharField(source='bank_question.difficulty', read_only=True)

    class Meta:
        model = MockExamAnswer
        fields = [
            'id', 'bank_question', 'question_text', 'question_type',
            'option_a', 'option_b', 'option_c', 'option_d',
            'selected_answer', 'is_correct', 'correct_answer',
            'explanation', 'marks', 'difficulty',
            'is_marked_for_review', 'time_spent_seconds', 'answered_at',
        ]
        read_only_fields = ['id', 'is_correct']


class MockExamSessionSerializer(serializers.ModelSerializer):
    """Serializer for MockExamSession (list view)."""

    bank_name = serializers.CharField(source='bank.name', read_only=True)
    subject_name = serializers.CharField(source='bank.subject.name', read_only=True)
    subject_code = serializers.CharField(source='bank.subject.code', read_only=True)
    exam_category_name = serializers.CharField(source='exam_category.name', read_only=True, default=None)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default=None)
    time_remaining_seconds = serializers.ReadOnlyField()

    class Meta:
        model = MockExamSession
        fields = [
            'id', 'bank', 'bank_name', 'subject_name', 'subject_code',
            'exam_category', 'exam_category_name',
            'topic', 'topic_name', 'difficulty',
            'num_questions', 'duration_minutes', 'passing_score',
            'shuffle_questions', 'status',
            'started_at', 'submitted_at', 'time_taken_seconds',
            'score', 'percentage', 'passed',
            'total_questions', 'correct_answers', 'wrong_answers', 'skipped_answers',
            'time_remaining_seconds', 'created_at',
        ]
        read_only_fields = [
            'id', 'started_at', 'submitted_at', 'time_taken_seconds',
            'score', 'percentage', 'passed',
            'total_questions', 'correct_answers', 'wrong_answers', 'skipped_answers',
            'created_at',
        ]


class MockExamSessionDetailSerializer(MockExamSessionSerializer):
    """Mock exam session with full answer review (shown after submission)."""

    answers = MockExamAnswerSerializer(source='mock_answers', many=True, read_only=True)

    class Meta(MockExamSessionSerializer.Meta):
        fields = MockExamSessionSerializer.Meta.fields + ['answers']


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — Weak Topic Detection
# ─────────────────────────────────────────────────────────────────────────────

class TopicPerformanceSerializer(serializers.ModelSerializer):
    """Serializer for TopicPerformance."""

    topic_name = serializers.CharField(source='topic.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    strength_display = serializers.CharField(source='get_strength_level_display', read_only=True)

    class Meta:
        model = TopicPerformance
        fields = [
            'id', 'topic', 'topic_name', 'subject', 'subject_name', 'subject_code',
            'total_attempts', 'total_correct', 'total_wrong',
            'accuracy_percent', 'strength_level', 'strength_display',
            'last_practiced_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_attempts', 'total_correct', 'total_wrong',
            'accuracy_percent', 'strength_level', 'last_practiced_at',
            'created_at', 'updated_at',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# TASK 4 — Study Recommendations (response shape)
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationQuerySerializer(serializers.Serializer):
    """Query params for the recommendations endpoint."""

    subject_id = serializers.UUIDField(required=False, allow_null=True)
    limit = serializers.IntegerField(min_value=1, max_value=20, default=5)
