"""
Views for the communications app.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import SchoolQuerysetMixin, SchoolCreateMixin
from core.permissions import HasSchoolContext, IsSchoolAdminOrTeacher

from .models import Announcement, MessageThread, ThreadParticipant, Message
from .serializers import (
    AnnouncementSerializer, AnnouncementCreateSerializer,
    MessageThreadSerializer, MessageSerializer, MessageCreateSerializer,
)


class AnnouncementListCreateView(SchoolQuerysetMixin, generics.ListCreateAPIView):
    """List or create announcements."""

    queryset = Announcement.objects.all()
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]
    select_related_fields = ['author', 'target_classroom']
    filterset_fields = ['priority', 'is_pinned', 'target_role']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AnnouncementCreateSerializer
        return AnnouncementSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), HasSchoolContext(), IsSchoolAdminOrTeacher()]
        return [permissions.IsAuthenticated(), HasSchoolContext()]

    def perform_create(self, serializer):
        serializer.save(school=self.request.school, author=self.request.user)


class AnnouncementDetailView(SchoolQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an announcement."""

    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext, IsSchoolAdminOrTeacher]


class ThreadListCreateView(generics.ListCreateAPIView):
    """List or create message threads."""

    serializer_class = MessageThreadSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return MessageThread.objects.filter(
            school=self.request.school,
            participants__user=self.request.user,
        ).select_related('created_by').distinct()

    def perform_create(self, serializer):
        thread = serializer.save(
            school=self.request.school,
            created_by=self.request.user,
        )
        # Add creator as admin participant
        ThreadParticipant.objects.create(
            thread=thread,
            user=self.request.user,
            role=ThreadParticipant.Role.ADMIN,
        )


class ThreadDetailView(generics.RetrieveAPIView):
    """Get thread detail with recent messages."""

    serializer_class = MessageThreadSerializer
    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_queryset(self):
        return MessageThread.objects.filter(
            school=self.request.school,
            participants__user=self.request.user,
        )


class MessageListCreateView(generics.ListCreateAPIView):
    """List or send messages in a thread."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MessageCreateSerializer
        return MessageSerializer

    def get_queryset(self):
        thread_id = self.kwargs.get('thread_id')
        # Verify user is a participant
        thread = get_object_or_404(
            MessageThread,
            id=thread_id,
            school=self.request.school,
            participants__user=self.request.user,
        )
        return Message.objects.filter(thread=thread).select_related('sender')

    def perform_create(self, serializer):
        thread = get_object_or_404(
            MessageThread,
            id=self.kwargs['thread_id'],
            school=self.request.school,
            participants__user=self.request.user,
        )
        message = serializer.save(thread=thread, sender=self.request.user)
        # Update thread last_message_at
        thread.last_message_at = message.created_at
        thread.save(update_fields=['last_message_at', 'updated_at'])


class MarkThreadReadView(APIView):
    """Mark a thread as read."""

    permission_classes = [permissions.IsAuthenticated, HasSchoolContext]

    def post(self, request, thread_id):
        participant = get_object_or_404(
            ThreadParticipant,
            thread_id=thread_id,
            user=request.user,
        )
        participant.last_read_at = timezone.now()
        participant.save(update_fields=['last_read_at', 'updated_at'])
        return Response({'message': 'Thread marked as read.'})
