"""
Serializers for the materials app.
"""

from rest_framework import serializers

from .models import Material, MaterialProgress, MaterialComment, MaterialBookmark, MaterialRating
from core.mixins import DynamicFieldsMixin


class MaterialSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    """Serializer for materials."""

    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default=None)
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True, default=None)
    file_size_display = serializers.ReadOnlyField()
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = [
            'id', 'subject', 'subject_name', 'topic', 'topic_name',
            'term', 'title', 'description', 'material_type',
            'file', 'file_url', 'file_size_bytes', 'file_size_display',
            'duration_seconds', 'is_published', 'order',
            'uploaded_by', 'uploaded_by_name', 'average_rating',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'uploaded_by', 'created_at', 'updated_at']

    def get_average_rating(self, obj):
        ratings = obj.ratings.all()
        if ratings.exists():
            return round(sum(r.rating for r in ratings) / ratings.count(), 1)
        return None


class MaterialCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating materials."""

    class Meta:
        model = Material
        fields = [
            'subject', 'topic', 'term', 'title', 'description',
            'material_type', 'file', 'file_url', 'file_size_bytes',
            'duration_seconds', 'order',
        ]


class MaterialProgressSerializer(serializers.ModelSerializer):
    """Serializer for material progress."""

    material_title = serializers.CharField(source='material.title', read_only=True)

    class Meta:
        model = MaterialProgress
        fields = [
            'id', 'material', 'material_title', 'progress_percent',
            'last_position', 'completed', 'completed_at',
            'time_spent_seconds', 'last_accessed_at',
        ]
        read_only_fields = fields


class UpdateProgressSerializer(serializers.Serializer):
    """Serializer for updating progress."""

    progress_percent = serializers.IntegerField(min_value=0, max_value=100)
    last_position = serializers.IntegerField(required=False, min_value=0)
    time_spent_seconds = serializers.IntegerField(required=False, min_value=0, default=0)


class MaterialCommentSerializer(serializers.ModelSerializer):
    """Serializer for material comments."""

    user_name = serializers.CharField(source='user.full_name', read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = MaterialComment
        fields = [
            'id', 'material', 'user', 'user_name', 'parent',
            'content', 'replies', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_replies(self, obj):
        if obj.replies.filter(is_deleted=False).exists():
            return MaterialCommentSerializer(
                obj.replies.filter(is_deleted=False), many=True, context=self.context
            ).data
        return []


class MaterialBookmarkSerializer(serializers.ModelSerializer):
    """Serializer for bookmarks."""

    material_title = serializers.CharField(source='material.title', read_only=True)

    class Meta:
        model = MaterialBookmark
        fields = ['id', 'material', 'material_title', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']


class MaterialRatingSerializer(serializers.ModelSerializer):
    """Serializer for ratings."""

    class Meta:
        model = MaterialRating
        fields = ['id', 'material', 'rating', 'review', 'created_at']
        read_only_fields = ['id', 'material', 'created_at']
