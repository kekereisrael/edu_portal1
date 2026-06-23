"""
Views for the materials app.
"""

import logging
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import SchoolQuerysetMixin, SchoolCreateMixin
from core.permissions import HasSchoolContext, IsSchoolAdminOrTeacher

from .models import Material, MaterialProgress, MaterialComment, MaterialBookmark, MaterialRating
from .serializers import (
    MaterialSerializer, MaterialCreateSerializer,
    MaterialProgressSerializer, MaterialCommentSerializer,
    MaterialBookmarkSerializer, MaterialRatingSerializer,
)

logger = logging.getLogger(__name__)


class MaterialListCreateView(SchoolQuerysetMixin, generics.ListCreateAPIView):
    """List all materials or upload a new one."""

    queryset = Material.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'topic', 'term', 'uploaded_by']
    filterset_fields = ['subject', 'topic', 'term', 'material_type', 'is_published']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'created_at', 'order']

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
        # Students only see published materials
        if hasattr(self.request, 'school_membership') and self.request.school_membership:
            if self.request.school_membership.role == 'student':
                qs = qs.filter(is_published=True)
        return qs

    def perform_create(self, serializer):
        material = serializer.save(
            school=self.request.school,
            uploaded_by=self.request.user,
        )
        # Update school storage usage
        try:
            storage = self.request.school.storage_usage
            storage.add_file(material.file_size_bytes)
        except Exception:
            pass
        return material


class MaterialDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a material."""

    queryset = Material.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['subject', 'topic', 'uploaded_by']

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return MaterialCreateSerializer
        return MaterialSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_destroy(self, instance):
        # Update storage usage
        try:
            storage = instance.school.storage_usage
            storage.remove_file(instance.file_size_bytes)
        except Exception:
            pass
        instance.delete()


class MaterialDownloadView(APIView):
    """Download a material file."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get(self, request, pk):
        material = get_object_or_404(
            Material, id=pk, school=request.school, is_published=True
        )
        if not material.file:
            return Response(
                {'detail': 'No file available for this material.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            response = FileResponse(
                material.file.open('rb'),
                as_attachment=True,
                filename=material.file.name.split('/')[-1],
            )
            return response
        except Exception as e:
            logger.error(f'Material download error: {e}')
            raise Http404('File not found.')


class MaterialProgressView(APIView):
    """Update material progress for the current student."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, pk):
        material = get_object_or_404(Material, id=pk, school=request.school)
        progress_percent = request.data.get('progress_percent', 0)
        position = request.data.get('last_position')
        time_spent = request.data.get('time_spent_seconds', 0)

        progress, _ = MaterialProgress.objects.get_or_create(
            student=request.user, material=material
        )
        progress.update_progress(progress_percent, position, time_spent)

        return Response(MaterialProgressSerializer(progress).data)

    def get(self, request, pk):
        material = get_object_or_404(Material, id=pk, school=request.school)
        try:
            progress = MaterialProgress.objects.get(student=request.user, material=material)
            return Response(MaterialProgressSerializer(progress).data)
        except MaterialProgress.DoesNotExist:
            return Response({'progress_percent': 0, 'completed': False})


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


class MaterialCommentListCreateView(generics.ListCreateAPIView):
    """List or create comments on a material."""

    serializer_class = MaterialCommentSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        material_id = self.kwargs.get('pk')
        return MaterialComment.objects.filter(
            material_id=material_id,
            material__school=self.request.school,
            is_deleted=False,
            parent__isnull=True,
        ).select_related('user').prefetch_related('replies')

    def perform_create(self, serializer):
        material = get_object_or_404(
            Material, id=self.kwargs['pk'], school=self.request.school
        )
        serializer.save(material=material, user=self.request.user)


class MaterialBookmarkView(APIView):
    """Toggle bookmark on a material."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, pk):
        material = get_object_or_404(Material, id=pk, school=request.school)
        bookmark, created = MaterialBookmark.objects.get_or_create(
            student=request.user, material=material,
            defaults={'note': request.data.get('note', '')}
        )
        if not created:
            bookmark.delete()
            return Response({'bookmarked': False})
        return Response({'bookmarked': True, 'id': str(bookmark.id)}, status=status.HTTP_201_CREATED)

    def get(self, request, pk):
        material = get_object_or_404(Material, id=pk, school=request.school)
        bookmarked = MaterialBookmark.objects.filter(
            student=request.user, material=material
        ).exists()
        return Response({'bookmarked': bookmarked})


class MyBookmarksView(generics.ListAPIView):
    """List current user's bookmarked materials."""

    serializer_class = MaterialBookmarkSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return MaterialBookmark.objects.filter(
            student=self.request.user,
            material__school=self.request.school,
        ).select_related('material')


class MaterialRatingView(APIView):
    """Rate a material."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, pk):
        material = get_object_or_404(Material, id=pk, school=request.school)
        serializer = MaterialRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rating, created = MaterialRating.objects.update_or_create(
            student=request.user, material=material,
            defaults={
                'rating': serializer.validated_data['rating'],
                'review': serializer.validated_data.get('review', ''),
            }
        )
        return Response(
            MaterialRatingSerializer(rating).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
