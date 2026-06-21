"""
Serializers for the notifications app.
"""

from rest_framework import serializers

from .models import Notification, BulkNotification, DeviceToken


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type', 'channel',
            'related_object_type', 'related_object_id',
            'is_read', 'read_at', 'sent_at', 'created_at',
        ]
        read_only_fields = fields


class BulkNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkNotification
        fields = [
            'id', 'title', 'message', 'target_role', 'target_classroom',
            'total_recipients', 'sent_count', 'failed_count', 'status',
            'created_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'total_recipients', 'sent_count', 'failed_count',
            'status', 'created_at', 'completed_at',
        ]


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'platform', 'device_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
