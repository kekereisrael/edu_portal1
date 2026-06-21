"""
URL configuration for the accounts app.
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # User
    path('me/', views.UserDetailView.as_view(), name='user_detail'),
    path('me/profile/', views.ProfileView.as_view(), name='profile'),
    path('me/change-password/', views.ChangePasswordView.as_view(), name='change_password'),

    # Sessions
    path('me/sessions/', views.UserSessionListView.as_view(), name='session_list'),
    path('me/sessions/<uuid:session_id>/revoke/', views.RevokeSessionView.as_view(), name='revoke_session'),
    path('me/sessions/revoke-all/', views.RevokeAllSessionsView.as_view(), name='revoke_all_sessions'),
]
