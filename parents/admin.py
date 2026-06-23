"""
Admin configuration for the parents app.
"""

from django.contrib import admin

from .models import ParentProfile


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'occupation', 'city', 'state', 'created_at']
    list_filter   = ['occupation', 'state', 'country']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'updated_at']
