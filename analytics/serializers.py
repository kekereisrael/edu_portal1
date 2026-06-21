"""
Serializers for the analytics app.
"""

from rest_framework import serializers

from .models import (
    StudentAnalytics, SubjectAnalytics, SchoolAnalytics,
    LearningPath, LearningPathStep, AIUsageRecord,
)


class StudentAnalyticsSerializer(serializers.ModelSerializer):
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = StudentAnalytics
        fields = [
            'id', 'term', 'term_name', 'average_score', 'total_exams_taken',
            'total_materials_completed', 'total_time_spent_minutes',
            'attendance_rate', 'rank_in_class', 'improvement_trend',
            'last_calculated_at',
        ]
        read_only_fields = fields


class SubjectAnalyticsSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = SubjectAnalytics
        fields = [
            'id', 'subject', 'subject_name', 'term', 'term_name',
            'average_score', 'pass_rate', 'total_students',
            'highest_score', 'lowest_score', 'last_calculated_at',
        ]
        read_only_fields = fields


class SchoolAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolAnalytics
        fields = [
            'id', 'total_students', 'total_teachers', 'total_subjects',
            'total_exams_created', 'average_pass_rate',
            'storage_used_bytes', 'ai_credits_used', 'last_calculated_at',
        ]
        read_only_fields = fields


class LearningPathStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningPathStep
        fields = [
            'id', 'order', 'step_type', 'title', 'description',
            'related_material', 'related_exam', 'related_topic',
            'is_completed', 'completed_at',
        ]
        read_only_fields = ['id']


class LearningPathSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    progress_percent = serializers.ReadOnlyField()

    class Meta:
        model = LearningPath
        fields = [
            'id', 'student', 'student_name', 'subject', 'subject_name',
            'title', 'description', 'is_ai_generated', 'status',
            'progress_percent', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class LearningPathDetailSerializer(LearningPathSerializer):
    steps = LearningPathStepSerializer(many=True, read_only=True)

    class Meta(LearningPathSerializer.Meta):
        fields = LearningPathSerializer.Meta.fields + ['steps']


class AIUsageRecordSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = AIUsageRecord
        fields = [
            'id', 'user', 'user_email', 'usage_type', 'credits_consumed',
            'input_tokens', 'output_tokens', 'model_used',
            'estimated_cost_usd', 'created_at',
        ]
        read_only_fields = fields
