"""
URL configuration for frontend template views.
Role-based routing: Student → /student/dashboard/, Teacher → /teacher/dashboard/, Admin → /admin-dashboard/
"""

from django.urls import path
from frontend_views import (
    dashboard_view,
    student_dashboard_view,
    teacher_dashboard_view,
    admin_dashboard_view,
    exam_page_view,
    courses_view,
    homeworks_view,
    statistics_view,
    # Phase 5B views
    subjects_view,
    materials_view,
    exams_manage_view,
    exam_create_view,
    exam_edit_view,
    exam_questions_view,
    results_view,
    notifications_view,
    # Phase 6E — PWA
    offline_view,
)

urlpatterns = [
    # Root — redirects to role-based dashboard
    path('', dashboard_view, name='dashboard'),

    # Role-based dashboards
    path('student/dashboard/', student_dashboard_view, name='student_dashboard'),
    path('teacher/dashboard/', teacher_dashboard_view, name='teacher_dashboard'),
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),

    # Core pages
    path('exam/', exam_page_view, name='exam_page'),
    path('courses/', courses_view, name='courses'),
    path('homeworks/', homeworks_view, name='homeworks'),
    path('statistics/', statistics_view, name='statistics'),

    # Phase 5B pages
    path('subjects/', subjects_view, name='subjects'),
    path('materials/', materials_view, name='materials'),
    path('exams/', exams_manage_view, name='exams_manage'),
    path('exams/create/', exam_create_view, name='exam_create'),
    path('exams/<uuid:exam_id>/edit/', exam_edit_view, name='exam_edit'),
    path('exams/<uuid:exam_id>/questions/', exam_questions_view, name='exam_questions'),
    path('results/', results_view, name='results'),
    path('notifications/', notifications_view, name='notifications'),

    # Phase 6E — PWA offline fallback
    path('offline/', offline_view, name='offline'),
]
