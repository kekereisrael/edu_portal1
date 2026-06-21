"""
Admin configuration for the schools app.
"""

from django.contrib import admin

from .models import (
    School, SchoolMembership, SchoolSettings,
    AcademicYear, Term, Department, ClassRoom,
)


class SchoolMembershipInline(admin.TabularInline):
    model = SchoolMembership
    extra = 0
    readonly_fields = ['joined_at']


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'city', 'state', 'is_active', 'created_at']
    list_filter = ['is_active', 'state', 'country', 'created_at']
    search_fields = ['name', 'email', 'city']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SchoolMembershipInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SchoolMembership)
class SchoolMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'school']
    search_fields = ['user__email', 'user__first_name', 'school__name']


@admin.register(SchoolSettings)
class SchoolSettingsAdmin(admin.ModelAdmin):
    list_display = ['school', 'timezone', 'grading_system']
    search_fields = ['school__name']


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['school', 'name', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'school']
    search_fields = ['name', 'school__name']


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ['academic_year', 'name', 'start_date', 'end_date', 'is_current', 'order']
    list_filter = ['is_current', 'academic_year__school']
    search_fields = ['name', 'academic_year__name']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'head', 'created_at']
    list_filter = ['school']
    search_fields = ['name', 'school__name']


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'grade_level', 'academic_year', 'class_teacher', 'is_active']
    list_filter = ['grade_level', 'is_active', 'school']
    search_fields = ['name', 'school__name']
