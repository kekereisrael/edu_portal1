"""
URL configuration for Educational Portal project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Frontend UI
    path('', include('frontend_urls')),

    # Admin
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/schools/', include('schools.urls')),
    path('api/v1/subscriptions/', include('subscriptions.urls')),
    path('api/v1/subjects/', include('subjects.urls')),
    path('api/v1/exams/', include('exams.urls')),
    path('api/v1/materials/', include('materials.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/v1/payments/', include('payments.urls')),
    path('api/v1/payments/webhooks/', include('payments.webhook_urls')),
    path('api/v1/analytics/', include('analytics.urls')),
    path('api/v1/communications/', include('communications.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
