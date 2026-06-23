"""
Admin configuration for the schools app.
"""

from django.contrib import admin

from .models import (
    School, SchoolMembership, SchoolSettings,
    AcademicSession, AcademicYear, Term,
    Department, ClassRoom, ClassLevel, StudentClassAssignment,
)


# ─────────────────────────────────────────────────────────────────────────────
# Inlines
# ─────────────────────────────────────────────────────────────────────────────

class SchoolMembershipInline(admin.TabularInline):
    model = SchoolMembership
    extra = 0
    readonly_fields = ['joined_at']
    fields = ['user', 'role', 'is_active', 'joined_at']


class ClassLevelInline(admin.TabularInline):
    model = ClassLevel
    extra = 0
    fields = ['code', 'display_name', 'category', 'order', 'is_active']
    readonly_fields = ['category', 'order']


class AcademicSessionInline(admin.TabularInline):
    model = AcademicSession
    extra = 0
    fields = ['name', 'start_date', 'end_date', 'is_current']


# ─────────────────────────────────────────────────────────────────────────────
# School
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'city', 'state', 'is_active', 'created_at']
    list_filter = ['is_active', 'state', 'country', 'created_at']
    search_fields = ['name', 'email', 'city']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [SchoolMembershipInline, ClassLevelInline, AcademicSessionInline]
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('Basic Info', {
            'fields': ['name', 'slug', 'email', 'phone', 'logo', 'website'],
        }),
        ('Address', {
            'fields': ['address', 'city', 'state', 'country'],
        }),
        ('Status', {
            'fields': ['owner', 'is_active', 'created_at', 'updated_at'],
        }),
    ]


@admin.register(SchoolMembership)
class SchoolMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'school']
    search_fields = ['user__email', 'user__first_name', 'school__name']
    readonly_fields = ['joined_at']


# ─────────────────────────────────────────────────────────────────────────────
# School Settings / Profile
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(SchoolSettings)
class SchoolSettingsAdmin(admin.ModelAdmin):
    list_display = ['school', 'principal_name', 'timezone', 'grading_system', 'current_session']
    search_fields = ['school__name', 'principal_name']
    list_select_related = ['school', 'current_session']
    fieldsets = [
        ('School Profile', {
            'fields': ['school', 'principal_name', 'motto', 'current_session'],
        }),
        ('Academic Settings', {
            'fields': ['timezone', 'grading_system', 'grading_scale', 'academic_year_start_month'],
        }),
        ('Access & Security', {
            'fields': [
                'allow_parent_access', 'exam_proctoring_enabled',
                'max_login_attempts', 'session_timeout_minutes',
            ],
        }),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Academic Session
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ['school', 'name', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current', 'school']
    search_fields = ['name', 'school__name']
    readonly_fields = ['created_at']
    actions = ['mark_as_current']

    @admin.action(description='Mark selected session as current')
    def mark_as_current(self, request, queryset):
        for session in queryset:
            session.is_current = True
            session.save()
        self.message_user(request, f'{queryset.count()} session(s) marked as current.')


# ─────────────────────────────────────────────────────────────────────────────
# Academic Year & Terms  (legacy)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Department
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'head', 'created_at']
    list_filter = ['school']
    search_fields = ['name', 'school__name']


# ─────────────────────────────────────────────────────────────────────────────
# Class Level
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ClassLevel)
class ClassLevelAdmin(admin.ModelAdmin):
    list_display = ['school', 'code', 'display_name', 'category', 'order', 'is_active']
    list_filter = ['category', 'is_active', 'school']
    search_fields = ['school__name', 'code', 'display_name']
    readonly_fields = ['category', 'order', 'created_at']
    ordering = ['school', 'order']


# ─────────────────────────────────────────────────────────────────────────────
# Classroom
# ─────────────────────────────────────────────────────────────────────────────

class StudentAssignmentInline(admin.TabularInline):
    model = StudentClassAssignment
    extra = 0
    fields = ['student', 'academic_session', 'status', 'assigned_at']
    readonly_fields = ['assigned_at']
    fk_name = 'classroom'


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'school', 'grade_level', 'class_level',
        'academic_year', 'class_teacher', 'student_count', 'is_active',
    ]
    list_filter = ['grade_level', 'class_level', 'is_active', 'school']
    search_fields = ['name', 'school__name']
    list_select_related = ['school', 'class_level', 'academic_year', 'class_teacher']
    inlines = [StudentAssignmentInline]

    @admin.display(description='Students')
    def student_count(self, obj):
        return obj.student_count


# ─────────────────────────────────────────────────────────────────────────────
# Student Class Assignment
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(StudentClassAssignment)
class StudentClassAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'classroom', 'academic_session',
        'status', 'assigned_by', 'assigned_at',
    ]
    list_filter = ['status', 'academic_session', 'classroom__school']
    search_fields = [
        'student__email', 'student__first_name', 'student__last_name',
        'classroom__name',
    ]
    readonly_fields = ['assigned_at']
    list_select_related = ['student', 'classroom', 'academic_session', 'assigned_by']
    actions = ['mark_graduated', 'mark_withdrawn']

    @admin.action(description='Mark selected as Graduated')
    def mark_graduated(self, request, queryset):
        updated = queryset.update(status=StudentClassAssignment.Status.GRADUATED)
        self.message_user(request, f'{updated} assignment(s) marked as graduated.')

    @admin.action(description='Mark selected as Withdrawn')
    def mark_withdrawn(self, request, queryset):
        updated = queryset.update(status=StudentClassAssignment.Status.WITHDRAWN)
        self.message_user(request, f'{updated} assignment(s) marked as withdrawn.')
