"""
Serializers for the exams app.
"""

from rest_framework import serializers

from .models import (
    QuestionBank, QuestionTag, Exam, ExamTemplate, ExamGroup,
    Question, QuestionOption, ExamAttempt, Answer, Result,
)
from core.mixins import DynamicFieldsMixin


class QuestionOptionSerializer(serializers.ModelSerializer):
    """Serializer for question options."""

    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_correct', 'order', 'image']
        read_only_fields = ['id']


class QuestionOptionStudentSerializer(serializers.ModelSerializer):
    """Serializer for options shown to students (hides correct answer)."""

    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'order', 'image']
        read_only_fields = ['id']


class QuestionSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Serializer for questions (teacher view - shows correct answers)."""

    options = QuestionOptionSerializer(many=True, read_only=True)
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'exam', 'question_bank', 'question_type', 'text',
            'explanation', 'marks', 'order', 'is_required', 'image',
            'tags', 'tag_names', 'metadata', 'options', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_tag_names(self, obj):
        return [tag.name for tag in obj.tags.all()]


class QuestionStudentSerializer(serializers.ModelSerializer):
    """Serializer for questions shown to students during exam (no correct answers)."""

    options = QuestionOptionStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'text', 'marks', 'order',
            'is_required', 'image', 'options',
        ]
        read_only_fields = fields


class QuestionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating questions with options."""

    options = QuestionOptionSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = [
            'question_type', 'text', 'explanation', 'marks',
            'order', 'is_required', 'image', 'tags', 'metadata', 'options',
        ]

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        tags = validated_data.pop('tags', [])
        question = Question.objects.create(**validated_data)
        question.tags.set(tags)

        for option_data in options_data:
            QuestionOption.objects.create(question=question, **option_data)

        return question


class QuestionBankSerializer(serializers.ModelSerializer):
    """Serializer for question banks."""

    question_count = serializers.ReadOnlyField()
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)

    class Meta:
        model = QuestionBank
        fields = [
            'id', 'subject', 'subject_name', 'name', 'description',
            'created_by', 'created_by_name', 'question_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class QuestionTagSerializer(serializers.ModelSerializer):
    """Serializer for question tags."""

    class Meta:
        model = QuestionTag
        fields = ['id', 'name', 'tag_type', 'created_at']
        read_only_fields = ['id', 'created_at']


class ExamSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Serializer for exam listing."""

    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True, default=None)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    question_count = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = Exam
        fields = [
            'id', 'subject', 'subject_name', 'subject_code', 'term', 'term_name',
            'classroom', 'classroom_name', 'title', 'description', 'exam_type',
            'total_marks', 'pass_marks', 'duration_minutes',
            'start_time', 'end_time', 'is_published', 'is_proctored',
            'shuffle_questions', 'shuffle_options', 'show_results_immediately',
            'show_correct_answers', 'max_attempts', 'instructions',
            'created_by', 'created_by_name', 'question_count', 'is_available',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class ExamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating an exam."""

    class Meta:
        model = Exam
        fields = [
            'subject', 'term', 'classroom', 'title', 'description',
            'exam_type', 'total_marks', 'pass_marks', 'duration_minutes',
            'start_time', 'end_time', 'is_proctored', 'shuffle_questions',
            'shuffle_options', 'show_results_immediately', 'show_correct_answers',
            'max_attempts', 'instructions',
        ]


class ExamDetailSerializer(ExamSerializer):
    """Detailed exam serializer with questions (teacher view)."""

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['questions']


class ExamTemplateSerializer(serializers.ModelSerializer):
    """Serializer for exam templates."""

    class Meta:
        model = ExamTemplate
        fields = [
            'id', 'subject', 'name', 'description', 'structure',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class ExamGroupSerializer(serializers.ModelSerializer):
    """Serializer for exam groups."""

    exam_count = serializers.SerializerMethodField()

    class Meta:
        model = ExamGroup
        fields = [
            'id', 'name', 'description', 'term', 'exams',
            'exam_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_exam_count(self, obj):
        return obj.exams.count()


class AnswerSerializer(serializers.ModelSerializer):
    """Serializer for answers."""

    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)

    class Meta:
        model = Answer
        fields = [
            'id', 'question', 'question_text', 'question_type',
            'selected_option', 'text_answer', 'marks_awarded',
            'is_correct', 'ai_feedback', 'teacher_feedback',
            'graded_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'marks_awarded', 'is_correct', 'ai_feedback',
            'teacher_feedback', 'graded_at', 'created_at',
        ]


class SubmitAnswerSerializer(serializers.Serializer):
    """Serializer for submitting an answer during an exam."""

    question_id = serializers.UUIDField()
    selected_option_id = serializers.UUIDField(required=False, allow_null=True)
    text_answer = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class GradeAnswerSerializer(serializers.Serializer):
    """Serializer for manually grading an answer."""

    marks = serializers.DecimalField(max_digits=5, decimal_places=2)
    feedback = serializers.CharField(required=False, allow_blank=True, default='')


class ExamAttemptSerializer(serializers.ModelSerializer):
    """Serializer for exam attempts."""

    exam_title = serializers.CharField(source='exam.title', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    passed = serializers.ReadOnlyField()
    time_remaining_seconds = serializers.ReadOnlyField()

    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'student', 'student_name',
            'attempt_number', 'started_at', 'submitted_at',
            'score', 'percentage', 'status', 'passed',
            'time_remaining_seconds', 'time_spent_seconds',
            'created_at',
        ]
        read_only_fields = fields


class ExamAttemptDetailSerializer(ExamAttemptSerializer):
    """Detailed attempt serializer with answers."""

    answers = AnswerSerializer(many=True, read_only=True)

    class Meta(ExamAttemptSerializer.Meta):
        fields = ExamAttemptSerializer.Meta.fields + ['answers']


class ResultSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Serializer for results."""

    student_name = serializers.CharField(source='student.full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = Result
        fields = [
            'id', 'student', 'student_name', 'subject', 'subject_name',
            'subject_code', 'term', 'term_name', 'exam', 'score',
            'total_possible', 'percentage', 'grade', 'remarks',
            'is_published', 'published_at', 'created_at',
        ]
        read_only_fields = ['id', 'percentage', 'published_at', 'created_at']


class ResultCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating results."""

    class Meta:
        model = Result
        fields = [
            'student', 'subject', 'term', 'exam', 'score',
            'total_possible', 'grade', 'remarks',
        ]
