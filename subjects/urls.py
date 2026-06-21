"""
URL configuration for the subjects app.
"""

from django.urls import path

from . import views

app_name = 'subjects'

urlpatterns = [
    # Subjects
    path('', views.SubjectListCreateView.as_view(), name='subject_list'),
    path('<uuid:pk>/', views.SubjectDetailView.as_view(), name='subject_detail'),

    # Topics
    path('<uuid:subject_id>/topics/', views.TopicListCreateView.as_view(), name='topic_list'),
    path('topics/<uuid:pk>/', views.TopicDetailView.as_view(), name='topic_detail'),

    # Teacher Assignments
    path('<uuid:subject_id>/teachers/', views.SubjectTeacherListCreateView.as_view(), name='teacher_list'),
    path(
        '<uuid:subject_id>/teachers/<uuid:assignment_id>/',
        views.SubjectTeacherRemoveView.as_view(),
        name='teacher_remove',
    ),

    # Enrollments
    path('<uuid:subject_id>/students/', views.SubjectEnrollmentListView.as_view(), name='enrollment_list'),
    path('<uuid:subject_id>/enroll/', views.EnrollStudentView.as_view(), name='enroll_student'),
    path('<uuid:subject_id>/enroll/bulk/', views.BulkEnrollView.as_view(), name='bulk_enroll'),
    path(
        '<uuid:subject_id>/enrollments/<uuid:enrollment_id>/drop/',
        views.DropEnrollmentView.as_view(),
        name='drop_enrollment',
    ),

    # My enrollments (student view)
    path('my/enrollments/', views.MyEnrollmentsView.as_view(), name='my_enrollments'),

    # Prerequisites
    path('<uuid:subject_id>/prerequisites/', views.PrerequisiteListCreateView.as_view(), name='prerequisite_list'),

    # Class Subjects
    path('classrooms/<uuid:classroom_id>/subjects/', views.ClassSubjectListCreateView.as_view(), name='class_subjects'),

    # Timetables
    path('timetables/', views.TimetableListCreateView.as_view(), name='timetable_list'),
    path('timetables/<uuid:pk>/', views.TimetableDetailView.as_view(), name='timetable_detail'),
    path(
        'timetables/<uuid:timetable_id>/slots/',
        views.TimetableSlotListCreateView.as_view(),
        name='timetable_slot_list',
    ),
    path('timetables/slots/<uuid:pk>/', views.TimetableSlotDetailView.as_view(), name='timetable_slot_detail'),
]
