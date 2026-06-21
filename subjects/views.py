"""
Views for the subjects app.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from schools.models import ClassRoom, Term
from core.mixins import SchoolQuerysetMixin, SchoolCreateMixin
from core.permissions import HasSchoolContext, IsSchoolAdminOrTeacher, IsSchoolAdmin

from .models import (
    Subject, Topic, SubjectTeacherAssignment,
    Enrollment, Prerequisite, ClassSubject,
    Timetable, TimetableSlot,
)
from .serializers import (
    SubjectSerializer, SubjectCreateSerializer, SubjectDetailSerializer,
    TopicSerializer, SubjectTeacherAssignmentSerializer,
    EnrollmentSerializer, EnrollStudentSerializer, BulkEnrollSerializer,
    PrerequisiteSerializer, ClassSubjectSerializer,
    TimetableSerializer, TimetableSlotSerializer,
)


# ============ Subjects ============

class SubjectListCreateView(SchoolQuerysetMixin, SchoolCreateMixin, generics.ListCreateAPIView):
    """List all subjects for the current school or create a new one."""

    queryset = Subject.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['department']
    filterset_fields = ['is_active', 'is_elective', 'department']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SubjectCreateSerializer
        return SubjectSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


class SubjectDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a subject."""

    queryset = Subject.objects.all()
    serializer_class = SubjectDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['department']

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


# ============ Topics ============

class TopicListCreateView(generics.ListCreateAPIView):
    """List or create topics for a subject."""

    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        subject_id = self.kwargs.get('subject_id')
        return Topic.objects.filter(
            subject_id=subject_id,
            subject__school=self.request.school,
            is_active=True,
            parent_topic__isnull=True,  # Only root topics
        ).prefetch_related('subtopics')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        subject = get_object_or_404(
            Subject, id=self.kwargs['subject_id'], school=self.request.school
        )
        serializer.save(subject=subject)


class TopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a topic."""

    serializer_class = TopicSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        return Topic.objects.filter(
            subject__school=self.request.school
        )


# ============ Teacher Assignments ============

class SubjectTeacherListCreateView(generics.ListCreateAPIView):
    """List or assign teachers to a subject."""

    serializer_class = SubjectTeacherAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        subject_id = self.kwargs.get('subject_id')
        return SubjectTeacherAssignment.objects.filter(
            subject_id=subject_id,
            subject__school=self.request.school,
        ).select_related('teacher', 'subject', 'classroom', 'term')

    def perform_create(self, serializer):
        subject = get_object_or_404(
            Subject, id=self.kwargs['subject_id'], school=self.request.school
        )
        serializer.save(subject=subject)


class SubjectTeacherRemoveView(APIView):
    """Remove a teacher assignment."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def delete(self, request, subject_id, assignment_id):
        assignment = get_object_or_404(
            SubjectTeacherAssignment,
            id=assignment_id,
            subject_id=subject_id,
            subject__school=request.school,
        )
        assignment.delete()
        return Response(
            {'message': 'Teacher assignment removed.'},
            status=status.HTTP_200_OK,
        )


# ============ Enrollments ============

class SubjectEnrollmentListView(generics.ListAPIView):
    """List all students enrolled in a subject."""

    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]
    filterset_fields = ['status', 'term', 'classroom']

    def get_queryset(self):
        subject_id = self.kwargs.get('subject_id')
        return Enrollment.objects.filter(
            subject_id=subject_id,
            subject__school=self.request.school,
        ).select_related('student', 'subject', 'classroom', 'term')


class EnrollStudentView(APIView):
    """Enroll a student in a subject."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, subject_id):
        serializer = EnrollStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subject = get_object_or_404(
            Subject, id=subject_id, school=request.school, is_active=True
        )
        student = get_object_or_404(
            User, id=serializer.validated_data['student_id']
        )
        classroom = get_object_or_404(
            ClassRoom, id=serializer.validated_data['classroom_id'], school=request.school
        )
        term = get_object_or_404(
            Term, id=serializer.validated_data['term_id'],
            academic_year__school=request.school,
        )

        # Check if already enrolled
        if Enrollment.objects.filter(
            student=student, subject=subject, term=term
        ).exists():
            return Response(
                {'detail': 'Student is already enrolled in this subject for this term.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enrollment = Enrollment.objects.create(
            student=student,
            subject=subject,
            classroom=classroom,
            term=term,
        )

        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED,
        )


class BulkEnrollView(APIView):
    """Bulk enroll multiple students in a subject."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, subject_id):
        serializer = BulkEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subject = get_object_or_404(
            Subject, id=subject_id, school=request.school, is_active=True
        )
        classroom = get_object_or_404(
            ClassRoom, id=serializer.validated_data['classroom_id'], school=request.school
        )
        term = get_object_or_404(
            Term, id=serializer.validated_data['term_id'],
            academic_year__school=request.school,
        )

        student_ids = serializer.validated_data['student_ids']
        students = User.objects.filter(id__in=student_ids)

        created = []
        skipped = []
        for student in students:
            if Enrollment.objects.filter(
                student=student, subject=subject, term=term
            ).exists():
                skipped.append(str(student.id))
            else:
                enrollment = Enrollment.objects.create(
                    student=student,
                    subject=subject,
                    classroom=classroom,
                    term=term,
                )
                created.append(str(enrollment.id))

        return Response(
            {
                'message': f'Enrolled {len(created)} students. Skipped {len(skipped)} (already enrolled).',
                'enrolled_count': len(created),
                'skipped_count': len(skipped),
            },
            status=status.HTTP_201_CREATED,
        )


class DropEnrollmentView(APIView):
    """Drop a student from a subject."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def post(self, request, subject_id, enrollment_id):
        enrollment = get_object_or_404(
            Enrollment,
            id=enrollment_id,
            subject_id=subject_id,
            subject__school=request.school,
            status=Enrollment.Status.ACTIVE,
        )
        enrollment.drop()
        return Response(
            {'message': 'Enrollment dropped successfully.'},
            status=status.HTTP_200_OK,
        )


class MyEnrollmentsView(generics.ListAPIView):
    """List current user's enrollments."""

    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['status', 'term']

    def get_queryset(self):
        return Enrollment.objects.filter(
            student=self.request.user,
            subject__school=self.request.school,
        ).select_related('subject', 'classroom', 'term')


# ============ Prerequisites ============

class PrerequisiteListCreateView(generics.ListCreateAPIView):
    """List or create prerequisites for a subject."""

    serializer_class = PrerequisiteSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        subject_id = self.kwargs.get('subject_id')
        return Prerequisite.objects.filter(
            subject_id=subject_id,
            subject__school=self.request.school,
        ).select_related('required_subject')

    def perform_create(self, serializer):
        subject = get_object_or_404(
            Subject, id=self.kwargs['subject_id'], school=self.request.school
        )
        serializer.save(subject=subject)


# ============ Class Subjects ============

class ClassSubjectListCreateView(generics.ListCreateAPIView):
    """List or assign subjects to a class."""

    serializer_class = ClassSubjectSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['term', 'is_compulsory']

    def get_queryset(self):
        classroom_id = self.kwargs.get('classroom_id')
        return ClassSubject.objects.filter(
            classroom_id=classroom_id,
            classroom__school=self.request.school,
        ).select_related('subject', 'classroom', 'term')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


# ============ Timetables ============

class TimetableListCreateView(SchoolQuerysetMixin, SchoolCreateMixin, generics.ListCreateAPIView):
    """List or create timetables."""

    queryset = Timetable.objects.all()
    serializer_class = TimetableSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['term']
    filterset_fields = ['term', 'is_active']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


class TimetableDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a timetable."""

    queryset = Timetable.objects.all()
    serializer_class = TimetableSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]
    select_related_fields = ['term']


class TimetableSlotListCreateView(generics.ListCreateAPIView):
    """List or create slots for a timetable."""

    serializer_class = TimetableSlotSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['day_of_week', 'classroom', 'teacher', 'subject']

    def get_queryset(self):
        timetable_id = self.kwargs.get('timetable_id')
        return TimetableSlot.objects.filter(
            timetable_id=timetable_id,
            timetable__school=self.request.school,
        ).select_related('subject', 'classroom', 'teacher')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdmin()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        timetable = get_object_or_404(
            Timetable, id=self.kwargs['timetable_id'], school=self.request.school
        )
        serializer.save(timetable=timetable)


class TimetableSlotDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a timetable slot."""

    serializer_class = TimetableSlotSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        return TimetableSlot.objects.filter(
            timetable__school=self.request.school
        )
