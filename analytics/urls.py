"""
URL configuration for the analytics app.
"""

from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('student/', views.MyStudentAnalyticsView.as_view(), name='my_analytics'),
    path('student/<uuid:student_id>/', views.StudentAnalyticsView.as_view(), name='student_analytics'),
    path('subject/<uuid:subject_id>/', views.SubjectAnalyticsView.as_view(), name='subject_analytics'),
    path('school/', views.SchoolAnalyticsView.as_view(), name='school_analytics'),
    path('ai-usage/', views.AIUsageView.as_view(), name='ai_usage'),
    path('learning-paths/', views.LearningPathListCreateView.as_view(), name='learning_path_list'),
    path('learning-paths/<uuid:pk>/', views.LearningPathDetailView.as_view(), name='learning_path_detail'),
]
