"""
Admin configuration for the accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Profile, UserSession, LoginAttempt


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model."""

    list_display = ['email', 'first_name', 'last_name', 'role', 'is_verified', 'is_active', 'date_joined']
    list_filter = ['role', 'is_verified', 'is_active', 'is_platform_admin', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('Role & Status', {'fields': ('role', 'is_verified', 'is_platform_admin')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin for Profile model."""

    list_display = ['user', 'city', 'state', 'country']
    search_fields = ['user__email', 'user__first_name', 'city', 'state']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Admin for UserSession model."""

    list_display = ['user', 'device_type', 'ip_address', 'is_active', 'last_activity']
    list_filter = ['device_type', 'is_active']
    search_fields = ['user__email', 'ip_address']
    readonly_fields = ['token_jti', 'created_at', 'last_activity']


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin for LoginAttempt model."""

    list_display = ['email', 'ip_address', 'success', 'failure_reason', 'attempted_at']
    list_filter = ['success', 'attempted_at']
    search_fields = ['email', 'ip_address']
    readonly_fields = ['email', 'ip_address', 'user_agent', 'success', 'failure_reason', 'attempted_at']
