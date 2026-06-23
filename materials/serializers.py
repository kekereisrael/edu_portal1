"""
Serializers for the materials app.
"""

from rest_framework import serializers
from .models import Material, MaterialProgress, MaterialComment, MaterialBookmark, MaterialRating


class MaterialSerializer(serializers.ModelSerializer):
    """List serializer for materials."""

    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    file_size_display = serializers.ReadOnlyField()
    file_url_resolved = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = [
            'id', 'title', 'description', 'subject', 'subject_name', 'subject_code',
            'topic', 'term', 'material_type', 'file', 'file_url', 'file_url_resolved',
            'file_size_bytes', 'file_size_display', 'duration_seconds',
            'is_published', 'order', 'uploaded_by', 'uploaded_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'file_size_bytes', 'uploaded_by', 'created_at', 'updated_at']

    def get_file_url_resolved(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file_url


class MaterialCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating materials."""

    class Meta:
        model = Material
        fields = [
            'id', 'title', 'description', 'subject', 'topic', 'term',
            'material_type', 'file', 'file_url', 'is_published', 'order',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        material_type = data.get('material_type', '')
        file_obj = data.get('file')
        file_url = data.get('file_url')

        if material_type == Material.MaterialType.LINK and not file_url:
            raise serializers.ValidationError({'file_url': 'URL is required for link type materials.'})
        if material_type != Material.MaterialType.LINK and not file_obj and not self.instance:
            raise serializers.ValidationError({'file': 'File is required for this material type.'})
        return data

    def create(self, validated_data):
        file_obj = validated_data.get('file')
        if file_obj:
            validated_data['file_size_bytes'] = file_obj.size
        return super().create(validated_data)

    def update(self, instance, validated_data):
        file_obj = validated_data.get('file')
        if file_obj:
            validated_data['file_size_bytes'] = file_obj.size
        return super().update(instance, validated_data)


class MaterialProgressSerializer(serializers.ModelSerializer):
    """Serializer for material progress."""

    material_title = serializers.CharField(source='material.title', read_only=True)

    class Meta:
        model = MaterialProgress
        fields = [
            'id', 'student', 'material', 'material_title',
            'progress_percent', 'last_position', 'completed',
            'completed_at', 'time_spent_seconds', 'last_accessed_at',
        ]
        read_only_fields = ['id', 'student', 'completed', 'completed_at', 'last_accessed_at']


class MaterialCommentSerializer(serializers.ModelSerializer):
    """Serializer for material comments."""

    user_name = serializers.CharField(source='user.full_name', read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = MaterialComment
        fields = [
            'id', 'material', 'user', 'user_name', 'parent',
            'content', 'is_deleted', 'replies', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']

    def get_replies(self, obj):
        if obj.parent is None:
            replies = obj.replies.filter(is_deleted=False)
            return MaterialCommentSerializer(replies, many=True, context=self.context).data
        return []


class MaterialBookmarkSerializer(serializers.ModelSerializer):
    """Serializer for material bookmarks."""

    material_title = serializers.CharField(source='material.title', read_only=True)

    class Meta:
        model = MaterialBookmark
        fields = ['id', 'student', 'material', 'material_title', 'note', 'created_at']
        read_only_fields = ['id', 'student', 'created_at']


class MaterialRatingSerializer(serializers.ModelSerializer):
    """Serializer for material ratings."""

    class Meta:
        model = MaterialRating
        fields = ['id', 'student', 'material', 'rating', 'review', 'created_at']
        read_only_fields = ['id', 'student', 'created_at']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value
