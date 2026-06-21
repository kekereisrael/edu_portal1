"""
Views for the schools app.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from .models import (
    School, SchoolMembership, SchoolSettings,
    AcademicYear, Term, Department, ClassRoom,
)
from .permissions import HasSchoolContext, IsSchoolAdmin, IsPlatformAdmin
from .serializers import (
    SchoolSerializer, SchoolCreateSerializer,
    SchoolMembershipSerializer, AddMemberSerializer,
    SchoolSettingsSerializer, AcademicYearSerializer,
    TermSerializer, DepartmentSerializer, ClassRoomSerializer,
)


# ============ School CRUD ============

class SchoolCreateView(generics.CreateAPIView):
    """Create a new school (registers the user as school admin)."""

    serializer_class = SchoolCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        school = serializer.save(owner=self.request.user)
        # Create default settings
        SchoolSettings.objects.create(school=school)
        # Add owner as school admin member
        SchoolMembership.objects.create(
            school=school,
            user=self.request.user,
            role=SchoolMembership.SchoolRole.SCHOOL_ADMIN,
        )
        # Update user role if not already school_admin
        if self.request.user.role != User.Role.SCHOOL_ADMIN:
            self.request.user.role = User.Role.SCHOOL_ADMIN
            self.request.user.save(update_fields=['role'])

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        school = School.objects.get(pk=serializer.instance.pk)
        return Response(
            SchoolSerializer(school).data,
            status=status.HTTP_201_CREATED,
        )


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


# ============ Membership Management ============

class MemberListView(generics.ListAPIView):
    """List all members of the current school."""

    serializer_class = SchoolMembershipSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_queryset(self):
        queryset = SchoolMembership.objects.filter(
            school=self.request.school
        ).select_related('user', 'school')

        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset


class AddMemberView(APIView):
    """Add a member to the current school."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request):
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        role = serializer.validated_data['role']

        # Find or inform about user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'detail': f'No user found with email {email}. They must register first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if already a member
        if SchoolMembership.objects.filter(school=request.school, user=user).exists():
            return Response(
                {'detail': 'User is already a member of this school.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create membership
        membership = SchoolMembership.objects.create(
            school=request.school,
            user=user,
            role=role,
        )

        return Response(
            SchoolMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class RemoveMemberView(APIView):
    """Remove a member from the current school."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, membership_id):
        membership = get_object_or_404(
            SchoolMembership, id=membership_id, school=request.school
        )

        # Cannot remove the school owner
        if membership.user == request.school.owner:
            return Response(
                {'detail': 'Cannot remove the school owner.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.is_active = False
        membership.save(update_fields=['is_active'])

        return Response(
            {'message': 'Member removed successfully.'},
            status=status.HTTP_200_OK,
        )


# ============ School Settings ============

class SchoolSettingsView(generics.RetrieveUpdateAPIView):
    """Get or update school settings."""

    serializer_class = SchoolSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get_object(self):
        settings, _ = SchoolSettings.objects.get_or_create(school=self.request.school)
        return settings


# ============ Academic Year & Terms ============

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


# ============ Departments ============

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


# ============ Classrooms ============

class ClassRoomListCreateView(generics.ListCreateAPIView):
    """List or create classrooms."""

    serializer_class = ClassRoomSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['grade_level', 'academic_year', 'is_active']

    def get_queryset(self):
        return ClassRoom.objects.filter(
            school=self.request.school
        ).select_related('academic_year', 'class_teacher')

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
