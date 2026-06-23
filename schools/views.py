"""
Views for the schools app.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from .models import (
    School, SchoolMembership, SchoolSettings,
    AcademicSession, AcademicYear, Term,
    Department, ClassRoom, ClassLevel, StudentClassAssignment,
    SchoolBranding, ClassPromotion, AuditLog,
)
from .permissions import HasSchoolContext, IsSchoolAdmin, IsPlatformAdmin
from .serializers import (
    SchoolSerializer, SchoolCreateSerializer,
    SchoolMembershipSerializer, AddMemberSerializer,
    SchoolSettingsSerializer,
    AcademicSessionSerializer,
    AcademicYearSerializer, TermSerializer,
    DepartmentSerializer,
    ClassRoomSerializer, ClassRoomDetailSerializer, AssignTeacherSerializer,
    ClassLevelSerializer,
    StudentClassAssignmentSerializer, BulkEnrollSerializer, EnrollStudentSerializer,
)

UserModel = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _seed_class_levels(school):
    """Create the six default JSS/SSS class levels for a new school."""
    defaults = [
        (ClassLevel.LevelCode.JSS1, 1),
        (ClassLevel.LevelCode.JSS2, 2),
        (ClassLevel.LevelCode.JSS3, 3),
        (ClassLevel.LevelCode.SSS1, 4),
        (ClassLevel.LevelCode.SSS2, 5),
        (ClassLevel.LevelCode.SSS3, 6),
    ]
    for code, order in defaults:
        ClassLevel.objects.get_or_create(
            school=school,
            code=code,
            defaults={'order': order},
        )


# ─────────────────────────────────────────────────────────────────────────────
# School CRUD
# ─────────────────────────────────────────────────────────────────────────────

class SchoolCreateView(generics.CreateAPIView):
    """Create a new school (registers the user as school admin)."""

    serializer_class = SchoolCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        school = serializer.save(owner=self.request.user)
        SchoolSettings.objects.create(school=school)
        SchoolMembership.objects.create(
            school=school,
            user=self.request.user,
            role=SchoolMembership.SchoolRole.SCHOOL_ADMIN,
        )
        if self.request.user.role != User.Role.SCHOOL_ADMIN:
            self.request.user.role = User.Role.SCHOOL_ADMIN
            self.request.user.save(update_fields=['role'])
        _seed_class_levels(school)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        school = School.objects.get(pk=serializer.instance.pk)
        return Response(SchoolSerializer(school).data, status=status.HTTP_201_CREATED)


class SchoolDetailView(generics.RetrieveUpdateAPIView):
    """Get or update the current school details."""

    serializer_class = SchoolSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_object(self):
        return self.request.school

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            return [permissions.IsAuthenticated(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


class SchoolListView(generics.ListAPIView):
    """List all schools (platform admin only)."""

    serializer_class = SchoolSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]
    queryset = School.objects.all()
    filterset_fields = ['is_active', 'state', 'country']
    search_fields = ['name', 'email', 'city']


# ─────────────────────────────────────────────────────────────────────────────
# School Profile  (combined School + SchoolSettings for admin editing)
# ─────────────────────────────────────────────────────────────────────────────

class SchoolProfileView(APIView):
    """
    GET  – Returns combined school profile (school fields + settings fields).
    PATCH – Admin can update school fields AND settings fields in one request.
    """

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            return [permissions.IsAuthenticated(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def _build_response(self, school, settings_obj):
        data = SchoolSerializer(school).data
        data['principal_name'] = settings_obj.principal_name
        data['motto'] = settings_obj.motto
        data['current_session'] = (
            AcademicSessionSerializer(settings_obj.current_session).data
            if settings_obj.current_session else None
        )
        return data

    def get(self, request):
        school = request.school
        settings_obj, _ = SchoolSettings.objects.get_or_create(school=school)
        return Response(self._build_response(school, settings_obj))

    def patch(self, request):
        school = request.school
        settings_obj, _ = SchoolSettings.objects.get_or_create(school=school)

        school_fields = [
            'name', 'email', 'phone', 'address',
            'city', 'state', 'country', 'website', 'logo',
        ]
        school_data = {k: v for k, v in request.data.items() if k in school_fields}
        if school_data:
            s = SchoolSerializer(school, data=school_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()

        settings_fields = [
            'principal_name', 'motto', 'current_session',
            'timezone', 'grading_system', 'grading_scale',
            'academic_year_start_month', 'allow_parent_access',
            'exam_proctoring_enabled', 'max_login_attempts', 'session_timeout_minutes',
        ]
        settings_data = {k: v for k, v in request.data.items() if k in settings_fields}
        if settings_data:
            ss = SchoolSettingsSerializer(settings_obj, data=settings_data, partial=True)
            ss.is_valid(raise_exception=True)
            ss.save()

        school.refresh_from_db()
        settings_obj.refresh_from_db()
        return Response(self._build_response(school, settings_obj))


# ─────────────────────────────────────────────────────────────────────────────
# Membership Management
# ─────────────────────────────────────────────────────────────────────────────

class MemberListView(generics.ListAPIView):
    """List all members of the current school."""

    serializer_class = SchoolMembershipSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        qs = SchoolMembership.objects.filter(
            school=self.request.school
        ).select_related('user', 'school')

        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')

        return qs


class AddMemberView(APIView):
    """Add a member to the current school."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        role = serializer.validated_data['role']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'detail': f'No user found with email {email}. They must register first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if SchoolMembership.objects.filter(school=request.school, user=user).exists():
            return Response(
                {'detail': 'User is already a member of this school.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = SchoolMembership.objects.create(
            school=request.school, user=user, role=role,
        )
        return Response(SchoolMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class RemoveMemberView(APIView):
    """Remove a member from the current school."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, membership_id):
        membership = get_object_or_404(
            SchoolMembership, id=membership_id, school=request.school
        )
        if membership.user == request.school.owner:
            return Response(
                {'detail': 'Cannot remove the school owner.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership.is_active = False
        membership.save(update_fields=['is_active'])
        return Response({'message': 'Member removed successfully.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# School Settings
# ─────────────────────────────────────────────────────────────────────────────

class SchoolSettingsView(generics.RetrieveUpdateAPIView):
    """Get or update school settings."""

    serializer_class = SchoolSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_object(self):
        settings, _ = SchoolSettings.objects.get_or_create(school=self.request.school)
        return settings


# ─────────────────────────────────────────────────────────────────────────────
# Academic Session
# ─────────────────────────────────────────────────────────────────────────────

class AcademicSessionListCreateView(generics.ListCreateAPIView):
    """List or create academic sessions for the current school."""

    serializer_class = AcademicSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return AcademicSession.objects.filter(school=self.request.school)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class AcademicSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an academic session."""

    serializer_class = AcademicSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return AcademicSession.objects.filter(school=self.request.school)


class SetCurrentSessionView(APIView):
    """
    POST /academic-sessions/<pk>/set-current/
    Mark an academic session as the current one and sync SchoolSettings.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, pk):
        session = get_object_or_404(AcademicSession, pk=pk, school=request.school)
        session.is_current = True
        session.save()

        settings_obj, _ = SchoolSettings.objects.get_or_create(school=request.school)
        settings_obj.current_session = session
        settings_obj.save(update_fields=['current_session'])

        return Response(AcademicSessionSerializer(session).data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Academic Year & Terms  (legacy – kept for backward compat with subjects app)
# ─────────────────────────────────────────────────────────────────────────────

class AcademicYearListCreateView(generics.ListCreateAPIView):
    """List or create academic years for the current school."""

    serializer_class = AcademicYearSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return AcademicYear.objects.filter(school=self.request.school)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class AcademicYearDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an academic year."""

    serializer_class = AcademicYearSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return AcademicYear.objects.filter(school=self.request.school)


class TermListCreateView(generics.ListCreateAPIView):
    """List or create terms for an academic year."""

    serializer_class = TermSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        academic_year_id = self.kwargs.get('academic_year_id')
        return Term.objects.filter(
            academic_year_id=academic_year_id,
            academic_year__school=self.request.school,
        )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        academic_year = get_object_or_404(
            AcademicYear,
            id=self.kwargs['academic_year_id'],
            school=self.request.school,
        )
        serializer.save(academic_year=academic_year)


# ─────────────────────────────────────────────────────────────────────────────
# Departments
# ─────────────────────────────────────────────────────────────────────────────

class DepartmentListCreateView(generics.ListCreateAPIView):
    """List or create departments."""

    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return Department.objects.filter(school=self.request.school)

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a department."""

    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return Department.objects.filter(school=self.request.school)


# ─────────────────────────────────────────────────────────────────────────────
# Class Levels  (JSS1–SSS3)
# ─────────────────────────────────────────────────────────────────────────────

class ClassLevelListView(generics.ListAPIView):
    """
    GET /class-levels/
    List all class levels for the current school.
    Auto-seeds JSS1–SSS3 if none exist.
    Supports ?category=junior|senior filter.
    """

    serializer_class = ClassLevelSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        school = self.request.school
        qs = ClassLevel.objects.filter(school=school)
        if not qs.exists():
            _seed_class_levels(school)
            qs = ClassLevel.objects.filter(school=school)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs.order_by('order')


class ClassLevelDetailView(generics.RetrieveUpdateAPIView):
    """GET or PATCH a class level (e.g. change display_name or is_active)."""

    serializer_class = ClassLevelSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return ClassLevel.objects.filter(school=self.request.school)


# ─────────────────────────────────────────────────────────────────────────────
# Classrooms  (TASK 3 – create, edit, assign teacher, view students)
# ─────────────────────────────────────────────────────────────────────────────

class ClassRoomListCreateView(generics.ListCreateAPIView):
    """List or create classrooms."""

    serializer_class = ClassRoomSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['grade_level', 'class_level', 'academic_year', 'is_active']
    search_fields = ['name', 'grade_level']

    def get_queryset(self):
        return ClassRoom.objects.filter(
            school=self.request.school
        ).select_related('academic_year', 'class_teacher', 'class_level')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class ClassRoomDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a classroom."""

    serializer_class = ClassRoomSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return ClassRoom.objects.filter(school=self.request.school)


class ClassRoomStudentsView(generics.RetrieveAPIView):
    """
    GET /classrooms/<pk>/students/
    Returns classroom details including the full student list.
    """

    serializer_class = ClassRoomDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return ClassRoom.objects.filter(school=self.request.school)


class AssignTeacherView(APIView):
    """
    POST /classrooms/<pk>/assign-teacher/
    Assign (or replace) the class teacher for a classroom.
    Body: { "teacher_id": "<uuid>" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, pk):
        classroom = get_object_or_404(ClassRoom, pk=pk, school=request.school)
        serializer = AssignTeacherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        teacher_id = serializer.validated_data['teacher_id']
        teacher = get_object_or_404(
            UserModel,
            id=teacher_id,
            school_memberships__school=request.school,
            school_memberships__role=SchoolMembership.SchoolRole.TEACHER,
            school_memberships__is_active=True,
        )

        classroom.class_teacher = teacher
        classroom.save(update_fields=['class_teacher'])

        return Response(ClassRoomSerializer(classroom).data, status=status.HTTP_200_OK)


class RemoveTeacherView(APIView):
    """
    POST /classrooms/<pk>/remove-teacher/
    Remove the class teacher assignment from a classroom.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, pk):
        classroom = get_object_or_404(ClassRoom, pk=pk, school=request.school)
        classroom.class_teacher = None
        classroom.save(update_fields=['class_teacher'])
        return Response(ClassRoomSerializer(classroom).data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Subject Assignment  (TASK 4 – Subject→Class, Teacher→Subject)
# ─────────────────────────────────────────────────────────────────────────────

class ClassSubjectListView(APIView):
    """
    GET /classrooms/<pk>/subjects/
    List subjects assigned to a classroom. Optionally filter by ?term=<id>.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get(self, request, pk):
        from subjects.models import ClassSubject
        from subjects.serializers import ClassSubjectSerializer

        classroom = get_object_or_404(ClassRoom, pk=pk, school=request.school)
        qs = ClassSubject.objects.filter(
            classroom=classroom
        ).select_related('subject', 'term')

        term_id = request.query_params.get('term')
        if term_id:
            qs = qs.filter(term_id=term_id)

        return Response(ClassSubjectSerializer(qs, many=True).data)


class AssignSubjectToClassView(APIView):
    """
    POST /classrooms/<pk>/subjects/assign/
    Assign a subject to a classroom for a term.
    Body: { "subject_id", "term_id", "is_compulsory" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, pk):
        from subjects.models import Subject, ClassSubject
        from subjects.serializers import ClassSubjectSerializer

        classroom = get_object_or_404(ClassRoom, pk=pk, school=request.school)

        subject_id = request.data.get('subject_id')
        term_id = request.data.get('term_id')
        is_compulsory = request.data.get('is_compulsory', True)

        if not subject_id or not term_id:
            return Response(
                {'detail': 'subject_id and term_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = get_object_or_404(Subject, id=subject_id, school=request.school)
        term = get_object_or_404(Term, id=term_id, academic_year__school=request.school)

        class_subject, created = ClassSubject.objects.get_or_create(
            classroom=classroom,
            subject=subject,
            term=term,
            defaults={'is_compulsory': is_compulsory},
        )

        if not created:
            return Response(
                {'detail': 'Subject is already assigned to this classroom for this term.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(ClassSubjectSerializer(class_subject).data, status=status.HTTP_201_CREATED)


class AssignTeacherToSubjectView(APIView):
    """
    POST /classrooms/<pk>/subjects/<subject_id>/assign-teacher/
    Assign a teacher to teach a subject in a classroom for a term.
    Body: { "teacher_id", "term_id", "is_primary" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, pk, subject_id):
        from subjects.models import Subject, SubjectTeacherAssignment
        from subjects.serializers import SubjectTeacherAssignmentSerializer

        classroom = get_object_or_404(ClassRoom, pk=pk, school=request.school)
        subject = get_object_or_404(Subject, id=subject_id, school=request.school)

        teacher_id = request.data.get('teacher_id')
        term_id = request.data.get('term_id')
        is_primary = request.data.get('is_primary', True)

        if not teacher_id or not term_id:
            return Response(
                {'detail': 'teacher_id and term_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        teacher = get_object_or_404(
            UserModel,
            id=teacher_id,
            school_memberships__school=request.school,
            school_memberships__role=SchoolMembership.SchoolRole.TEACHER,
            school_memberships__is_active=True,
        )
        term = get_object_or_404(Term, id=term_id, academic_year__school=request.school)

        assignment, created = SubjectTeacherAssignment.objects.get_or_create(
            subject=subject,
            teacher=teacher,
            classroom=classroom,
            term=term,
            defaults={'is_primary': is_primary},
        )

        if not created:
            return Response(
                {'detail': 'Teacher is already assigned to this subject/classroom/term.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SubjectTeacherAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Student Enrollment  (TASK 5 – assign students to JSS1–SSS3 classes)
# ─────────────────────────────────────────────────────────────────────────────

class StudentEnrollmentListView(generics.ListAPIView):
    """
    GET /enrollments/
    List all student class assignments for the current school.
    Supports filtering by ?classroom=, ?academic_session=, ?status=
    """

    serializer_class = StudentClassAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]
    filterset_fields = ['classroom', 'academic_session', 'status']
    search_fields = ['student__first_name', 'student__last_name', 'student__email']

    def get_queryset(self):
        return StudentClassAssignment.objects.filter(
            school=self.request.school
        ).select_related('student', 'classroom', 'academic_session', 'assigned_by')


class StudentEnrollmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /enrollments/<pk>/
    Retrieve, update status, or remove a student class assignment.
    """

    serializer_class = StudentClassAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return StudentClassAssignment.objects.filter(school=self.request.school)


class EnrollStudentView(APIView):
    """
    POST /enrollments/enroll/
    Enroll a single student into a classroom for an academic session.
    Body: { "student_id", "classroom_id", "academic_session_id", "notes" }

    If the student is already enrolled in another class for the same session,
    the old assignment is marked as 'transferred' and a new one is created.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = EnrollStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_object_or_404(
            UserModel,
            id=data['student_id'],
            school_memberships__school=request.school,
            school_memberships__role=SchoolMembership.SchoolRole.STUDENT,
            school_memberships__is_active=True,
        )
        classroom = get_object_or_404(ClassRoom, id=data['classroom_id'], school=request.school)
        session = get_object_or_404(
            AcademicSession, id=data['academic_session_id'], school=request.school
        )

        existing = StudentClassAssignment.objects.filter(
            student=student,
            academic_session=session,
        ).first()

        if existing:
            if existing.classroom == classroom:
                return Response(
                    {'detail': 'Student is already enrolled in this classroom for this session.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Transfer to new class
            existing.status = StudentClassAssignment.Status.TRANSFERRED
            existing.save(update_fields=['status'])

        assignment = StudentClassAssignment.objects.create(
            school=request.school,
            student=student,
            classroom=classroom,
            academic_session=session,
            assigned_by=request.user,
            notes=data.get('notes', ''),
        )

        return Response(
            StudentClassAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class BulkEnrollView(APIView):
    """
    POST /enrollments/bulk-enroll/
    Enroll multiple students into a classroom for an academic session.
    Body: { "student_ids": [...], "classroom_id", "academic_session_id", "notes" }

    Returns a summary: { enrolled: [...], transferred: [...], skipped: [...] }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = BulkEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        classroom = get_object_or_404(ClassRoom, id=data['classroom_id'], school=request.school)
        session = get_object_or_404(
            AcademicSession, id=data['academic_session_id'], school=request.school
        )

        results = {'enrolled': [], 'transferred': [], 'skipped': []}

        for student_id in data['student_ids']:
            student = UserModel.objects.filter(
                id=student_id,
                school_memberships__school=request.school,
                school_memberships__role=SchoolMembership.SchoolRole.STUDENT,
                school_memberships__is_active=True,
            ).first()

            if not student:
                results['skipped'].append({
                    'student_id': str(student_id),
                    'reason': 'Student not found or not a member of this school.',
                })
                continue

            existing = StudentClassAssignment.objects.filter(
                student=student,
                academic_session=session,
            ).first()

            if existing:
                if existing.classroom == classroom:
                    results['skipped'].append({
                        'student_id': str(student_id),
                        'reason': 'Already enrolled in this classroom for this session.',
                    })
                    continue
                # Transfer
                existing.status = StudentClassAssignment.Status.TRANSFERRED
                existing.save(update_fields=['status'])
                results['transferred'].append(str(student_id))

            assignment = StudentClassAssignment.objects.create(
                school=request.school,
                student=student,
                classroom=classroom,
                academic_session=session,
                assigned_by=request.user,
                notes=data.get('notes', ''),
            )
            results['enrolled'].append(StudentClassAssignmentSerializer(assignment).data)

        return Response(results, status=status.HTTP_201_CREATED)


class StudentClassAssignmentStatusView(APIView):
    """
    POST /enrollments/<pk>/update-status/
    Update the status of a student class assignment.
    Body: { "status": "active|transferred|graduated|withdrawn" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, pk):
        assignment = get_object_or_404(
            StudentClassAssignment, pk=pk, school=request.school
        )
        new_status = request.data.get('status')
        valid_statuses = [s.value for s in StudentClassAssignment.Status]
        if new_status not in valid_statuses:
            return Response(
                {'detail': f'Invalid status. Choose from: {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment.status = new_status
        assignment.save(update_fields=['status'])
        return Response(StudentClassAssignmentSerializer(assignment).data)


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — School Registration & Onboarding
# ═════════════════════════════════════════════════════════════════════════════

from django.contrib.auth.hashers import make_password
from django.utils import timezone as tz

from .models import SchoolRegistration, SchoolVerificationToken
from .serializers import (
    SchoolRegistrationSerializer,
    SchoolRegistrationInitSerializer,
    VerifyEmailSerializer,
    OnboardingStep1Serializer,
    OnboardingStep2Serializer,
    OnboardingStep3Serializer,
    OnboardingStep4Serializer,
    CompleteRegistrationSerializer,
)


def _get_client_ip(request):
    """Extract the real client IP from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class SchoolRegistrationInitView(APIView):
    """
    POST /api/v1/schools/register/
    Step 0: Submit school name + email to start registration.
    Creates a SchoolRegistration record and sends a verification email.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SchoolRegistrationInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        registration = SchoolRegistration.objects.create(
            school_name=data['school_name'],
            school_email=data['school_email'],
            phone=data.get('phone', ''),
            ip_address=_get_client_ip(request),
            status=SchoolRegistration.Status.PENDING_VERIFICATION,
        )

        # Create verification token
        token_obj = SchoolVerificationToken.create_for_registration(registration)

        # TODO: Send verification email via Celery task
        # from notifications.tasks import send_school_verification_email
        # send_school_verification_email.delay(registration.id, token_obj.token)

        return Response(
            {
                'message': (
                    'Registration started. Please check your email for a '
                    'verification link.'
                ),
                'registration_id': str(registration.id),
                'status': registration.status,
            },
            status=status.HTTP_201_CREATED,
        )


class SchoolRegistrationStatusView(APIView):
    """
    GET /api/v1/schools/register/<registration_id>/
    Return the current status and progress of a registration.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, registration_id):
        registration = get_object_or_404(SchoolRegistration, pk=registration_id)
        serializer = SchoolRegistrationSerializer(registration)
        return Response(serializer.data)


class VerifySchoolEmailView(APIView):
    """
    POST /api/v1/schools/register/verify-email/
    Step 1: Verify the school email using the token sent by email.
    Body: { "token": "<token>" }
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_str = serializer.validated_data['token']

        try:
            token_obj = SchoolVerificationToken.objects.select_related(
                'registration'
            ).get(token=token_str)
        except SchoolVerificationToken.DoesNotExist:
            return Response(
                {'detail': 'Invalid verification token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not token_obj.is_valid:
            return Response(
                {'detail': 'Token has expired or already been used.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_obj.mark_used()
        registration = token_obj.registration

        return Response(
            {
                'message': 'Email verified successfully.',
                'registration_id': str(registration.id),
                'status': registration.status,
                'onboarding_progress': registration.onboarding_progress,
            }
        )


class ResendVerificationEmailView(APIView):
    """
    POST /api/v1/schools/register/<registration_id>/resend-verification/
    Resend the verification email for a pending registration.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, registration_id):
        registration = get_object_or_404(
            SchoolRegistration,
            pk=registration_id,
            status=SchoolRegistration.Status.PENDING_VERIFICATION,
        )

        token_obj = SchoolVerificationToken.create_for_registration(registration)

        # TODO: Send verification email via Celery task
        # from notifications.tasks import send_school_verification_email
        # send_school_verification_email.delay(registration.id, token_obj.token)

        return Response(
            {'message': 'Verification email resent. Please check your inbox.'}
        )


class OnboardingStep1View(APIView):
    """
    POST /api/v1/schools/register/<registration_id>/onboarding/step-1/
    Step 2: Basic school info (name, address, principal details).
    Requires email_verified status.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, registration_id):
        registration = get_object_or_404(SchoolRegistration, pk=registration_id)

        if not registration.is_email_verified:
            return Response(
                {'detail': 'Email must be verified before onboarding.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OnboardingStep1Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        for field, value in data.items():
            setattr(registration, field, value)

        registration.status = SchoolRegistration.Status.ONBOARDING_STEP_1
        registration.save()

        return Response(
            {
                'message': 'Step 1 saved.',
                'status': registration.status,
                'onboarding_progress': registration.onboarding_progress,
            }
        )


class OnboardingStep2View(APIView):
    """
    POST /api/v1/schools/register/<registration_id>/onboarding/step-2/
    Step 3: Logo & branding.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, registration_id):
        registration = get_object_or_404(SchoolRegistration, pk=registration_id)

        if registration.status not in (
            SchoolRegistration.Status.ONBOARDING_STEP_1,
            SchoolRegistration.Status.ONBOARDING_STEP_2,
            SchoolRegistration.Status.ONBOARDING_STEP_3,
            SchoolRegistration.Status.ONBOARDING_STEP_4,
        ):
            return Response(
                {'detail': 'Please complete step 1 first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OnboardingStep2Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'logo' in data:
            registration.logo = data['logo']
        if 'motto' in data:
            registration.motto = data['motto']

        registration.status = SchoolRegistration.Status.ONBOARDING_STEP_2
        registration.save()

        return Response(
            {
                'message': 'Step 2 saved.',
                'status': registration.status,
                'onboarding_progress': registration.onboarding_progress,
            }
        )


class OnboardingStep3View(APIView):
    """
    POST /api/v1/schools/register/<registration_id>/onboarding/step-3/
    Step 4: Academic setup (grading system, timezone, term start month).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, registration_id):
        registration = get_object_or_404(SchoolRegistration, pk=registration_id)

        if registration.status not in (
            SchoolRegistration.Status.ONBOARDING_STEP_2,
            SchoolRegistration.Status.ONBOARDING_STEP_3,
            SchoolRegistration.Status.ONBOARDING_STEP_4,
        ):
            return Response(
                {'detail': 'Please complete step 2 first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OnboardingStep3Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        registration.academic_year_start_month = data['academic_year_start_month']
        registration.grading_system = data['grading_system']
        registration.timezone = data['timezone']
        registration.status = SchoolRegistration.Status.ONBOARDING_STEP_3
        registration.save()

        return Response(
            {
                'message': 'Step 3 saved.',
                'status': registration.status,
                'onboarding_progress': registration.onboarding_progress,
            }
        )


class OnboardingStep4View(APIView):
    """
    POST /api/v1/schools/register/<registration_id>/onboarding/step-4/
    Step 5: Admin account credentials.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, registration_id):
        registration = get_object_or_404(SchoolRegistration, pk=registration_id)

        if registration.status not in (
            SchoolRegistration.Status.ONBOARDING_STEP_3,
            SchoolRegistration.Status.ONBOARDING_STEP_4,
        ):
            return Response(
                {'detail': 'Please complete step 3 first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OnboardingStep4Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        registration.admin_first_name = data['admin_first_name']
        registration.admin_last_name = data['admin_last_name']
        registration.admin_email = data['admin_email']
        registration.admin_password_hash = make_password(data['admin_password'])
        registration.status = SchoolRegistration.Status.ONBOARDING_STEP_4
        registration.save()

        return Response(
            {
                'message': 'Step 4 saved. Ready to complete registration.',
                'status': registration.status,
                'onboarding_progress': registration.onboarding_progress,
            }
        )


class CompleteRegistrationView(APIView):
    """
    POST /api/v1/schools/register/<registration_id>/complete/
    Final step: Create the School, SchoolSettings, admin User, and
    SchoolMembership records. Marks registration as completed.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, registration_id):
        from django.db import transaction
        from django.contrib.auth.hashers import check_password

        registration = get_object_or_404(SchoolRegistration, pk=registration_id)

        if registration.status != SchoolRegistration.Status.ONBOARDING_STEP_4:
            return Response(
                {'detail': 'Please complete all onboarding steps first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate required fields are present
        required = [
            'school_name', 'school_email', 'admin_first_name',
            'admin_last_name', 'admin_email', 'admin_password_hash',
        ]
        missing = [f for f in required if not getattr(registration, f, None)]
        if missing:
            return Response(
                {'detail': f'Missing required fields: {missing}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # 1. Create admin User
                User = get_user_model()

                # Check if admin email already exists
                if User.objects.filter(email=registration.admin_email).exists():
                    return Response(
                        {'detail': 'An account with this admin email already exists.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                admin_user = User.objects.create(
                    email=registration.admin_email,
                    first_name=registration.admin_first_name,
                    last_name=registration.admin_last_name,
                    password=registration.admin_password_hash,
                    is_active=True,
                )

                # 2. Create School
                school = School.objects.create(
                    name=registration.school_name,
                    email=registration.school_email,
                    phone=registration.phone or '',
                    address=registration.address or '',
                    city=registration.city or '',
                    state=registration.state or '',
                    country=registration.country,
                    website=registration.website or '',
                    owner=admin_user,
                    is_active=True,
                )

                # Copy logo if present
                if registration.logo:
                    school.logo = registration.logo
                    school.save(update_fields=['logo'])

                # 3. Create SchoolSettings
                SchoolSettings.objects.create(
                    school=school,
                    principal_name=registration.principal_name or '',
                    motto=registration.motto or '',
                    timezone=registration.timezone,
                    grading_system=registration.grading_system,
                    academic_year_start_month=registration.academic_year_start_month,
                )

                # 4. Create SchoolMembership for admin
                SchoolMembership.objects.create(
                    school=school,
                    user=admin_user,
                    role=SchoolMembership.SchoolRole.SCHOOL_ADMIN,
                    is_active=True,
                )

                # 5. Seed default class levels
                _seed_class_levels(school)

                # 6. Mark registration as completed
                registration.school = school
                registration.status = SchoolRegistration.Status.COMPLETED
                registration.completed_at = tz.now()
                # Clear the hashed password from registration record
                registration.admin_password_hash = None
                registration.save()

        except Exception as exc:
            return Response(
                {'detail': f'Registration failed: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                'message': 'School registered successfully! You can now log in.',
                'school_id': str(school.id),
                'school_name': school.name,
                'admin_email': admin_user.email,
            },
            status=status.HTTP_201_CREATED,
        )


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — School Admin Dashboard
# ═════════════════════════════════════════════════════════════════════════════

from core.services.dashboard_service import get_school_admin_dashboard_data
from core.permissions import IsSchoolMember
from .serializers import SchoolMemberDetailSerializer, InviteStaffSerializer


class SchoolDashboardView(APIView):
    """
    GET /api/v1/schools/dashboard/
    Returns aggregated school-wide statistics for the school admin.

    Requires:
      - IsAuthenticated
      - HasSchoolContext  (X-School-ID header or single membership)
      - IsSchoolAdmin
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        data = get_school_admin_dashboard_data(request.school)
        return Response(data)


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — Member Management by Role
# ═════════════════════════════════════════════════════════════════════════════

class SchoolStudentsListView(generics.ListAPIView):
    """
    GET /api/v1/schools/members/students/
    List all active students in the current school.
    Supports ?search=<name|email> query param.
    """

    serializer_class = SchoolMemberDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        qs = SchoolMembership.objects.filter(
            school=self.request.school,
            role=SchoolMembership.SchoolRole.STUDENT,
            is_active=True,
        ).select_related('user').order_by('user__last_name', 'user__first_name')

        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q as DQ
            qs = qs.filter(
                DQ(user__first_name__icontains=search) |
                DQ(user__last_name__icontains=search) |
                DQ(user__email__icontains=search)
            )
        return qs


class SchoolTeachersListView(generics.ListAPIView):
    """
    GET /api/v1/schools/members/teachers/
    List all active teachers (and school admins) in the current school.
    Supports ?search=<name|email> query param.
    """

    serializer_class = SchoolMemberDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        qs = SchoolMembership.objects.filter(
            school=self.request.school,
            role__in=[
                SchoolMembership.SchoolRole.TEACHER,
                SchoolMembership.SchoolRole.SCHOOL_ADMIN,
            ],
            is_active=True,
        ).select_related('user').order_by('user__last_name', 'user__first_name')

        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q as DQ
            qs = qs.filter(
                DQ(user__first_name__icontains=search) |
                DQ(user__last_name__icontains=search) |
                DQ(user__email__icontains=search)
            )
        return qs


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — Invite Staff via Email
# ═════════════════════════════════════════════════════════════════════════════

class InviteStaffView(APIView):
    """
    POST /api/v1/schools/members/invite/
    Invite a teacher or school admin to the current school.

    If the user already exists (matched by email) they are added directly.
    If not, a new User account is created with a random temporary password
    and the user is notified by email.

    Body:
      {
        "email": "teacher@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "role": "teacher",          // or "school_admin"
        "send_welcome_email": true
      }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        import secrets as _secrets
        from django.core.mail import send_mail
        from django.conf import settings as django_settings

        serializer = InviteStaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data['email'].lower()
        role = data['role']
        school = request.school

        # ── Check for duplicate active membership ────────────────────────────
        if SchoolMembership.objects.filter(
            school=school,
            user__email=email,
            is_active=True,
        ).exists():
            return Response(
                {'detail': f'A member with email {email} already belongs to this school.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Get or create the user ───────────────────────────────────────────
        created_user = False
        temp_password = None
        try:
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            temp_password = _secrets.token_urlsafe(12)
            user = UserModel.objects.create_user(
                email=email,
                password=temp_password,
                first_name=data['first_name'],
                last_name=data['last_name'],
            )
            created_user = True

        # ── Create membership ────────────────────────────────────────────────
        membership, _ = SchoolMembership.objects.get_or_create(
            school=school,
            user=user,
            defaults={'role': role, 'is_active': True},
        )
        # If membership existed but was inactive, reactivate it
        if not membership.is_active or membership.role != role:
            membership.role = role
            membership.is_active = True
            membership.save(update_fields=['role', 'is_active'])

        # ── Send welcome / invite email ──────────────────────────────────────
        if data.get('send_welcome_email', True):
            try:
                subject = f"You've been invited to {school.name} on Examind"
                if created_user:
                    body = (
                        f"Hello {user.first_name or email},\n\n"
                        f"You have been invited to join {school.name} as a {role.replace('_', ' ').title()}.\n\n"
                        f"Your temporary login credentials:\n"
                        f"  Email:    {email}\n"
                        f"  Password: {temp_password}\n\n"
                        f"Please log in and change your password immediately.\n\n"
                        f"— The Examind Team"
                    )
                else:
                    body = (
                        f"Hello {user.first_name or email},\n\n"
                        f"You have been added to {school.name} as a {role.replace('_', ' ').title()} on Examind.\n\n"
                        f"Log in with your existing credentials to access the school.\n\n"
                        f"— The Examind Team"
                    )
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@examind.ng'),
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass  # Email failure must not block the response

        return Response(
            {
                'message': f'{"Created and invited" if created_user else "Invited"} {email} as {role}.',
                'membership_id': str(membership.id),
                'user_created': created_user,
                'role': role,
            },
            status=status.HTTP_201_CREATED,
        )


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — Teacher Management (CRUD + assign subjects/classes)
# ═════════════════════════════════════════════════════════════════════════════

from .serializers import (
    TeacherProfileSerializer,
    CreateTeacherSerializer,
    UpdateTeacherSerializer,
    StudentProfileSerializer,
    CreateStudentSerializer,
    UpdateStudentSerializer,
    BulkStudentUploadSerializer,
)


class TeacherListCreateView(APIView):
    """
    GET  /api/v1/schools/teachers/        — list all teachers in the school
    POST /api/v1/schools/teachers/        — create / invite a teacher
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        qs = SchoolMembership.objects.filter(
            school=request.school,
            role__in=[
                SchoolMembership.SchoolRole.TEACHER,
                SchoolMembership.SchoolRole.SCHOOL_ADMIN,
            ],
            is_active=True,
        ).select_related('user').order_by('user__last_name', 'user__first_name')

        if search:
            from django.db.models import Q as DQ
            qs = qs.filter(
                DQ(user__first_name__icontains=search) |
                DQ(user__last_name__icontains=search) |
                DQ(user__email__icontains=search)
            )

        serializer = TeacherProfileSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        import secrets as _secrets
        from django.core.mail import send_mail
        from django.conf import settings as django_settings

        serializer = CreateTeacherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data['email'].lower()
        school = request.school

        # Check duplicate active membership
        if SchoolMembership.objects.filter(
            school=school, user__email=email, is_active=True,
        ).exists():
            return Response(
                {'detail': f'A member with email {email} already belongs to this school.'},
                status=status.HTTP_409_CONFLICT,
            )

        created_user = False
        temp_password = None
        try:
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            temp_password = _secrets.token_urlsafe(12)
            user = UserModel.objects.create_user(
                email=email,
                password=temp_password,
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data.get('phone', ''),
                role=User.Role.TEACHER,
                is_active=True,
            )
            created_user = True

        membership, _ = SchoolMembership.objects.get_or_create(
            school=school,
            user=user,
            defaults={'role': SchoolMembership.SchoolRole.TEACHER, 'is_active': True},
        )
        if not membership.is_active or membership.role != SchoolMembership.SchoolRole.TEACHER:
            membership.role = SchoolMembership.SchoolRole.TEACHER
            membership.is_active = True
            membership.save(update_fields=['role', 'is_active'])

        if data.get('send_welcome_email', True):
            try:
                subject = f"You've been added as a teacher at {school.name} — Examind"
                if created_user:
                    body = (
                        f"Hello {user.first_name or email},\n\n"
                        f"You have been added as a teacher at {school.name} on Examind.\n\n"
                        f"Your login credentials:\n"
                        f"  Email:    {email}\n"
                        f"  Password: {temp_password}\n\n"
                        f"Please log in and change your password immediately.\n\n"
                        f"— The Examind Team"
                    )
                else:
                    body = (
                        f"Hello {user.first_name or email},\n\n"
                        f"You have been added as a teacher at {school.name} on Examind.\n\n"
                        f"Log in with your existing credentials.\n\n"
                        f"— The Examind Team"
                    )
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@examind.ng'),
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass

        membership.refresh_from_db()
        return Response(
            TeacherProfileSerializer(membership, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class TeacherDetailView(APIView):
    """
    GET    /api/v1/schools/teachers/<membership_id>/  — get teacher details
    PATCH  /api/v1/schools/teachers/<membership_id>/  — update teacher info
    DELETE /api/v1/schools/teachers/<membership_id>/  — deactivate teacher
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def _get_membership(self, request, membership_id):
        return get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            role__in=[SchoolMembership.SchoolRole.TEACHER, SchoolMembership.SchoolRole.SCHOOL_ADMIN],
        )

    def get(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        return Response(TeacherProfileSerializer(membership, context={'request': request}).data)

    def patch(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        serializer = UpdateTeacherSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = membership.user
        update_fields = []
        for field in ['first_name', 'last_name', 'phone']:
            if field in data:
                setattr(user, field, data[field])
                update_fields.append(field)
        if update_fields:
            user.save(update_fields=update_fields)

        membership.refresh_from_db()
        return Response(TeacherProfileSerializer(membership, context={'request': request}).data)

    def delete(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        if membership.user == request.school.owner:
            return Response(
                {'detail': 'Cannot deactivate the school owner.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership.is_active = False
        membership.save(update_fields=['is_active'])
        return Response({'message': 'Teacher deactivated successfully.'}, status=status.HTTP_200_OK)


class TeacherAssignSubjectView(APIView):
    """
    POST /api/v1/schools/teachers/<membership_id>/assign-subject/
    Assign a subject + classroom + term to a teacher.
    Body: { "subject_id", "classroom_id", "term_id", "is_primary" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, membership_id):
        from subjects.models import Subject, SubjectTeacherAssignment
        from subjects.serializers import SubjectTeacherAssignmentSerializer

        membership = get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            role__in=[SchoolMembership.SchoolRole.TEACHER, SchoolMembership.SchoolRole.SCHOOL_ADMIN],
            is_active=True,
        )

        subject_id  = request.data.get('subject_id')
        classroom_id = request.data.get('classroom_id')
        term_id     = request.data.get('term_id')
        is_primary  = request.data.get('is_primary', True)

        if not all([subject_id, classroom_id, term_id]):
            return Response(
                {'detail': 'subject_id, classroom_id, and term_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject   = get_object_or_404(Subject, id=subject_id, school=request.school)
        classroom = get_object_or_404(ClassRoom, id=classroom_id, school=request.school)
        term      = get_object_or_404(Term, id=term_id, academic_year__school=request.school)

        assignment, created = SubjectTeacherAssignment.objects.get_or_create(
            subject=subject,
            teacher=membership.user,
            classroom=classroom,
            term=term,
            defaults={'is_primary': is_primary},
        )

        if not created:
            return Response(
                {'detail': 'Teacher is already assigned to this subject/classroom/term.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SubjectTeacherAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class TeacherRemoveSubjectView(APIView):
    """
    DELETE /api/v1/schools/teachers/<membership_id>/remove-subject/
    Remove a subject assignment from a teacher.
    Body: { "subject_id", "classroom_id", "term_id" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def delete(self, request, membership_id):
        from subjects.models import SubjectTeacherAssignment

        membership = get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            is_active=True,
        )

        subject_id   = request.data.get('subject_id')
        classroom_id = request.data.get('classroom_id')
        term_id      = request.data.get('term_id')

        qs = SubjectTeacherAssignment.objects.filter(
            teacher=membership.user,
            subject__school=request.school,
        )
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
        if term_id:
            qs = qs.filter(term_id=term_id)

        deleted, _ = qs.delete()
        return Response(
            {'message': f'{deleted} assignment(s) removed.'},
            status=status.HTTP_200_OK,
        )


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 7A — Student Management (CRUD + bulk upload + profile)
# ═════════════════════════════════════════════════════════════════════════════

class StudentListCreateView(APIView):
    """
    GET  /api/v1/schools/students/  — list all students
    POST /api/v1/schools/students/  — create a new student
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        qs = SchoolMembership.objects.filter(
            school=request.school,
            role=SchoolMembership.SchoolRole.STUDENT,
            is_active=True,
        ).select_related('user').order_by('user__last_name', 'user__first_name')

        if search:
            from django.db.models import Q as DQ
            qs = qs.filter(
                DQ(user__first_name__icontains=search) |
                DQ(user__last_name__icontains=search) |
                DQ(user__email__icontains=search)
            )

        serializer = StudentProfileSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        import secrets as _secrets
        from accounts.models import StudentProfile

        serializer = CreateStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email  = data['email'].lower()
        school = request.school

        # Check duplicate active membership
        if SchoolMembership.objects.filter(
            school=school, user__email=email, is_active=True,
        ).exists():
            return Response(
                {'detail': f'A member with email {email} already belongs to this school.'},
                status=status.HTTP_409_CONFLICT,
            )

        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            created_user = False
            try:
                user = UserModel.objects.get(email=email)
            except UserModel.DoesNotExist:
                temp_password = _secrets.token_urlsafe(12)
                user = UserModel.objects.create_user(
                    email=email,
                    password=temp_password,
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    phone=data.get('phone', ''),
                    role=User.Role.STUDENT,
                    is_active=True,
                )
                created_user = True

            membership, _ = SchoolMembership.objects.get_or_create(
                school=school,
                user=user,
                defaults={'role': SchoolMembership.SchoolRole.STUDENT, 'is_active': True},
            )
            if not membership.is_active:
                membership.is_active = True
                membership.save(update_fields=['is_active'])

            # Create or update StudentProfile
            profile_data = {
                'admission_number': data.get('admission_number', ''),
                'date_of_birth': data.get('date_of_birth'),
                'gender': data.get('gender', ''),
                'guardian_name': data.get('guardian_name', ''),
                'guardian_phone': data.get('guardian_phone', ''),
                'guardian_email': data.get('guardian_email', ''),
                'guardian_relationship': data.get('guardian_relationship', ''),
            }
            profile_data = {k: v for k, v in profile_data.items() if v is not None}
            StudentProfile.objects.update_or_create(
                user=user,
                school=school,
                defaults=profile_data,
            )

        membership.refresh_from_db()
        return Response(
            StudentProfileSerializer(membership, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class StudentDetailView(APIView):
    """
    GET    /api/v1/schools/students/<membership_id>/  — get student details
    PATCH  /api/v1/schools/students/<membership_id>/  — update student info
    DELETE /api/v1/schools/students/<membership_id>/  — deactivate student
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def _get_membership(self, request, membership_id):
        return get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            role=SchoolMembership.SchoolRole.STUDENT,
        )

    def get(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        return Response(StudentProfileSerializer(membership, context={'request': request}).data)

    def patch(self, request, membership_id):
        from accounts.models import StudentProfile

        membership = self._get_membership(request, membership_id)
        serializer = UpdateStudentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = membership.user
        user_fields = ['first_name', 'last_name', 'phone']
        user_update = [f for f in user_fields if f in data]
        if user_update:
            for f in user_update:
                setattr(user, f, data[f])
            user.save(update_fields=user_update)

        profile_fields = [
            'admission_number', 'date_of_birth', 'gender',
            'guardian_name', 'guardian_phone', 'guardian_email', 'guardian_relationship',
        ]
        profile_data = {k: data[k] for k in profile_fields if k in data}
        if profile_data:
            StudentProfile.objects.update_or_create(
                user=user,
                school=request.school,
                defaults=profile_data,
            )

        membership.refresh_from_db()
        return Response(StudentProfileSerializer(membership, context={'request': request}).data)

    def delete(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        membership.is_active = False
        membership.save(update_fields=['is_active'])
        return Response({'message': 'Student deactivated successfully.'}, status=status.HTTP_200_OK)


class StudentBulkUploadView(APIView):
    """
    POST /api/v1/schools/students/bulk-upload/
    Bulk create students from a JSON list.
    Body: { "students": [{ "email", "first_name", "last_name", ... }, ...] }
    Returns: { "created": [...], "skipped": [...], "errors": [...] }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        import secrets as _secrets
        from accounts.models import StudentProfile
        from django.db import transaction as db_transaction

        serializer = BulkStudentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        students_data = serializer.validated_data['students']

        school = request.school
        results = {'created': [], 'skipped': [], 'errors': []}

        for idx, student_data in enumerate(students_data):
            email = (student_data.get('email') or '').lower().strip()
            if not email:
                results['errors'].append({'index': idx, 'reason': 'Email is required.'})
                continue

            first_name = student_data.get('first_name', '').strip()
            last_name  = student_data.get('last_name', '').strip()
            if not first_name or not last_name:
                results['errors'].append({'index': idx, 'email': email, 'reason': 'first_name and last_name are required.'})
                continue

            try:
                with db_transaction.atomic():
                    if SchoolMembership.objects.filter(
                        school=school, user__email=email, is_active=True,
                    ).exists():
                        results['skipped'].append({'email': email, 'reason': 'Already a member.'})
                        continue

                    try:
                        user = UserModel.objects.get(email=email)
                    except UserModel.DoesNotExist:
                        temp_password = _secrets.token_urlsafe(12)
                        user = UserModel.objects.create_user(
                            email=email,
                            password=temp_password,
                            first_name=first_name,
                            last_name=last_name,
                            phone=student_data.get('phone', ''),
                            role=User.Role.STUDENT,
                            is_active=True,
                        )

                    membership, _ = SchoolMembership.objects.get_or_create(
                        school=school,
                        user=user,
                        defaults={'role': SchoolMembership.SchoolRole.STUDENT, 'is_active': True},
                    )
                    if not membership.is_active:
                        membership.is_active = True
                        membership.save(update_fields=['is_active'])

                    profile_data = {
                        k: student_data[k]
                        for k in [
                            'admission_number', 'date_of_birth', 'gender',
                            'guardian_name', 'guardian_phone', 'guardian_email',
                            'guardian_relationship',
                        ]
                        if k in student_data and student_data[k]
                    }
                    StudentProfile.objects.update_or_create(
                        user=user, school=school, defaults=profile_data,
                    )

                    results['created'].append({'email': email, 'user_id': str(user.id)})

            except Exception as exc:
                results['errors'].append({'index': idx, 'email': email, 'reason': str(exc)})

        return Response(results, status=status.HTTP_201_CREATED)

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 7B VIEWS — PART 1 (Tasks 1-5)
# Appended to schools/views.py
# ══════════════════════════════════════════════════════════════════════════════


class PlatformInfoView(APIView):
    """
    GET /api/v1/schools/platform/info/
    Public endpoint — returns platform features, stats, and pricing tiers.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            'platform': {
                'name': 'Examind',
                'tagline': 'The all-in-one school management platform for Nigerian secondary schools.',
                'version': '2.0',
            },
            'features': [
                {'id': 'multi_school',    'title': 'Multi-School Management', 'description': 'Manage multiple schools from a single platform.',                      'icon': 'school'},
                {'id': 'exam_engine',     'title': 'CBT Exam Engine',         'description': 'Create, schedule, and auto-grade computer-based tests.',               'icon': 'quiz'},
                {'id': 'result_mgmt',     'title': 'Result Management',       'description': 'Generate result sheets, report cards, and transcripts.',               'icon': 'assessment'},
                {'id': 'class_promotion', 'title': 'Class Promotion Engine',  'description': 'Bulk-promote students from JSS1 to SSS3 with one click.',              'icon': 'upgrade'},
                {'id': 'parent_portal',   'title': 'Parent Portal',           'description': 'Parents can view results, attendance, and communicate with teachers.', 'icon': 'family_restroom'},
                {'id': 'bulk_import',     'title': 'Bulk Import',             'description': 'Import students, teachers, and parents via CSV or Excel.',             'icon': 'upload_file'},
                {'id': 'branding',        'title': 'School Branding',         'description': 'Customise your school portal with your logo, colours, and motto.',     'icon': 'palette'},
                {'id': 'audit_logs',      'title': 'Audit Logs',              'description': 'Full audit trail of all actions performed in your school.',            'icon': 'history'},
            ],
            'stats': {
                'schools_onboarded': 0,
                'students_managed':  0,
                'exams_conducted':   0,
            },
            'pricing': [
                {
                    'tier': 'starter', 'name': 'Starter', 'price_ngn': 0,
                    'price_label': 'Free', 'max_students': 100,
                    'features': ['CBT Exams', 'Result Management', 'Up to 100 students'],
                },
                {
                    'tier': 'school', 'name': 'School', 'price_ngn': 50000,
                    'price_label': '\u20a650,000/term', 'max_students': 1000,
                    'features': ['Everything in Starter', 'Parent Portal', 'Bulk Import', 'Branding', 'Up to 1,000 students'],
                },
                {
                    'tier': 'enterprise', 'name': 'Enterprise', 'price_ngn': None,
                    'price_label': 'Contact us', 'max_students': None,
                    'features': ['Everything in School', 'Multi-school', 'Dedicated support', 'Custom integrations'],
                },
            ],
        })


class BookDemoView(APIView):
    """
    POST /api/v1/schools/platform/book-demo/
    Public endpoint — records a demo booking request.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        name    = request.data.get('name', '').strip()
        email   = request.data.get('email', '').strip()
        phone   = request.data.get('phone', '').strip()
        school  = request.data.get('school_name', '').strip()
        message = request.data.get('message', '').strip()

        if not name or not email:
            return Response({'detail': 'name and email are required.'}, status=status.HTTP_400_BAD_REQUEST)

        from core.services.audit_service import log_action, AuditAction
        log_action(
            action=AuditAction.LOGIN,
            actor=None, school=None,
            target_type='DemoRequest', target_repr=f'{name} <{email}>',
            metadata={'name': name, 'email': email, 'phone': phone, 'school_name': school, 'message': message},
            request=request,
        )
        return Response(
            {'detail': 'Demo request received. Our team will contact you within 24 hours.', 'name': name, 'email': email},
            status=status.HTTP_201_CREATED,
        )


class RegistrationReviewView(APIView):
    """
    GET /api/v1/schools/register/<registration_id>/review/
    Returns a summary of all onboarding data collected so far.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, registration_id):
        from .models import SchoolRegistration
        try:
            reg = SchoolRegistration.objects.get(id=registration_id)
        except SchoolRegistration.DoesNotExist:
            return Response({'detail': 'Registration not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = reg.onboarding_data or {}
        return Response({
            'registration_id': str(reg.id),
            'status':          reg.status,
            'email':           reg.email,
            'email_verified':  reg.email_verified,
            'steps_completed': reg.steps_completed,
            'review': {
                'school_name':               data.get('school_name', ''),
                'school_type':               data.get('school_type', ''),
                'phone':                     data.get('phone', ''),
                'address':                   data.get('address', ''),
                'city':                      data.get('city', ''),
                'state':                     data.get('state', ''),
                'country':                   data.get('country', 'Nigeria'),
                'website':                   data.get('website', ''),
                'primary_color':             data.get('primary_color', '#1A73E8'),
                'secondary_color':           data.get('secondary_color', '#FFFFFF'),
                'motto':                     data.get('motto', ''),
                'academic_year_start_month': data.get('academic_year_start_month', 9),
                'grading_system':            data.get('grading_system', 'percentage'),
                'admin_first_name':          data.get('admin_first_name', ''),
                'admin_last_name':           data.get('admin_last_name', ''),
                'admin_email':               data.get('admin_email', reg.email),
            },
            'created_at': reg.created_at.isoformat(),
        })


class EnhancedSchoolDashboardView(APIView):
    """
    GET /api/v1/schools/dashboard/enhanced/
    Rich dashboard: stats + quick actions + recent activity.
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        school = request.school
        from core.services.audit_service import get_recent_activity
        from core.services.school_settings_service import get_current_session, get_current_term

        total_students   = SchoolMembership.objects.filter(school=school, role=SchoolMembership.SchoolRole.STUDENT, is_active=True).count()
        total_teachers   = SchoolMembership.objects.filter(school=school, role=SchoolMembership.SchoolRole.TEACHER, is_active=True).count()
        total_classrooms = ClassRoom.objects.filter(school=school, is_active=True).count()

        current_session = get_current_session(school)
        current_term    = get_current_term(school)

        enrolled_this_session = 0
        if current_session:
            enrolled_this_session = StudentClassAssignment.objects.filter(
                school=school,
                academic_session=current_session,
                status=StudentClassAssignment.Status.ACTIVE,
            ).count()

        return Response({
            'school': {
                'id':          str(school.id),
                'name':        school.name,
                'slug':        school.slug,
                'logo_url':    school.logo.url if school.logo else None,
                'school_type': school.school_type,
            },
            'stats': {
                'total_students':        total_students,
                'total_teachers':        total_teachers,
                'total_classrooms':      total_classrooms,
                'enrolled_this_session': enrolled_this_session,
            },
            'current_session': {
                'id':   str(current_session.id) if current_session else None,
                'name': current_session.name    if current_session else None,
            },
            'current_term': {
                'id':   str(current_term.id) if current_term else None,
                'name': current_term.name    if current_term else None,
            },
            'quick_actions': [
                {'id': 'add_student',     'label': 'Add Student',     'url': '/schools/students/',         'icon': 'person_add'},
                {'id': 'add_teacher',     'label': 'Add Teacher',     'url': '/schools/teachers/',         'icon': 'school'},
                {'id': 'bulk_import',     'label': 'Bulk Import',     'url': '/schools/import/',           'icon': 'upload_file'},
                {'id': 'promote_class',   'label': 'Promote Classes', 'url': '/schools/promotions/apply/', 'icon': 'upgrade'},
                {'id': 'view_results',    'label': 'View Results',    'url': '/results/',                  'icon': 'assessment'},
                {'id': 'school_settings', 'label': 'Settings',        'url': '/schools/settings/full/',    'icon': 'settings'},
            ],
            'recent_activity': get_recent_activity(school, limit=10),
        })


class BulkImportView(APIView):
    """
    POST /api/v1/schools/import/
    Accepts a CSV or Excel file and imports students, teachers, or parents.
    Form fields: file, import_type ('students'|'teachers'|'parents')
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        school      = request.school
        import_type = request.data.get('import_type', 'students').lower()
        file_obj    = request.FILES.get('file')

        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        if import_type not in ('students', 'teachers', 'parents'):
            return Response({'detail': 'import_type must be students, teachers, or parents.'}, status=status.HTTP_400_BAD_REQUEST)

        rows, parse_error = self._parse_file(file_obj)
        if parse_error:
            return Response({'detail': parse_error}, status=status.HTTP_400_BAD_REQUEST)

        if import_type == 'students':
            result = self._import_students(rows, school)
        elif import_type == 'teachers':
            result = self._import_teachers(rows, school)
        else:
            result = self._import_parents(rows, school)

        from core.services.audit_service import log_action, AuditAction
        log_action(
            action=AuditAction.BULK_IMPORT, actor=request.user, school=school, request=request,
            metadata={
                'import_type': import_type,
                'created': len(result.get('created', [])),
                'updated': len(result.get('updated', [])),
                'errors':  len(result.get('errors', [])),
            },
        )
        return Response(result, status=status.HTTP_200_OK)

    def _parse_file(self, file_obj):
        filename = file_obj.name.lower()
        try:
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                return self._parse_excel(file_obj)
            return self._parse_csv(file_obj)
        except Exception as exc:
            return [], f'File parse error: {exc}'

    def _parse_csv(self, file_obj):
        import csv, io
        content = file_obj.read().decode('utf-8-sig')
        reader  = csv.DictReader(io.StringIO(content))
        return [row for row in reader], None

    def _parse_excel(self, file_obj):
        try:
            import openpyxl
        except ImportError:
            return [], 'openpyxl is required for Excel import. Install it or use CSV.'
        import io
        wb      = openpyxl.load_workbook(io.BytesIO(file_obj.read()), read_only=True, data_only=True)
        ws      = wb.active
        raw     = ws.iter_rows(values_only=True)
        headers = [str(h).strip().lower() if h else '' for h in next(raw, [])]
        rows    = []
        for row in raw:
            if any(cell is not None for cell in row):
                rows.append({headers[i]: (str(row[i]).strip() if row[i] is not None else '') for i in range(len(headers))})
        return rows, None

    def _import_students(self, rows, school):
        from django.db import transaction
        from accounts.models import StudentProfile
        User = get_user_model()
        created, updated, errors = [], [], []
        for idx, row in enumerate(rows, start=2):
            email = (row.get('email') or '').strip().lower()
            if not email:
                errors.append({'row': idx, 'reason': 'email is required'})
                continue
            first_name = (row.get('first_name') or '').strip()
            last_name  = (row.get('last_name')  or '').strip()
            try:
                with transaction.atomic():
                    user, is_new = User.objects.get_or_create(
                        email=email,
                        defaults={'first_name': first_name, 'last_name': last_name, 'username': email},
                    )
                    if not is_new:
                        if first_name: user.first_name = first_name
                        if last_name:  user.last_name  = last_name
                        user.save(update_fields=['first_name', 'last_name'])
                    membership, _ = SchoolMembership.objects.get_or_create(
                        school=school, user=user,
                        defaults={'role': SchoolMembership.SchoolRole.STUDENT, 'is_active': True},
                    )
                    if not membership.is_active:
                        membership.is_active = True
                        membership.save(update_fields=['is_active'])
                    profile_defaults = {
                        f: (row.get(f) or '').strip()
                        for f in ('admission_number', 'date_of_birth', 'gender', 'guardian_name', 'guardian_phone')
                        if (row.get(f) or '').strip()
                    }
                    StudentProfile.objects.update_or_create(user=user, school=school, defaults=profile_defaults)
                    (created if is_new else updated).append({'row': idx, 'email': email})
            except Exception as exc:
                errors.append({'row': idx, 'email': email, 'reason': str(exc)})
        return {'created': created, 'updated': updated, 'errors': errors,
                'summary': {'created': len(created), 'updated': len(updated), 'errors': len(errors)}}

    def _import_teachers(self, rows, school):
        from django.db import transaction
        User = get_user_model()
        created, updated, errors = [], [], []
        for idx, row in enumerate(rows, start=2):
            email = (row.get('email') or '').strip().lower()
            if not email:
                errors.append({'row': idx, 'reason': 'email is required'})
                continue
            first_name = (row.get('first_name') or '').strip()
            last_name  = (row.get('last_name')  or '').strip()
            try:
                with transaction.atomic():
                    user, is_new = User.objects.get_or_create(
                        email=email,
                        defaults={'first_name': first_name, 'last_name': last_name, 'username': email},
                    )
                    if not is_new:
                        if first_name: user.first_name = first_name
                        if last_name:  user.last_name  = last_name
                        user.save(update_fields=['first_name', 'last_name'])
                    membership, _ = SchoolMembership.objects.get_or_create(
                        school=school, user=user,
                        defaults={'role': SchoolMembership.SchoolRole.TEACHER, 'is_active': True},
                    )
                    if not membership.is_active:
                        membership.is_active = True
                        membership.save(update_fields=['is_active'])
                    (created if is_new else updated).append({'row': idx, 'email': email})
            except Exception as exc:
                errors.append({'row': idx, 'email': email, 'reason': str(exc)})
        return {'created': created, 'updated': updated, 'errors': errors,
                'summary': {'created': len(created), 'updated': len(updated), 'errors': len(errors)}}

    def _import_parents(self, rows, school):
        from django.db import transaction
        from parents.models import ParentProfile
        User = get_user_model()
        created, updated, errors = [], [], []
        for idx, row in enumerate(rows, start=2):
            email = (row.get('email') or '').strip().lower()
            if not email:
                errors.append({'row': idx, 'reason': 'email is required'})
                continue
            first_name = (row.get('first_name') or '').strip()
            last_name  = (row.get('last_name')  or '').strip()
            try:
                with transaction.atomic():
                    user, is_new = User.objects.get_or_create(
                        email=email,
                        defaults={'first_name': first_name, 'last_name': last_name, 'username': email},
                    )
                    if not is_new:
                        if first_name: user.first_name = first_name
                        if last_name:  user.last_name  = last_name
                        user.save(update_fields=['first_name', 'last_name'])
                    membership, _ = SchoolMembership.objects.get_or_create(
                        school=school, user=user,
                        defaults={'role': SchoolMembership.SchoolRole.PARENT, 'is_active': True},
                    )
                    if not membership.is_active:
                        membership.is_active = True
                        membership.save(update_fields=['is_active'])
                    profile_defaults = {
                        f: (row.get(f) or '').strip()
                        for f in ('phone', 'relationship')
                        if (row.get(f) or '').strip()
                    }
                    ParentProfile.objects.update_or_create(user=user, school=school, defaults=profile_defaults)
                    student_email = (row.get('student_email') or '').strip().lower()
                    if student_email:
                        try:
                            student_user = User.objects.get(email=student_email)
                            from schools.models import ParentStudentLink
                            ParentStudentLink.objects.get_or_create(
                                parent=user, student=student_user, school=school,
                                defaults={'status': 'active'},
                            )
                        except User.DoesNotExist:
                            pass
                    (created if is_new else updated).append({'row': idx, 'email': email})
            except Exception as exc:
                errors.append({'row': idx, 'email': email, 'reason': str(exc)})
        return {'created': created, 'updated': updated, 'errors': errors,
                'summary': {'created': len(created), 'updated': len(updated), 'errors': len(errors)}}


class BulkImportTemplateView(APIView):
    """
    GET /api/v1/schools/import/template/?type=students|teachers|parents
    Returns a CSV template with the correct column headers.
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    TEMPLATES = {
        'students': 'first_name,last_name,email,admission_number,date_of_birth,gender,guardian_name,guardian_phone\n',
        'teachers': 'first_name,last_name,email,phone,subject\n',
        'parents':  'first_name,last_name,email,phone,student_email,relationship\n',
    }

    def get(self, request):
        from django.http import HttpResponse
        import_type = request.query_params.get('type', 'students').lower()
        if import_type not in self.TEMPLATES:
            return Response({'detail': 'type must be students, teachers, or parents.'}, status=status.HTTP_400_BAD_REQUEST)
        response = HttpResponse(self.TEMPLATES[import_type], content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{import_type}_import_template.csv"'
        return response


class PromotionPreviewView(APIView):
    """
    POST /api/v1/schools/promotions/preview/
    Dry-run promotion — returns what would happen without making DB changes.
    Body: { "from_session_id": "<uuid>", "to_session_id": "<uuid>" }
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        school  = request.school
        from_id = request.data.get('from_session_id')
        to_id   = request.data.get('to_session_id')
        if not from_id or not to_id:
            return Response({'detail': 'from_session_id and to_session_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        from_session = get_object_or_404(AcademicSession, id=from_id, school=school)
        to_session   = get_object_or_404(AcademicSession, id=to_id,   school=school)
        from core.services.promotion_service import preview_promotion
        return Response(preview_promotion(school, from_session, to_session))


class PromotionApplyView(APIView):
    """
    POST /api/v1/schools/promotions/apply/
    Apply class promotion — creates new assignments, marks old ones.
    Body: { "from_session_id": "<uuid>", "to_session_id": "<uuid>" }
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        school  = request.school
        from_id = request.data.get('from_session_id')
        to_id   = request.data.get('to_session_id')
        if not from_id or not to_id:
            return Response({'detail': 'from_session_id and to_session_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        from_session = get_object_or_404(AcademicSession, id=from_id, school=school)
        to_session   = get_object_or_404(AcademicSession, id=to_id,   school=school)
        if ClassPromotion.objects.filter(
            school=school, from_session=from_session, to_session=to_session,
            status=ClassPromotion.Status.APPLIED,
        ).exists():
            return Response(
                {'detail': 'A promotion for this session pair has already been applied.'},
                status=status.HTTP_409_CONFLICT,
            )
        from core.services.promotion_service import apply_promotion
        promotion = apply_promotion(school, from_session, to_session, promoted_by=request.user, request=request)
        return Response({
            'id':        str(promotion.id),
            'status':    promotion.status,
            'promoted':  promotion.summary.get('promoted', 0),
            'graduated': promotion.summary.get('graduated', 0),
            'skipped':   promotion.summary.get('skipped', 0),
            'applied_at': promotion.applied_at.isoformat() if promotion.applied_at else None,
        }, status=status.HTTP_201_CREATED)


class PromotionUndoView(APIView):
    """
    POST /api/v1/schools/promotions/<promotion_id>/undo/
    Undo a previously applied promotion.
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, promotion_id):
        school    = request.school
        promotion = get_object_or_404(ClassPromotion, id=promotion_id, school=school)
        if promotion.status != ClassPromotion.Status.APPLIED:
            return Response(
                {'detail': f'Cannot undo a promotion with status "{promotion.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from core.services.promotion_service import undo_promotion
        try:
            promotion = undo_promotion(promotion, undone_by=request.user, request=request)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'id':        str(promotion.id),
            'status':    promotion.status,
            'undone_at': promotion.undone_at.isoformat() if promotion.undone_at else None,
        })


class PromotionReportView(APIView):
    """
    GET /api/v1/schools/promotions/
    Returns all promotion records for the school.
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        from core.services.promotion_service import get_promotion_report
        return Response({'promotions': get_promotion_report(request.school)})

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 7B VIEWS — PART 2 (Tasks 6-9)
# Appended to schools/views.py
# ══════════════════════════════════════════════════════════════════════════════


class SchoolBrandingView(APIView):
    """
    GET  /api/v1/schools/branding/  — retrieve current branding context
    PATCH /api/v1/schools/branding/ — update branding fields (school admin only)
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get(self, request):
        from core.services.branding_service import get_branding_context
        return Response(get_branding_context(request.school))

    def patch(self, request):
        school     = request.school
        membership = SchoolMembership.objects.filter(school=school, user=request.user, is_active=True).first()
        if not membership or membership.role != SchoolMembership.SchoolRole.SCHOOL_ADMIN:
            return Response({'detail': 'Only school admins can update branding.'}, status=status.HTTP_403_FORBIDDEN)
        from core.services.branding_service import update_branding
        branding = update_branding(school, request.data, request=request)
        return Response({
            'id':                      str(branding.id),
            'primary_color':           branding.primary_color,
            'secondary_color':         branding.secondary_color,
            'accent_color':            branding.accent_color,
            'motto':                   branding.motto,
            'tagline':                 branding.tagline,
            'report_header_text':      branding.report_header_text,
            'certificate_header_text': branding.certificate_header_text,
            'report_footer_text':      branding.report_footer_text,
            'certificate_footer_text': branding.certificate_footer_text,
            'logo_url':                branding.logo.url if branding.logo else None,
            'favicon_url':             branding.favicon.url if branding.favicon else None,
            'has_signature':           bool(branding.principal_signature),
            'has_stamp':               bool(branding.stamp_image),
            'updated_at':              branding.updated_at.isoformat(),
        })


class StudentIDCardView(APIView):
    """
    GET /api/v1/schools/documents/id-card/<student_id>/
    Returns structured data for a student ID card.
    Add ?format=pdf to get a PDF response (requires ReportLab).
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request, student_id):
        from django.http import HttpResponse
        from core.services.document_service import generate_student_id_card_data, generate_pdf_bytes
        from core.services.audit_service import log_action, AuditAction
        school       = request.school
        student_user = get_object_or_404(get_user_model(), id=student_id)
        data         = generate_student_id_card_data(student_user, school)
        log_action(action=AuditAction.DOCUMENT_GENERATED, actor=request.user, school=school, request=request,
                   metadata={'document_type': 'student_id_card', 'student_id': str(student_id)})
        if request.query_params.get('format') == 'pdf':
            pdf_bytes = generate_pdf_bytes(data)
            if pdf_bytes:
                resp = HttpResponse(pdf_bytes, content_type='application/pdf')
                resp['Content-Disposition'] = f'inline; filename="id_card_{student_id}.pdf"'
                return resp
            return Response({'detail': 'PDF generation unavailable. Install ReportLab.'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        return Response(data)


class ResultSheetView(APIView):
    """
    GET /api/v1/schools/documents/result-sheet/<student_id>/
    Query params: term_id (optional), session_id (optional), format=pdf
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request, student_id):
        from django.http import HttpResponse
        from core.services.document_service import generate_result_sheet_data, generate_pdf_bytes
        from core.services.audit_service import log_action, AuditAction
        school       = request.school
        student_user = get_object_or_404(get_user_model(), id=student_id)

        term    = None
        session = None
        term_id    = request.query_params.get('term_id')
        session_id = request.query_params.get('session_id')
        if term_id:
            from .models import Term
            term = Term.objects.filter(id=term_id).first()
        if session_id:
            session = AcademicSession.objects.filter(id=session_id, school=school).first()

        data = generate_result_sheet_data(student_user, school, term=term, session=session)
        log_action(action=AuditAction.DOCUMENT_GENERATED, actor=request.user, school=school, request=request,
                   metadata={'document_type': 'result_sheet', 'student_id': str(student_id)})
        if request.query_params.get('format') == 'pdf':
            pdf_bytes = generate_pdf_bytes(data)
            if pdf_bytes:
                resp = HttpResponse(pdf_bytes, content_type='application/pdf')
                resp['Content-Disposition'] = f'inline; filename="result_sheet_{student_id}.pdf"'
                return resp
            return Response({'detail': 'PDF generation unavailable. Install ReportLab.'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        return Response(data)


class ReportCardView(APIView):
    """
    GET /api/v1/schools/documents/report-card/<student_id>/
    Query params: session_id (optional), format=pdf
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request, student_id):
        from django.http import HttpResponse
        from core.services.document_service import generate_report_card_data, generate_pdf_bytes
        from core.services.audit_service import log_action, AuditAction
        school       = request.school
        student_user = get_object_or_404(get_user_model(), id=student_id)

        session    = None
        session_id = request.query_params.get('session_id')
        if session_id:
            session = AcademicSession.objects.filter(id=session_id, school=school).first()

        data = generate_report_card_data(student_user, school, session=session)
        log_action(action=AuditAction.DOCUMENT_GENERATED, actor=request.user, school=school, request=request,
                   metadata={'document_type': 'report_card', 'student_id': str(student_id)})
        if request.query_params.get('format') == 'pdf':
            pdf_bytes = generate_pdf_bytes(data)
            if pdf_bytes:
                resp = HttpResponse(pdf_bytes, content_type='application/pdf')
                resp['Content-Disposition'] = f'inline; filename="report_card_{student_id}.pdf"'
                return resp
            return Response({'detail': 'PDF generation unavailable. Install ReportLab.'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        return Response(data)


class ExamSlipView(APIView):
    """
    GET /api/v1/schools/documents/exam-slip/<student_id>/?exam_id=<uuid>
    Returns structured data for an examination slip.
    Add ?format=pdf to get a PDF response.
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request, student_id):
        from django.http import HttpResponse
        from core.services.document_service import generate_exam_slip_data, generate_pdf_bytes
        from core.services.audit_service import log_action, AuditAction
        school       = request.school
        student_user = get_object_or_404(get_user_model(), id=student_id)
        exam_id      = request.query_params.get('exam_id')
        if not exam_id:
            return Response({'detail': 'exam_id query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from exams.models import Exam
            exam = Exam.objects.get(id=exam_id)
        except Exception:
            return Response({'detail': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = generate_exam_slip_data(student_user, school, exam)
        log_action(action=AuditAction.DOCUMENT_GENERATED, actor=request.user, school=school, request=request,
                   metadata={'document_type': 'exam_slip', 'student_id': str(student_id), 'exam_id': exam_id})
        if request.query_params.get('format') == 'pdf':
            pdf_bytes = generate_pdf_bytes(data)
            if pdf_bytes:
                resp = HttpResponse(pdf_bytes, content_type='application/pdf')
                resp['Content-Disposition'] = f'inline; filename="exam_slip_{student_id}.pdf"'
                return resp
            return Response({'detail': 'PDF generation unavailable. Install ReportLab.'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        return Response(data)


class CertificateView(APIView):
    """
    GET /api/v1/schools/documents/certificate/<student_id>/
    Query params: type=completion|graduation (default: completion), format=pdf
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request, student_id):
        from django.http import HttpResponse
        from core.services.document_service import generate_certificate_data, generate_pdf_bytes
        from core.services.audit_service import log_action, AuditAction
        school           = request.school
        student_user     = get_object_or_404(get_user_model(), id=student_id)
        certificate_type = request.query_params.get('type', 'completion')

        data = generate_certificate_data(student_user, school, certificate_type=certificate_type)
        log_action(action=AuditAction.DOCUMENT_GENERATED, actor=request.user, school=school, request=request,
                   metadata={'document_type': 'certificate', 'certificate_type': certificate_type, 'student_id': str(student_id)})
        if request.query_params.get('format') == 'pdf':
            pdf_bytes = generate_pdf_bytes(data)
            if pdf_bytes:
                resp = HttpResponse(pdf_bytes, content_type='application/pdf')
                resp['Content-Disposition'] = f'inline; filename="certificate_{student_id}.pdf"'
                return resp
            return Response({'detail': 'PDF generation unavailable. Install ReportLab.'}, status=status.HTTP_501_NOT_IMPLEMENTED)
        return Response(data)


class AuditLogListView(APIView):
    """
    GET /api/v1/schools/audit-logs/
    Returns paginated audit logs for the school.
    Query params: action, limit (default 50), offset (default 0)
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        from core.services.audit_service import get_school_audit_logs
        school = request.school
        action = request.query_params.get('action')
        limit  = min(int(request.query_params.get('limit',  50)), 200)
        offset = int(request.query_params.get('offset', 0))

        logs = get_school_audit_logs(school, action=action, limit=limit, offset=offset)
        total = AuditLog.objects.filter(school=school).count()

        return Response({
            'count':  total,
            'limit':  limit,
            'offset': offset,
            'results': [
                {
                    'id':           str(log.id),
                    'action':       log.action,
                    'action_display': log.get_action_display(),
                    'actor':        log.actor.get_full_name() if log.actor else 'System',
                    'actor_email':  log.actor.email if log.actor else None,
                    'target_type':  log.target_type,
                    'target_repr':  log.target_repr,
                    'metadata':     log.metadata,
                    'ip_address':   log.ip_address,
                    'created_at':   log.created_at.isoformat(),
                }
                for log in logs
            ],
        })


class SchoolSettingsDetailView(APIView):
    """
    GET   /api/v1/schools/settings/full/  — retrieve full school settings
    PATCH /api/v1/schools/settings/full/  — update school info + settings
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        from core.services.school_settings_service import get_full_school_settings
        return Response(get_full_school_settings(request.school))

    def patch(self, request):
        from core.services.school_settings_service import update_school_info, update_school_settings
        school = request.school
        data   = request.data

        # Split into school-level vs settings-level fields
        school_fields   = {'name', 'email', 'phone', 'address', 'city', 'state', 'country', 'website'}
        settings_fields = {
            'principal_name', 'motto', 'timezone', 'grading_system',
            'grading_scale', 'academic_year_start_month', 'allow_parent_access',
            'exam_proctoring_enabled', 'max_login_attempts', 'session_timeout_minutes',
        }

        school_data   = {k: v for k, v in data.items() if k in school_fields}
        settings_data = {k: v for k, v in data.items() if k in settings_fields}

        if school_data:
            update_school_info(school, school_data, request=request)
        if settings_data:
            update_school_settings(school, settings_data, request=request)

        from core.services.school_settings_service import get_full_school_settings
        return Response(get_full_school_settings(school))


class GradingScaleView(APIView):
    """
    GET   /api/v1/schools/settings/grading/  — retrieve grading scale + pass mark
    PUT   /api/v1/schools/settings/grading/  — replace grading scale
    """
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        from core.services.school_settings_service import get_grading_scale, get_pass_mark
        school = request.school
        return Response({
            'grading_scale': get_grading_scale(school),
            'pass_mark':     get_pass_mark(school),
        })

    def put(self, request):
        from core.services.school_settings_service import update_grading_scale
        school        = request.school
        grading_scale = request.data.get('grading_scale')
        pass_mark     = request.data.get('pass_mark')

        if not grading_scale or not isinstance(grading_scale, dict):
            return Response({'detail': 'grading_scale must be a non-empty object.'}, status=status.HTTP_400_BAD_REQUEST)

        settings_obj = update_grading_scale(school, grading_scale, pass_mark=pass_mark)
        return Response({
            'grading_scale': settings_obj.grading_scale,
            'pass_mark':     pass_mark or settings_obj.grading_scale.get('_pass_mark', 40),
        })
