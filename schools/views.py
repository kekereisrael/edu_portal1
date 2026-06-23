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
