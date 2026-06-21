"""
Views for the materials app.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import SchoolQuerysetMixin, SchoolCreateMixin
from core.permissions import HasSchoolContext, IsSchoolAdminOrTeacher

from .models import Material, MaterialProgress, MaterialComment, MaterialBookmark, MaterialRating
from .serializers import (
    MaterialSerializer, MaterialCreateSerializer,
    MaterialProgressSerializer, UpdateProgressSerializer,
    MaterialCommentSerializer, MaterialBookmarkSerializer,
    MaterialRatingSerializer,
)


class MaterialListCreateView(SchoolQuerysetMixin, generics.ListCreateAPIView):
    """List or create materials."""

    queryset = Material.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'topic', 'uploaded_by']
    filterset_fields = ['subject', 'topic', 'term', 'material_type', 'is_published']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'order', 'created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MaterialCreateSerializer
        return MaterialSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.request, 'school_membership'):
            if self.request.school_membership and self.request.school_membership.role == 'student':
                qs = qs.filter(is_published=True)
        return qs

    def perform_create(self, serializer):
        material = serializer.save(
            school=self.request.school,
            uploaded_by=self.request.user,
        )
        # Update storage usage
        if material.file and material.file_size_bytes > 0:
            from schools.models import StorageUsage
            storage, _ = StorageUsage.objects.get_or_create(school=self.request.school)
            storage.add_file(material.file_size_bytes)


class MaterialDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a material."""

    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'topic', 'uploaded_by']

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]


class UpdateProgressView(APIView):
    """Update progress on a material."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, material_id):
        material = get_object_or_404(
            Material, id=material_id, school=request.school, is_published=True
        )
        serializer = UpdateProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        progress, created = MaterialProgress.objects.get_or_create(
            student=request.user,
            material=material,
        )
        progress.update_progress(
            percent=serializer.validated_data['progress_percent'],
            position=serializer.validated_data.get('last_position'),
            time_spent=serializer.validated_data.get('time_spent_seconds', 0),
        )

        return Response(MaterialProgressSerializer(progress).data)


class MyProgressView(generics.ListAPIView):
    """List current user's material progress."""

    serializer_class = MaterialProgressSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    filterset_fields = ['completed']

    def get_queryset(self):
        return MaterialProgress.objects.filter(
            student=self.request.user,
            material__school=self.request.school,
        ).select_related('material')


class CommentListCreateView(generics.ListCreateAPIView):
    """List or create comments on a material."""

    serializer_class = MaterialCommentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        material_id = self.kwargs.get('material_id')
        return MaterialComment.objects.filter(
            material_id=material_id,
            material__school=self.request.school,
            is_deleted=False,
            parent__isnull=True,
        ).select_related('user').prefetch_related('replies')

    def perform_create(self, serializer):
        material = get_object_or_404(
            Material, id=self.kwargs['material_id'], school=self.request.school
        )
        serializer.save(material=material, user=self.request.user)


class BookmarkToggleView(APIView):
    """Toggle bookmark on a material."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, material_id):
        material = get_object_or_404(
            Material, id=material_id, school=request.school
        )
        bookmark, created = MaterialBookmark.objects.get_or_create(
            student=request.user,
            material=material,
            defaults={'note': request.data.get('note', '')},
        )
        if not created:
            bookmark.delete()
            return Response({'message': 'Bookmark removed.', 'bookmarked': False})
        return Response({'message': 'Material bookmarked.', 'bookmarked': True}, status=status.HTTP_201_CREATED)


class MyBookmarksView(generics.ListAPIView):
    """List current user's bookmarks."""

    serializer_class = MaterialBookmarkSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return MaterialBookmark.objects.filter(
            student=self.request.user,
            material__school=self.request.school,
        ).select_related('material')


class RateMaterialView(APIView):
    """Rate a material."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, material_id):
        material = get_object_or_404(
            Material, id=material_id, school=request.school, is_published=True
        )
        serializer = MaterialRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rating, created = MaterialRating.objects.update_or_create(
            student=request.user,
            material=material,
            defaults={
                'rating': serializer.validated_data['rating'],
                'review': serializer.validated_data.get('review', ''),
            },
        )
        return Response(MaterialRatingSerializer(rating).data)
