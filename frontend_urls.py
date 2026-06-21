"""
URL configuration for frontend template views.
"""

from django.urls import path
from frontend_views import dashboard_view, exam_page_view

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('exam/', exam_page_view, name='exam_page'),
]
