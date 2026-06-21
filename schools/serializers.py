"""
Serializers for the schools app.
"""

from rest_framework import serializers

from .models import (
    School, SchoolMembership, SchoolSettings,
    AcademicYear, Term, Department, ClassRoom,
)


class SchoolSerializer(serializers.ModelSerializer):
    """Serializer for School model."""

    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            'id', 'name', 'slug', 'email', 'phone', 'address',
            'city', 'state', 'country', 'logo', 'website',
            'owner', 'owner_email', 'is_active', 'member_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'owner', 'is_active', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()


class SchoolCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new school."""

    class Meta:
        model = School
        fields = ['name', 'email', 'phone', 'address', 'city', 'state', 'country', 'website']


class SchoolMembershipSerializer(serializers.ModelSerializer):
    """Serializer for SchoolMembership model."""

    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = SchoolMembership
        fields = [
            'id', 'school', 'school_name', 'user', 'user_email',
            'user_name', 'role', 'joined_at', 'is_active',
        ]
        read_only_fields = ['id', 'joined_at']


class AddMemberSerializer(serializers.Serializer):
    """Serializer for adding a member to a school."""

    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(choices=SchoolMembership.SchoolRole.choices)


class SchoolSettingsSerializer(serializers.ModelSerializer):
    """Serializer for SchoolSettings model."""

    class Meta:
        model = SchoolSettings
        fields = [
            'id', 'timezone', 'grading_system', 'grading_scale',
            'academic_year_start_month', 'allow_parent_access',
            'exam_proctoring_enabled', 'max_login_attempts',
            'session_timeout_minutes',
        ]
        read_only_fields = ['id']


class AcademicYearSerializer(serializers.ModelSerializer):
    """Serializer for AcademicYear model."""

    terms = serializers.SerializerMethodField()

    class Meta:
        model = AcademicYear
        fields = [
            'id', 'name', 'start_date', 'end_date',
            'is_current', 'terms', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_terms(self, obj):
        return TermSerializer(obj.terms.all(), many=True).data


class TermSerializer(serializers.ModelSerializer):
    """Serializer for Term model."""

    class Meta:
        model = Term
        fields = [
            'id', 'academic_year', 'name', 'start_date',
            'end_date', 'is_current', 'order',
        ]
        read_only_fields = ['id']


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model."""

    head_name = serializers.CharField(source='head.full_name', read_only=True, default=None)

    class Meta:
        model = Department
        fields = ['id', 'name', 'head', 'head_name', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class ClassRoomSerializer(serializers.ModelSerializer):
    """Serializer for ClassRoom model."""

    class_teacher_name = serializers.CharField(
        source='class_teacher.full_name', read_only=True, default=None
    )
    academic_year_name = serializers.CharField(
        source='academic_year.name', read_only=True
    )

    class Meta:
        model = ClassRoom
        fields = [
            'id', 'name', 'grade_level', 'academic_year',
            'academic_year_name', 'class_teacher', 'class_teacher_name',
            'max_students', 'is_active',
        ]
        read_only_fields = ['id']
