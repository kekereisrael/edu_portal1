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


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — Teacher Management
# ═════════════════════════════════════════════════════════════════════════════

class TeacherProfileSerializer(serializers.ModelSerializer):
    """
    Detailed teacher record for the school admin teacher-management views.
    Includes user fields + membership info + assigned subjects/classes.
    """

    user_id       = serializers.UUIDField(source='user.id', read_only=True)
    email         = serializers.EmailField(source='user.email', read_only=True)
    first_name    = serializers.CharField(source='user.first_name', read_only=True)
    last_name     = serializers.CharField(source='user.last_name', read_only=True)
    full_name     = serializers.SerializerMethodField()
    phone         = serializers.CharField(source='user.phone', read_only=True, default=None)
    avatar        = serializers.ImageField(source='user.avatar', read_only=True, default=None)
    assigned_subjects = serializers.SerializerMethodField()
    assigned_classrooms = serializers.SerializerMethodField()

    class Meta:
        model = SchoolMembership
        fields = [
            'id', 'user_id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'avatar', 'role', 'joined_at', 'is_active',
            'assigned_subjects', 'assigned_classrooms',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_assigned_subjects(self, obj):
        """Return subjects this teacher is assigned to in the current school."""
        try:
            from subjects.models import SubjectTeacherAssignment
            assignments = SubjectTeacherAssignment.objects.filter(
                teacher=obj.user,
                subject__school=obj.school,
            ).select_related('subject').distinct('subject')
            return [
                {'id': str(a.subject.id), 'name': a.subject.name, 'code': a.subject.code}
                for a in assignments
            ]
        except Exception:
            return []

    def get_assigned_classrooms(self, obj):
        """Return classrooms where this teacher is the class teacher."""
        classrooms = ClassRoom.objects.filter(
            school=obj.school,
            class_teacher=obj.user,
            is_active=True,
        )
        return [{'id': str(c.id), 'name': c.name} for c in classrooms]


class CreateTeacherSerializer(serializers.Serializer):
    """Create or invite a teacher to the school."""

    email      = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name  = serializers.CharField(max_length=100)
    phone      = serializers.CharField(max_length=20, required=False, allow_blank=True)
    send_welcome_email = serializers.BooleanField(default=True)


class UpdateTeacherSerializer(serializers.Serializer):
    """Update a teacher's basic info (name, phone)."""

    first_name = serializers.CharField(max_length=100, required=False)
    last_name  = serializers.CharField(max_length=100, required=False)
    phone      = serializers.CharField(max_length=20, required=False, allow_blank=True)


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — Student Management
# ═════════════════════════════════════════════════════════════════════════════

class StudentProfileSerializer(serializers.ModelSerializer):
    """
    Detailed student record for the school admin student-management views.
    Includes user fields + StudentProfile + current class assignment.
    """

    user_id       = serializers.UUIDField(source='user.id', read_only=True)
    email         = serializers.EmailField(source='user.email', read_only=True)
    first_name    = serializers.CharField(source='user.first_name', read_only=True)
    last_name     = serializers.CharField(source='user.last_name', read_only=True)
    full_name     = serializers.SerializerMethodField()
    phone         = serializers.CharField(source='user.phone', read_only=True, default=None)
    avatar        = serializers.ImageField(source='user.avatar', read_only=True, default=None)
    admission_number   = serializers.SerializerMethodField()
    date_of_birth      = serializers.SerializerMethodField()
    gender             = serializers.SerializerMethodField()
    guardian_name      = serializers.SerializerMethodField()
    guardian_phone     = serializers.SerializerMethodField()
    guardian_email     = serializers.SerializerMethodField()
    guardian_relationship = serializers.SerializerMethodField()
    current_class      = serializers.SerializerMethodField()
    profile_picture    = serializers.SerializerMethodField()

    class Meta:
        model = SchoolMembership
        fields = [
            'id', 'user_id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'avatar', 'profile_picture',
            'admission_number', 'date_of_birth', 'gender',
            'guardian_name', 'guardian_phone', 'guardian_email', 'guardian_relationship',
            'current_class', 'role', 'joined_at', 'is_active',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def _get_student_profile(self, obj):
        try:
            from accounts.models import StudentProfile
            return StudentProfile.objects.get(user=obj.user, school=obj.school)
        except Exception:
            return None

    def get_admission_number(self, obj):
        sp = self._get_student_profile(obj)
        return sp.admission_number if sp else None

    def get_date_of_birth(self, obj):
        sp = self._get_student_profile(obj)
        return sp.date_of_birth.isoformat() if sp and sp.date_of_birth else None

    def get_gender(self, obj):
        sp = self._get_student_profile(obj)
        return sp.gender if sp else None

    def get_guardian_name(self, obj):
        sp = self._get_student_profile(obj)
        return sp.guardian_name if sp else None

    def get_guardian_phone(self, obj):
        sp = self._get_student_profile(obj)
        return sp.guardian_phone if sp else None

    def get_guardian_email(self, obj):
        sp = self._get_student_profile(obj)
        return sp.guardian_email if sp else None

    def get_guardian_relationship(self, obj):
        sp = self._get_student_profile(obj)
        return sp.guardian_relationship if sp else None

    def get_profile_picture(self, obj):
        sp = self._get_student_profile(obj)
        if sp and sp.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(sp.profile_picture.url)
            return sp.profile_picture.url
        return None

    def get_current_class(self, obj):
        assignment = StudentClassAssignment.objects.filter(
            school=obj.school,
            student=obj.user,
            status=StudentClassAssignment.Status.ACTIVE,
        ).select_related('classroom', 'academic_session').first()
        if assignment:
            return {
                'assignment_id': str(assignment.id),
                'classroom_id': str(assignment.classroom.id),
                'classroom_name': assignment.classroom.name,
                'session_id': str(assignment.academic_session.id),
                'session_name': assignment.academic_session.name,
            }
        return None


class CreateStudentSerializer(serializers.Serializer):
    """Create a new student in the school."""

    email          = serializers.EmailField()
    first_name     = serializers.CharField(max_length=100)
    last_name      = serializers.CharField(max_length=100)
    phone          = serializers.CharField(max_length=20, required=False, allow_blank=True)
    admission_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    date_of_birth  = serializers.DateField(required=False, allow_null=True)
    gender         = serializers.ChoiceField(
        choices=['male', 'female', 'other'],
        required=False,
        allow_blank=True,
    )
    guardian_name  = serializers.CharField(max_length=200, required=False, allow_blank=True)
    guardian_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    guardian_email = serializers.EmailField(required=False, allow_blank=True)
    guardian_relationship = serializers.CharField(max_length=50, required=False, allow_blank=True)
    send_welcome_email = serializers.BooleanField(default=False)


class UpdateStudentSerializer(serializers.Serializer):
    """Update a student's profile info."""

    first_name     = serializers.CharField(max_length=100, required=False)
    last_name      = serializers.CharField(max_length=100, required=False)
    phone          = serializers.CharField(max_length=20, required=False, allow_blank=True)
    admission_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    date_of_birth  = serializers.DateField(required=False, allow_null=True)
    gender         = serializers.ChoiceField(
        choices=['male', 'female', 'other'],
        required=False,
        allow_blank=True,
    )
    guardian_name  = serializers.CharField(max_length=200, required=False, allow_blank=True)
    guardian_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    guardian_email = serializers.EmailField(required=False, allow_blank=True)
    guardian_relationship = serializers.CharField(max_length=50, required=False, allow_blank=True)


class BulkStudentUploadSerializer(serializers.Serializer):
    """Bulk upload students via CSV/JSON list."""

    students = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=500,
        help_text='List of student objects with email, first_name, last_name, etc.',
    )


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — School Dashboard, Member Management & Staff Invite
# ═════════════════════════════════════════════════════════════════════════════

class SchoolMemberDetailSerializer(serializers.ModelSerializer):
    """
    Detailed membership record including user profile fields.
    Used by the school admin member-management endpoints.
    """

    user_id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = SchoolMembership
        fields = [
            'id', 'user_id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'joined_at', 'is_active',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.email


class InviteStaffSerializer(serializers.Serializer):
    """
    Invite a teacher or admin to the school.
    If the user already exists (by email) they are added directly;
    otherwise a new user account is created with a temporary password.
    """

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(
        choices=[
            (SchoolMembership.SchoolRole.TEACHER, 'Teacher'),
            (SchoolMembership.SchoolRole.SCHOOL_ADMIN, 'School Admin'),
        ]
    )
    send_welcome_email = serializers.BooleanField(default=True)
