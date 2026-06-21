"""
Views for the analytics app.
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasSchoolContext, IsSchoolAdminOrTeacher, IsSchoolAdmin

from .models import StudentAnalytics, SubjectAnalytics, SchoolAnalytics, LearningPath, AIUsageRecord
from .serializers import (
    StudentAnalyticsSerializer, SubjectAnalyticsSerializer,
    SchoolAnalyticsSerializer, LearningPathSerializer,
    LearningPathDetailSerializer, AIUsageRecordSerializer,
)


class MyStudentAnalyticsView(generics.ListAPIView):
    """Get current student's analytics."""

    serializer_class = StudentAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return StudentAnalytics.objects.filter(
            student=self.request.user,
            school=self.request.school,
        ).select_related('term')


class StudentAnalyticsView(generics.ListAPIView):
    """Get a specific student's analytics (teacher/admin view)."""

    serializer_class = StudentAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        student_id = self.kwargs.get('student_id')
        return StudentAnalytics.objects.filter(
            student_id=student_id,
            school=self.request.school,
        ).select_related('term')


class SubjectAnalyticsView(generics.ListAPIView):
    """Get subject analytics."""

    serializer_class = SubjectAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]

    def get_queryset(self):
        subject_id = self.kwargs.get('subject_id')
        return SubjectAnalytics.objects.filter(
            subject_id=subject_id,
            school=self.request.school,
        ).select_related('term', 'subject')


class SchoolAnalyticsView(APIView):
    """Get school-wide analytics dashboard."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def get(self, request):
        analytics = SchoolAnalytics.objects.filter(
            school=request.school
        ).order_by('-last_calculated_at').first()

        if not analytics:
            return Response({'detail': 'No analytics data available yet.'})

        return Response(SchoolAnalyticsSerializer(analytics).data)


class AIUsageView(generics.ListAPIView):
    """Get AI usage records for the school."""

    serializer_class = AIUsageRecordSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]
    filterset_fields = ['usage_type', 'user']

    def get_queryset(self):
        return AIUsageRecord.objects.filter(
            school=self.request.school
        ).select_related('user')


class LearningPathListCreateView(generics.ListCreateAPIView):
    """List or create learning paths."""

    serializer_class = LearningPathSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        qs = LearningPath.objects.filter(school=self.request.school)
        # Students see only their own
        if hasattr(self.request, 'school_membership'):
            if self.request.school_membership and self.request.school_membership.role == 'student':
                qs = qs.filter(student=self.request.user)
        return qs.select_related('student', 'subject')

    def perform_create(self, serializer):
        serializer.save(school=self.request.school)


class LearningPathDetailView(generics.RetrieveAPIView):
    """Get learning path with steps."""

    serializer_class = LearningPathDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return LearningPath.objects.filter(
            school=self.request.school
        ).prefetch_related('steps')
