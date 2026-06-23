"""
Views for the parents app.

Endpoints:
  School Admin:
    GET/POST   /api/v1/parents/                          — list/create parents
    GET/PATCH  /api/v1/parents/<membership_id>/          — detail/update parent
    DELETE     /api/v1/parents/<membership_id>/          — deactivate parent
    POST       /api/v1/parents/<membership_id>/link-student/   — link to student
    DELETE     /api/v1/parents/<membership_id>/unlink-student/ — unlink student
    GET        /api/v1/parents/<membership_id>/children/ — list linked children

  Parent (self-service):
    GET/PATCH  /api/v1/parents/me/                       — own profile
    GET        /api/v1/parents/me/children/              — own children + their data
    GET        /api/v1/parents/me/dashboard/             — parent dashboard
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasSchoolContext, IsSchoolAdmin, IsParent
from schools.models import SchoolMembership, ParentStudentLink
from .models import ParentProfile
from .serializers import (
    ParentProfileSerializer,
    UpdateParentProfileSerializer,
    CreateParentSerializer,
    ParentStudentLinkSerializer,
    ParentStudentLinkDetailSerializer,
    ParentMembershipSerializer,
)

UserModel = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# School Admin — Parent Management
# ─────────────────────────────────────────────────────────────────────────────

class ParentListCreateView(APIView):
    """
    GET  /api/v1/parents/  — list all parents in the school
    POST /api/v1/parents/  — create / invite a parent
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        qs = SchoolMembership.objects.filter(
            school=request.school,
            role=SchoolMembership.SchoolRole.PARENT,
            is_active=True,
        ).select_related('user').order_by('user__last_name', 'user__first_name')

        if search:
            from django.db.models import Q as DQ
            qs = qs.filter(
                DQ(user__first_name__icontains=search) |
                DQ(user__last_name__icontains=search) |
                DQ(user__email__icontains=search)
            )

        serializer = ParentMembershipSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        from core.services.parent_service import create_parent_user

        serializer = CreateParentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data['email'].lower()

        # Check duplicate active membership
        if SchoolMembership.objects.filter(
            school=request.school, user__email=email, is_active=True,
        ).exists():
            return Response(
                {'detail': f'A member with email {email} already belongs to this school.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            user, membership, created_user = create_parent_user(
                school=request.school,
                email=email,
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data.get('phone', ''),
                invited_by=request.user,
                send_welcome_email=data.get('send_welcome_email', True),
            )
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        membership.refresh_from_db()
        return Response(
            ParentMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class ParentDetailView(APIView):
    """
    GET    /api/v1/parents/<membership_id>/  — parent detail
    DELETE /api/v1/parents/<membership_id>/  — deactivate parent
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def _get_membership(self, request, membership_id):
        return get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            role=SchoolMembership.SchoolRole.PARENT,
        )

    def get(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        return Response(ParentMembershipSerializer(membership).data)

    def delete(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        membership.is_active = False
        membership.save(update_fields=['is_active'])
        return Response({'message': 'Parent deactivated successfully.'}, status=status.HTTP_200_OK)


class ParentLinkStudentView(APIView):
    """
    POST /api/v1/parents/<membership_id>/link-student/
    Link a parent to a student in the same school.
    Body: { "student_id": "<uuid>", "relationship": "Father" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def post(self, request, membership_id):
        from core.services.parent_service import link_parent_to_student

        membership = get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            role=SchoolMembership.SchoolRole.PARENT,
            is_active=True,
        )

        serializer = ParentStudentLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = get_object_or_404(
            UserModel,
            id=data['student_id'],
            school_memberships__school=request.school,
            school_memberships__role=SchoolMembership.SchoolRole.STUDENT,
            school_memberships__is_active=True,
        )

        try:
            link = link_parent_to_student(
                school=request.school,
                parent_user=membership.user,
                student_user=student,
                relationship=data.get('relationship', 'parent'),
                linked_by=request.user,
                auto_approve=True,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ParentStudentLinkDetailSerializer(link).data,
            status=status.HTTP_201_CREATED,
        )


class ParentUnlinkStudentView(APIView):
    """
    DELETE /api/v1/parents/<membership_id>/unlink-student/
    Remove the link between a parent and a student.
    Body: { "student_id": "<uuid>" }
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def delete(self, request, membership_id):
        from core.services.parent_service import unlink_parent_from_student

        membership = get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            role=SchoolMembership.SchoolRole.PARENT,
        )

        student_id = request.data.get('student_id')
        if not student_id:
            return Response(
                {'detail': 'student_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = get_object_or_404(UserModel, id=student_id)

        try:
            unlink_parent_from_student(
                school=request.school,
                parent_user=membership.user,
                student_user=student,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Parent-student link removed.'}, status=status.HTTP_200_OK)


class ParentChildrenView(APIView):
    """
    GET /api/v1/parents/<membership_id>/children/
    List all students linked to this parent in the school.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request, membership_id):
        membership = get_object_or_404(
            SchoolMembership,
            id=membership_id,
            school=request.school,
            role=SchoolMembership.SchoolRole.PARENT,
        )

        links = ParentStudentLink.objects.filter(
            school=request.school,
            parent=membership.user,
        ).select_related('student')

        data = [
            {
                'link_id': str(link.id),
                'student_id': str(link.student.id),
                'student_name': link.student.get_full_name(),
                'student_email': link.student.email,
                'relationship': link.relationship,
                'status': link.status,
                'created_at': link.created_at.isoformat(),
            }
            for link in links
        ]
        return Response(data)


# ─────────────────────────────────────────────────────────────────────────────
# Parent Self-Service
# ─────────────────────────────────────────────────────────────────────────────

class ParentMeView(APIView):
    """
    GET   /api/v1/parents/me/   — get own parent profile
    PATCH /api/v1/parents/me/   — update own parent profile
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsParent]

    def get(self, request):
        profile, _ = ParentProfile.objects.get_or_create(user=request.user)
        return Response(ParentProfileSerializer(profile, context={'request': request}).data)

    def patch(self, request):
        profile, _ = ParentProfile.objects.get_or_create(user=request.user)
        serializer = UpdateParentProfileSerializer(
            profile, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ParentProfileSerializer(profile, context={'request': request}).data)


class ParentMyChildrenView(APIView):
    """
    GET /api/v1/parents/me/children/
    List the parent's own linked children in the current school.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsParent]

    def get(self, request):
        links = ParentStudentLink.objects.filter(
            school=request.school,
            parent=request.user,
            status=ParentStudentLink.Status.APPROVED,
        ).select_related('student')

        from schools.models import StudentClassAssignment
        children = []
        for link in links:
            student = link.student
            assignment = StudentClassAssignment.objects.filter(
                school=request.school,
                student=student,
                status=StudentClassAssignment.Status.ACTIVE,
            ).select_related('classroom', 'academic_session').first()

            children.append({
                'link_id': str(link.id),
                'student_id': str(student.id),
                'student_name': student.get_full_name(),
                'student_email': student.email,
                'relationship': link.relationship,
                'current_class': (
                    {
                        'classroom': assignment.classroom.name,
                        'session': assignment.academic_session.name,
                    }
                    if assignment else None
                ),
            })

        return Response({'children': children, 'count': len(children)})


class ParentDashboardView(APIView):
    """
    GET /api/v1/parents/me/dashboard/
    Returns the parent dashboard: children, their results, upcoming exams.
    """

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsParent]

    def get(self, request):
        from core.services.parent_service import get_parent_dashboard_data
        data = get_parent_dashboard_data(request.user, request.school)
        return Response(data)
