"""
Serializers for the results app.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import GradeConfig, ResultSheet, StudentScore, ReportCard, ScoreEntryBatch

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# GRADE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

class GradeConfigSerializer(serializers.ModelSerializer):
    total_max = serializers.ReadOnlyField()

    class Meta:
        model = GradeConfig
        fields = [
            'id', 'system', 'pass_mark',
            'ca_max_score', 'exam_max_score', 'total_max',
            'bands', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_max']

    def validate_bands(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('bands must be a list.')
        required_keys = {'grade', 'min', 'max', 'remark'}
        for i, band in enumerate(value):
            missing = required_keys - set(band.keys())
            if missing:
                raise serializers.ValidationError(
                    f'Band #{i} is missing keys: {missing}'
                )
            if band['min'] > band['max']:
                raise serializers.ValidationError(
                    f'Band #{i}: min ({band["min"]}) > max ({band["max"]})'
                )
        return value

    def validate(self, data):
        ca = data.get('ca_max_score', self.instance.ca_max_score if self.instance else Decimal('40'))
        exam = data.get('exam_max_score', self.instance.exam_max_score if self.instance else Decimal('60'))
        if ca + exam <= 0:
            raise serializers.ValidationError('ca_max_score + exam_max_score must be > 0.')
        return data


class GradeConfigNigerianResetSerializer(serializers.Serializer):
    """Trigger reset to Nigerian A1–F9 defaults."""
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError('Set confirm=true to reset.')
        return value


# ─────────────────────────────────────────────────────────────────────────────
# RESULT SHEET
# ─────────────────────────────────────────────────────────────────────────────

class ResultSheetSerializer(serializers.ModelSerializer):
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    academic_year_name = serializers.CharField(
        source='term.academic_year.name', read_only=True
    )
    published_by_name = serializers.CharField(
        source='published_by.full_name', read_only=True, default=None
    )
    score_count = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = ResultSheet
        fields = [
            'id', 'classroom', 'classroom_name',
            'term', 'term_name', 'academic_year_name',
            'academic_session',
            'status', 'published_by', 'published_by_name', 'published_at',
            'next_term_begins', 'principal_remark',
            'score_count', 'student_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'school', 'published_by', 'published_at',
            'created_at', 'updated_at',
        ]

    def get_score_count(self, obj):
        return obj.scores.count()

    def get_student_count(self, obj):
        return obj.report_cards.count()


class ResultSheetCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultSheet
        fields = ['classroom', 'term', 'academic_session', 'next_term_begins', 'principal_remark']

    def validate(self, data):
        school = self.context['request'].school
        classroom = data['classroom']
        term = data['term']
        if classroom.school != school:
            raise serializers.ValidationError('Classroom does not belong to this school.')
        if term.academic_year.school != school:
            raise serializers.ValidationError('Term does not belong to this school.')
        if ResultSheet.objects.filter(classroom=classroom, term=term).exists():
            raise serializers.ValidationError(
                'A result sheet already exists for this classroom and term.'
            )
        return data


class PublishResultSheetSerializer(serializers.Serializer):
    """Used to publish or unpublish a result sheet."""
    action = serializers.ChoiceField(choices=['publish', 'unpublish'])


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT SCORE
# ─────────────────────────────────────────────────────────────────────────────

class StudentScoreSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    is_pass = serializers.ReadOnlyField()

    class Meta:
        model = StudentScore
        fields = [
            'id', 'result_sheet',
            'student', 'student_name', 'student_email',
            'subject', 'subject_name', 'subject_code',
            'ca1_score', 'ca2_score', 'ca3_score', 'exam_score',
            'total_ca', 'total_score', 'percentage',
            'grade', 'grade_remark', 'grade_points',
            'is_absent', 'is_pass',
            'entered_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'total_ca', 'total_score', 'percentage',
            'grade', 'grade_remark', 'grade_points',
            'is_pass', 'entered_by', 'created_at', 'updated_at',
        ]


class StudentScoreCreateSerializer(serializers.ModelSerializer):
    """Used by teachers to enter/update a single student's score."""

    class Meta:
        model = StudentScore
        fields = [
            'student', 'subject',
            'ca1_score', 'ca2_score', 'ca3_score',
            'exam_score', 'is_absent',
        ]

    def validate(self, data):
        request = self.context['request']
        result_sheet = self.context['result_sheet']

        # Cannot edit a published sheet
        if result_sheet.is_published:
            raise serializers.ValidationError(
                'Cannot edit scores on a published result sheet.'
            )

        # Validate score bounds against GradeConfig
        try:
            cfg = result_sheet.school.grade_config
            ca_max = cfg.ca_max_score
            exam_max = cfg.exam_max_score
        except Exception:
            ca_max = Decimal('40')
            exam_max = Decimal('60')

        ca_total = (
            data.get('ca1_score', Decimal('0')) +
            data.get('ca2_score', Decimal('0')) +
            data.get('ca3_score', Decimal('0'))
        )
        if ca_total > ca_max:
            raise serializers.ValidationError(
                f'Total CA ({ca_total}) exceeds configured CA max ({ca_max}).'
            )
        if data.get('exam_score', Decimal('0')) > exam_max:
            raise serializers.ValidationError(
                f'Exam score exceeds configured exam max ({exam_max}).'
            )
        return data


class BulkScoreEntrySerializer(serializers.Serializer):
    """
    Bulk score entry for a subject: list of student scores.
    POST /results/sheets/<id>/scores/bulk/
    """
    subject = serializers.UUIDField()
    scores = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=500,
    )

    def validate_scores(self, value):
        required = {'student_id'}
        for i, row in enumerate(value):
            missing = required - set(row.keys())
            if missing:
                raise serializers.ValidationError(
                    f'Row #{i}: missing fields {missing}'
                )
        return value


# ─────────────────────────────────────────────────────────────────────────────
# REPORT CARD
# ─────────────────────────────────────────────────────────────────────────────

class SubjectScoreLineSerializer(serializers.ModelSerializer):
    """Compact score line used inside a report card."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    is_pass = serializers.ReadOnlyField()

    class Meta:
        model = StudentScore
        fields = [
            'subject', 'subject_name', 'subject_code',
            'ca1_score', 'ca2_score', 'ca3_score', 'exam_score',
            'total_ca', 'total_score', 'percentage',
            'grade', 'grade_remark', 'grade_points',
            'is_absent', 'is_pass',
        ]


class ReportCardSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    scores = serializers.SerializerMethodField()
    classroom_name = serializers.CharField(
        source='result_sheet.classroom.name', read_only=True
    )
    term_name = serializers.CharField(
        source='result_sheet.term.name', read_only=True
    )
    academic_year = serializers.CharField(
        source='result_sheet.term.academic_year.name', read_only=True
    )
    result_sheet_status = serializers.CharField(
        source='result_sheet.status', read_only=True
    )
    next_term_begins = serializers.DateField(
        source='result_sheet.next_term_begins', read_only=True
    )
    school_principal_remark = serializers.CharField(
        source='result_sheet.principal_remark', read_only=True
    )

    class Meta:
        model = ReportCard
        fields = [
            'id', 'student',
            'classroom_name', 'term_name', 'academic_year',
            'result_sheet', 'result_sheet_status',
            'total_score', 'average_score',
            'subjects_offered', 'subjects_passed', 'subjects_failed',
            'class_position', 'out_of',
            'class_teacher_remark', 'principal_remark',
            'school_principal_remark',
            'days_present', 'days_absent', 'days_in_term',
            'punctuality', 'neatness', 'attentiveness', 'sports',
            'next_term_begins',
            'scores', 'computed_at',
        ]
        read_only_fields = [
            'id', 'total_score', 'average_score',
            'subjects_offered', 'subjects_passed', 'subjects_failed',
            'class_position', 'out_of', 'computed_at',
        ]

    def get_scores(self, obj):
        scores = StudentScore.objects.filter(
            result_sheet=obj.result_sheet,
            student=obj.student,
        ).select_related('subject').order_by('subject__name')
        return SubjectScoreLineSerializer(scores, many=True).data


class ReportCardUpdateSerializer(serializers.ModelSerializer):
    """Teacher/admin can update remarks and attendance."""

    class Meta:
        model = ReportCard
        fields = [
            'class_teacher_remark', 'principal_remark',
            'days_present', 'days_absent', 'days_in_term',
            'punctuality', 'neatness', 'attentiveness', 'sports',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS  (read-only computed responses)
# ─────────────────────────────────────────────────────────────────────────────

class SubjectAnalyticsSerializer(serializers.Serializer):
    """Per-subject analytics within a result sheet."""
    subject_id = serializers.UUIDField()
    subject_name = serializers.CharField()
    subject_code = serializers.CharField()
    students_scored = serializers.IntegerField()
    highest_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    lowest_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    pass_count = serializers.IntegerField()
    fail_count = serializers.IntegerField()
    pass_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    grade_distribution = serializers.DictField()


class ClassAnalyticsSerializer(serializers.Serializer):
    """Overall class analytics for a result sheet."""
    result_sheet_id = serializers.UUIDField()
    classroom_name = serializers.CharField()
    term_name = serializers.CharField()
    total_students = serializers.IntegerField()
    subjects = SubjectAnalyticsSerializer(many=True)
    top_students = serializers.ListField(child=serializers.DictField())
    class_average = serializers.DecimalField(max_digits=5, decimal_places=2)
    overall_pass_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class StudentTrendSerializer(serializers.Serializer):
    """Student performance trend across multiple terms."""
    student_id = serializers.UUIDField()
    student_name = serializers.CharField()
    terms = serializers.ListField(child=serializers.DictField())


# ─────────────────────────────────────────────────────────────────────────────
# SCORE ENTRY BATCH
# ─────────────────────────────────────────────────────────────────────────────

class ScoreEntryBatchSerializer(serializers.ModelSerializer):
    entered_by_name = serializers.CharField(source='entered_by.full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = ScoreEntryBatch
        fields = [
            'id', 'subject', 'subject_name',
            'entered_by', 'entered_by_name',
            'scores_entered', 'scores_updated', 'created_at',
        ]
        read_only_fields = fields
