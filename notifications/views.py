"""
Views for the notifications app.
"""

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasSchoolContext, IsSchoolAdmin

from .models import Notification, BulkNotification, DeviceToken
from .serializers import (
    NotificationSerializer, BulkNotificationSerializer,
    DeviceTokenSerializer,
)


class NotificationListView(generics.ListAPIView):
    """List notifications for the current user."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['is_read', 'notification_type', 'channel']

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')


class MarkReadView(APIView):
    """Mark a notification as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(id=pk, recipient=request.user)
            notification.mark_read()
            return Response({'message': 'Notification marked as read.'})
        except Notification.DoesNotExist:
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )


class MarkAllReadView(APIView):
    """Mark all notifications as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({'message': f'{count} notifications marked as read.'})


class UnreadCountView(APIView):
    """Get unread notification count."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({'unread_count': count})


class BulkNotificationCreateView(generics.CreateAPIView):
    """Create a bulk notification (school admin only)."""

    serializer_class = BulkNotificationSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdmin]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, sent_by=self.request.user)


class RegisterDeviceView(generics.CreateAPIView):
    """Register a device token for push notifications."""

    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RemoveDeviceView(generics.DestroyAPIView):
    """Remove a device token."""

    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)
