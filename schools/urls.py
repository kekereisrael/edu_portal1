"""
URL configuration for the schools app.
"""

from django.urls import path

from . import views

app_name = 'schools'

urlpatterns = [
    # School CRUD
    path('', views.SchoolListView.as_view(), name='school_list'),
    path('create/', views.SchoolCreateView.as_view(), name='school_create'),
    path('current/', views.SchoolDetailView.as_view(), name='school_detail'),

    # Settings
    path('settings/', views.SchoolSettingsView.as_view(), name='school_settings'),

    # Members
    path('members/', views.MemberListView.as_view(), name='member_list'),
    path('members/add/', views.AddMemberView.as_view(), name='add_member'),
    path('members/<uuid:membership_id>/remove/', views.RemoveMemberView.as_view(), name='remove_member'),

    # Academic Years
    path('academic-years/', views.AcademicYearListCreateView.as_view(), name='academic_year_list'),
    path('academic-years/<uuid:pk>/', views.AcademicYearDetailView.as_view(), name='academic_year_detail'),
    path('academic-years/<uuid:academic_year_id>/terms/', views.TermListCreateView.as_view(), name='term_list'),

    # Departments
    path('departments/', views.DepartmentListCreateView.as_view(), name='department_list'),
    path('departments/<uuid:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),

    # Classrooms
    path('classrooms/', views.ClassRoomListCreateView.as_view(), name='classroom_list'),
    path('classrooms/<uuid:pk>/', views.ClassRoomDetailView.as_view(), name='classroom_detail'),
]
