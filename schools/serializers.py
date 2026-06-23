"""
Serializers for the schools app.
"""

from rest_framework import serializers

from .models import (
    School, SchoolMembership, SchoolSettings,
    AcademicSession, AcademicYear, Term,
    Department, ClassRoom, ClassLevel, StudentClassAssignment,
    SchoolRegistration, SchoolVerificationToken,
)


# ─────────────────────────────────────────────────────────────────────────────
# School
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Membership
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# School Settings / Profile
# ─────────────────────────────────────────────────────────────────────────────

class SchoolSettingsSerializer(serializers.ModelSerializer):
    """Serializer for SchoolSettings model (includes school profile fields)."""

    current_session_name = serializers.CharField(
        source='current_session.name', read_only=True, default=None
    )

    class Meta:
        model = SchoolSettings
        fields = [
            'id',
            # Profile
            'principal_name', 'motto', 'current_session', 'current_session_name',
            # Operational
            'timezone', 'grading_system', 'grading_scale',
            'academic_year_start_month', 'allow_parent_access',
            'exam_proctoring_enabled', 'max_login_attempts',
            'session_timeout_minutes',
        ]
        read_only_fields = ['id', 'current_session_name']


class SchoolProfileSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer combining School + SchoolSettings for the
    'school profile' page that admins can edit.
    """

    principal_name = serializers.SerializerMethodField()
    motto = serializers.SerializerMethodField()
    current_session = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = [
            'id', 'name', 'slug', 'email', 'phone', 'address',
            'city', 'state', 'country', 'logo', 'website',
            'principal_name', 'motto', 'current_session',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_principal_name(self, obj):
        try:
            return obj.settings.principal_name
        except SchoolSettings.DoesNotExist:
            return None

    def get_motto(self, obj):
        try:
            return obj.settings.motto
        except SchoolSettings.DoesNotExist:
            return None

    def get_current_session(self, obj):
        try:
            s = obj.settings.current_session
            return {'id': str(s.id), 'name': s.name} if s else None
        except SchoolSettings.DoesNotExist:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Academic Session
# ─────────────────────────────────────────────────────────────────────────────

class AcademicSessionSerializer(serializers.ModelSerializer):
    """Serializer for AcademicSession model."""

    class Meta:
        model = AcademicSession
        fields = [
            'id', 'name', 'start_date', 'end_date',
            'is_current', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ─────────────────────────────────────────────────────────────────────────────
# Academic Year & Terms  (legacy – kept for backward compat)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Class Level
# ─────────────────────────────────────────────────────────────────────────────

class ClassLevelSerializer(serializers.ModelSerializer):
    """Serializer for ClassLevel model."""

    name = serializers.CharField(source='name', read_only=True)
    code_display = serializers.CharField(source='get_code_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = ClassLevel
        fields = [
            'id', 'code', 'code_display', 'display_name', 'name',
            'category', 'category_display', 'order', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'category', 'order', 'created_at', 'name', 'code_display', 'category_display']


# ─────────────────────────────────────────────────────────────────────────────
# Department
# ─────────────────────────────────────────────────────────────────────────────

class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model."""

    head_name = serializers.CharField(source='head.full_name', read_only=True, default=None)

    class Meta:
        model = Department
        fields = ['id', 'name', 'head', 'head_name', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


# ─────────────────────────────────────────────────────────────────────────────
# Classroom
# ─────────────────────────────────────────────────────────────────────────────

class ClassRoomSerializer(serializers.ModelSerializer):
    """Serializer for ClassRoom model."""

    class_teacher_name = serializers.CharField(
        source='class_teacher.full_name', read_only=True, default=None
    )
    academic_year_name = serializers.CharField(
        source='academic_year.name', read_only=True
    )
    class_level_code = serializers.CharField(
        source='class_level.code', read_only=True, default=None
    )
    class_level_name = serializers.CharField(
        source='class_level.name', read_only=True, default=None
    )
    student_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClassRoom
        fields = [
            'id', 'name', 'grade_level',
            'class_level', 'class_level_code', 'class_level_name',
            'academic_year', 'academic_year_name',
            'class_teacher', 'class_teacher_name',
            'max_students', 'student_count', 'is_active',
        ]
        read_only_fields = ['id', 'student_count']


class ClassRoomDetailSerializer(ClassRoomSerializer):
    """Extended classroom serializer that includes the student list."""

    students = serializers.SerializerMethodField()

    class Meta(ClassRoomSerializer.Meta):
        fields = ClassRoomSerializer.Meta.fields + ['students']

    def get_students(self, obj):
        from accounts.serializers import UserBasicSerializer
        return UserBasicSerializer(obj.students, many=True).data


class AssignTeacherSerializer(serializers.Serializer):
    """Assign a class teacher to a classroom."""

    teacher_id = serializers.UUIDField(required=True)


# ─────────────────────────────────────────────────────────────────────────────
# Student Class Assignment
# ─────────────────────────────────────────────────────────────────────────────

class StudentClassAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for StudentClassAssignment model."""

    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    session_name = serializers.CharField(source='academic_session.name', read_only=True)
    assigned_by_name = serializers.CharField(
        source='assigned_by.full_name', read_only=True, default=None
    )

    class Meta:
        model = StudentClassAssignment
        fields = [
            'id', 'student', 'student_name', 'student_email',
            'classroom', 'classroom_name',
            'academic_session', 'session_name',
            'status', 'assigned_by', 'assigned_by_name',
            'assigned_at', 'notes',
        ]
        read_only_fields = [
            'id', 'assigned_at', 'student_name', 'student_email',
            'classroom_name', 'session_name', 'assigned_by_name',
        ]


class BulkEnrollSerializer(serializers.Serializer):
    """Bulk-enroll multiple students into a classroom for a session."""

    student_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        help_text='List of student user UUIDs to enroll.',
    )
    classroom_id = serializers.UUIDField(required=True)
    academic_session_id = serializers.UUIDField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class EnrollStudentSerializer(serializers.Serializer):
    """Enroll a single student into a classroom for a session."""

    student_id = serializers.UUIDField(required=True)
    classroom_id = serializers.UUIDField(required=True)
    academic_session_id = serializers.UUIDField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7A — School Registration & Onboarding
# ─────────────────────────────────────────────────────────────────────────────

class SchoolRegistrationSerializer(serializers.ModelSerializer):
    """
    Read serializer for SchoolRegistration — used in status/detail responses.
    Excludes the hashed password field.
    """

    onboarding_progress = serializers.ReadOnlyField()
    is_email_verified = serializers.ReadOnlyField()

    class Meta:
        model = SchoolRegistration
        fields = [
            'id', 'school_name', 'school_email', 'phone',
            'address', 'city', 'state', 'country', 'website',
            'principal_name', 'principal_email', 'principal_phone',
            'logo', 'motto',
            'academic_year_start_month', 'grading_system', 'timezone',
            'admin_first_name', 'admin_last_name', 'admin_email',
            'status', 'onboarding_progress', 'is_email_verified',
            'school', 'ip_address', 'created_at', 'updated_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'status', 'onboarding_progress', 'is_email_verified',
            'school', 'ip_address', 'created_at', 'updated_at', 'completed_at',
        ]


class SchoolRegistrationInitSerializer(serializers.Serializer):
    """
    Step 0 — Initial registration: school name + email.
    Creates the SchoolRegistration record and sends verification email.
    """

    school_name = serializers.CharField(max_length=200)
    school_email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_school_email(self, value):
        if SchoolRegistration.objects.filter(
            school_email=value,
            status__in=[
                SchoolRegistration.Status.PENDING_VERIFICATION,
                SchoolRegistration.Status.EMAIL_VERIFIED,
                SchoolRegistration.Status.ONBOARDING_STEP_1,
                SchoolRegistration.Status.ONBOARDING_STEP_2,
                SchoolRegistration.Status.ONBOARDING_STEP_3,
                SchoolRegistration.Status.ONBOARDING_STEP_4,
                SchoolRegistration.Status.COMPLETED,
            ]
        ).exists():
            raise serializers.ValidationError(
                'A registration with this email already exists.'
            )
        return value.lower()


class VerifyEmailSerializer(serializers.Serializer):
    """Step 1 — Verify email via token."""

    token = serializers.CharField(max_length=128)


class OnboardingStep1Serializer(serializers.Serializer):
    """Step 2 — Basic school info."""

    school_name = serializers.CharField(max_length=200)
    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, default='Nigeria')
    website = serializers.URLField(required=False, allow_blank=True)
    principal_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    principal_email = serializers.EmailField(required=False, allow_blank=True)
    principal_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)


class OnboardingStep2Serializer(serializers.Serializer):
    """Step 3 — Logo & branding."""

    logo = serializers.ImageField(required=False)
    motto = serializers.CharField(max_length=255, required=False, allow_blank=True)


class OnboardingStep3Serializer(serializers.Serializer):
    """Step 4 — Academic setup."""

    academic_year_start_month = serializers.IntegerField(min_value=1, max_value=12, default=9)
    grading_system = serializers.ChoiceField(
        choices=SchoolSettings.GradingSystem.choices,
        default=SchoolSettings.GradingSystem.PERCENTAGE,
    )
    timezone = serializers.CharField(max_length=50, default='Africa/Lagos')


class OnboardingStep4Serializer(serializers.Serializer):
    """Step 5 — Admin account creation."""

    admin_first_name = serializers.CharField(max_length=100)
    admin_last_name = serializers.CharField(max_length=100)
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(
        min_length=8,
        write_only=True,
        style={'input_type': 'password'},
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    def validate(self, data):
        if data['admin_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return data


class CompleteRegistrationSerializer(serializers.Serializer):
    """
    Final step — confirm and activate the school.
    Validates that all required onboarding fields are present.
    """

    registration_id = serializers.UUIDField()
