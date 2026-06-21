"""
Serializers for the communications app.
"""

from rest_framework import serializers

from .models import Announcement, MessageThread, ThreadParticipant, Message


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True, default=None)
    classroom_name = serializers.CharField(source='target_classroom.name', read_only=True, default=None)
    is_active = serializers.ReadOnlyField()

    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'content', 'author', 'author_name',
            'target_role', 'target_classroom', 'classroom_name',
            'priority', 'is_pinned', 'is_active',
            'published_at', 'expires_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            'title', 'content', 'target_role', 'target_classroom',
            'priority', 'is_pinned', 'published_at', 'expires_at',
        ]


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'sender_name', 'content', 'attachment',
            'is_edited', 'edited_at', 'created_at',
        ]
        read_only_fields = ['id', 'sender', 'is_edited', 'edited_at', 'created_at']


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['content', 'attachment']


class ThreadParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    unread_count = serializers.ReadOnlyField()

    class Meta:
        model = ThreadParticipant
        fields = ['id', 'user', 'user_name', 'role', 'last_read_at', 'is_muted', 'unread_count']
        read_only_fields = ['id']


class MessageThreadSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    participants_list = ThreadParticipantSerializer(source='participants', many=True, read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = MessageThread
        fields = [
            'id', 'subject', 'thread_type', 'created_by', 'created_by_name',
            'participants_list', 'last_message', 'last_message_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'last_message_at', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        last = obj.messages.order_by('-created_at').first()
        if last:
            return MessageSerializer(last).data
        return None
