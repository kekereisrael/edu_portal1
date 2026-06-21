"""
Django admin configuration for the subjects app.
"""

from django.contrib import admin

from .models import (
    Subject, Topic, SubjectTeacherAssignment,
    Enrollment, Prerequisite, ClassSubject,
    Timetable, TimetableSlot,
)


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0
    fields = ['name', 'parent_topic', 'order', 'is_active']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'school', 'department', 'is_elective', 'is_active']
    list_filter = ['school', 'is_elective', 'is_active', 'department']
    search_fields = ['name', 'code', 'description']
    inlines = [TopicInline]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'parent_topic', 'order', 'is_active']
    list_filter = ['subject__school', 'is_active']
    search_fields = ['name', 'subject__name']


@admin.register(SubjectTeacherAssignment)
class SubjectTeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject', 'classroom', 'term', 'is_primary']
    list_filter = ['subject__school', 'term', 'is_primary']
    search_fields = ['teacher__email', 'subject__name']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'classroom', 'term', 'status', 'enrolled_at']
    list_filter = ['subject__school', 'status', 'term']
    search_fields = ['student__email', 'subject__name']


@admin.register(Prerequisite)
class PrerequisiteAdmin(admin.ModelAdmin):
    list_display = ['subject', 'required_subject', 'minimum_grade']
    list_filter = ['subject__school']


@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ['classroom', 'subject', 'term', 'is_compulsory']
    list_filter = ['classroom__school', 'term', 'is_compulsory']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'term', 'is_active']
    list_filter = ['school', 'is_active']


@admin.register(TimetableSlot)
class TimetableSlotAdmin(admin.ModelAdmin):
    list_display = ['timetable', 'day_of_week', 'start_time', 'end_time', 'subject', 'classroom', 'teacher']
    list_filter = ['timetable__school', 'day_of_week']
