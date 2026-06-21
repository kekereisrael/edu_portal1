"""
URL configuration for the communications app.
"""

from django.urls import path

from . import views

app_name = 'communications'

urlpatterns = [
    # Announcements
    path('announcements/', views.AnnouncementListCreateView.as_view(), name='announcement_list'),
    path('announcements/<uuid:pk>/', views.AnnouncementDetailView.as_view(), name='announcement_detail'),

    # Threads
    path('threads/', views.ThreadListCreateView.as_view(), name='thread_list'),
    path('threads/<uuid:pk>/', views.ThreadDetailView.as_view(), name='thread_detail'),
    path('threads/<uuid:thread_id>/messages/', views.MessageListCreateView.as_view(), name='message_list'),
    path('threads/<uuid:thread_id>/read/', views.MarkThreadReadView.as_view(), name='mark_read'),
]
