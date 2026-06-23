"""
URL configuration for the parents app.
"""

from django.urls import path

from . import views

app_name = 'parents'

urlpatterns = [
    # ── School Admin — Parent Management ─────────────────────────────────────
    # GET    /api/v1/parents/                              — list parents
    # POST   /api/v1/parents/                              — create/invite parent
    path('', views.ParentListCreateView.as_view(), name='parent_list'),

    # GET    /api/v1/parents/me/                           — own profile (parent)
    # PATCH  /api/v1/parents/me/                           — update own profile
    path('me/', views.ParentMeView.as_view(), name='parent_me'),

    # GET    /api/v1/parents/me/children/                  — own children
    path('me/children/', views.ParentMyChildrenView.as_view(), name='parent_my_children'),

    # GET    /api/v1/parents/me/dashboard/                 — parent dashboard
    path('me/dashboard/', views.ParentDashboardView.as_view(), name='parent_dashboard'),

    # GET    /api/v1/parents/<id>/                         — parent detail
    # DELETE /api/v1/parents/<id>/                         — deactivate parent
    path('<uuid:membership_id>/', views.ParentDetailView.as_view(), name='parent_detail'),

    # POST   /api/v1/parents/<id>/link-student/            — link to student
    path('<uuid:membership_id>/link-student/', views.ParentLinkStudentView.as_view(), name='parent_link_student'),

    # DELETE /api/v1/parents/<id>/unlink-student/          — unlink student
    path('<uuid:membership_id>/unlink-student/', views.ParentUnlinkStudentView.as_view(), name='parent_unlink_student'),

    # GET    /api/v1/parents/<id>/children/                — list linked children
    path('<uuid:membership_id>/children/', views.ParentChildrenView.as_view(), name='parent_children'),
]
