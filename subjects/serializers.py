"""
Serializers for the subjects app.
"""

from rest_framework import serializers

from .models import (
    Subject, Topic, SubjectTeacherAssignment,
    Enrollment, Prerequisite, ClassSubject,
    Timetable, TimetableSlot,
)
from core.mixins import DynamicFieldsMixin


class TopicSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Serializer for Topic model."""

    subtopics = serializers.SerializerMethodField()
    depth = serializers.ReadOnlyField()

    class Meta:
        model = Topic
        fields = [
            'id', 'subject', 'parent_topic', 'name', 'description',
            'order', 'is_active', 'subtopics', 'depth', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'depth']

    def get_subtopics(self, obj):
        """Get child topics recursively (max 2 levels deep)."""
        if obj.subtopics.exists():
            return TopicSerializer(
                obj.subtopics.filter(is_active=True),
                many=True,
                context=self.context,
            ).data
        return []


class SubjectSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Serializer for Subject model."""

    department_name = serializers.CharField(
        source='department.name', read_only=True, default=None
    )
    topic_count = serializers.SerializerMethodField()
    enrollment_count = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'description', 'department',
            'department_name', 'credit_units', 'is_elective',
            'is_active', 'topic_count', 'enrollment_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_topic_count(self, obj):
        return obj.topics.filter(is_active=True, parent_topic__isnull=True).count()

    def get_enrollment_count(self, obj):
        return obj.enrollments.filter(status='active').count()


class SubjectCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a subject."""

    class Meta:
        model = Subject
        fields = [
            'name', 'code', 'description', 'department',
            'credit_units', 'is_elective',
        ]

    def validate_code(self, value):
        """Ensure code is unique within the school."""
        school = self.context['request'].school
        if Subject.objects.filter(school=school, code=value).exists():
            raise serializers.ValidationError(
                f'A subject with code "{value}" already exists in this school.'
            )
        return value.upper()


class SubjectDetailSerializer(SubjectSerializer):
    """Detailed serializer for Subject with topics."""

    topics = TopicSerializer(many=True, read_only=True, source='topics_root')

    class Meta(SubjectSerializer.Meta):
        fields = SubjectSerializer.Meta.fields + ['topics']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Only include root-level topics
        data['topics'] = TopicSerializer(
            instance.topics.filter(is_active=True, parent_topic__isnull=True),
            many=True,
            context=self.context,
        ).data
        return data


class SubjectTeacherAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for teacher assignments."""

    teacher_name = serializers.CharField(source='teacher.full_name', read_only=True)
    teacher_email = serializers.CharField(source='teacher.email', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = SubjectTeacherAssignment
        fields = [
            'id', 'subject', 'teacher', 'classroom', 'term',
            'is_primary', 'teacher_name', 'teacher_email',
            'subject_name', 'classroom_name', 'term_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class EnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for student enrollments."""

    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'student', 'subject', 'classroom', 'term',
            'status', 'enrolled_at', 'dropped_at',
            'student_name', 'student_email', 'subject_name',
            'subject_code', 'classroom_name', 'term_name',
            'created_at',
        ]
        read_only_fields = ['id', 'enrolled_at', 'dropped_at', 'created_at']


class EnrollStudentSerializer(serializers.Serializer):
    """Serializer for enrolling a student in a subject."""

    student_id = serializers.UUIDField()
    classroom_id = serializers.UUIDField()
    term_id = serializers.UUIDField()


class BulkEnrollSerializer(serializers.Serializer):
    """Serializer for bulk enrolling students."""

    student_ids = serializers.ListField(child=serializers.UUIDField())
    classroom_id = serializers.UUIDField()
    term_id = serializers.UUIDField()


class PrerequisiteSerializer(serializers.ModelSerializer):
    """Serializer for subject prerequisites."""

    required_subject_name = serializers.CharField(
        source='required_subject.name', read_only=True
    )
    required_subject_code = serializers.CharField(
        source='required_subject.code', read_only=True
    )

    class Meta:
        model = Prerequisite
        fields = [
            'id', 'subject', 'required_subject', 'minimum_grade',
            'required_subject_name', 'required_subject_code',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ClassSubjectSerializer(serializers.ModelSerializer):
    """Serializer for class-subject assignments."""

    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = ClassSubject
        fields = [
            'id', 'classroom', 'subject', 'term', 'is_compulsory',
            'subject_name', 'subject_code', 'classroom_name', 'term_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TimetableSerializer(serializers.ModelSerializer):
    """Serializer for timetables."""

    term_name = serializers.CharField(source='term.name', read_only=True)
    slot_count = serializers.SerializerMethodField()

    class Meta:
        model = Timetable
        fields = [
            'id', 'term', 'name', 'is_active', 'term_name',
            'slot_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_slot_count(self, obj):
        return obj.slots.count()


class TimetableSlotSerializer(serializers.ModelSerializer):
    """Serializer for timetable slots."""

    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    teacher_name = serializers.CharField(
        source='teacher.full_name', read_only=True, default=None
    )
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = TimetableSlot
        fields = [
            'id', 'timetable', 'subject', 'classroom', 'teacher',
            'day_of_week', 'day_name', 'start_time', 'end_time',
            'room_name', 'subject_name', 'subject_code',
            'classroom_name', 'teacher_name', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
