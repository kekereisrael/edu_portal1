"""
URL configuration for authentication views.
"""

from django.urls import path
from auth_views import (
    login_view, register_view, logout_view,
    forgot_password_view, change_password_view,
)

urlpatterns = [
    path('login/', login_view, name='auth_login'),
    path('register/', register_view, name='auth_register'),
    path('logout/', logout_view, name='auth_logout'),
    path('forgot-password/', forgot_password_view, name='auth_forgot_password'),
    path('change-password/', change_password_view, name='auth_change_password'),
]
