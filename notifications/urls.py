"""
URL configuration for the notifications app.
"""

from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('<uuid:pk>/read/', views.MarkReadView.as_view(), name='mark_read'),
    path('read-all/', views.MarkAllReadView.as_view(), name='mark_all_read'),
    path('unread-count/', views.UnreadCountView.as_view(), name='unread_count'),
    path('bulk/', views.BulkNotificationCreateView.as_view(), name='bulk_create'),
    path('devices/register/', views.RegisterDeviceView.as_view(), name='register_device'),
    path('devices/<uuid:pk>/', views.RemoveDeviceView.as_view(), name='remove_device'),
]
