"""
Django admin for the results app.
"""

from decimal import Decimal
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count

from .models import GradeConfig, ResultSheet, StudentScore, ReportCard, ScoreEntryBatch


# ─────────────────────────────────────────────────────────────────────────────
# GRADE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(GradeConfig)
class GradeConfigAdmin(admin.ModelAdmin):
    list_display = [
        'school', 'system', 'pass_mark',
        'ca_max_score', 'exam_max_score', 'total_max_display',
        'band_count',
    ]
    list_filter = ['system']
    search_fields = ['school__name']
    readonly_fields = ['total_max_display', 'created_at', 'updated_at']
    fieldsets = (
        ('School', {'fields': ('school',)}),
        ('Grading System', {
            'fields': ('system', 'pass_mark', 'ca_max_score', 'exam_max_score', 'total_max_display'),
        }),
        ('Grade Bands (JSON)', {
            'fields': ('bands',),
            'description': (
                'List of grade bands ordered highest → lowest. '
                'Each entry: {"grade": "A1", "min": 75, "max": 100, "remark": "Excellent", "points": 1}'
            ),
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def total_max_display(self, obj):
        return obj.total_max
    total_max_display.short_description = 'Total Max'

    def band_count(self, obj):
        return len(obj.bands) if obj.bands else 0
    band_count.short_description = '# Bands'

    actions = ['reset_to_nigerian_defaults']

    @admin.action(description='Reset selected configs to Nigerian A1–F9 defaults')
    def reset_to_nigerian_defaults(self, request, queryset):
        count = 0
        for config in queryset:
            config.bands = GradeConfig.nigerian_default_bands()
            config.system = GradeConfig.GradeSystem.NIGERIAN
            config.save(update_fields=['bands', 'system', 'updated_at'])
            count += 1
        self.message_user(request, f'Reset {count} grade config(s) to Nigerian defaults.')


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT SCORE INLINE
# ─────────────────────────────────────────────────────────────────────────────

class StudentScoreInline(admin.TabularInline):
    model = StudentScore
    extra = 0
    fields = [
        'student', 'subject',
        'ca1_score', 'ca2_score', 'ca3_score', 'exam_score',
        'total_score', 'percentage', 'grade', 'is_absent',
    ]
    readonly_fields = ['total_score', 'percentage', 'grade']
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'subject')


class ReportCardInline(admin.TabularInline):
    model = ReportCard
    extra = 0
    fields = [
        'student', 'average_score', 'total_score',
        'subjects_offered', 'subjects_passed', 'class_position',
        'class_teacher_remark',
    ]
    readonly_fields = [
        'average_score', 'total_score',
        'subjects_offered', 'subjects_passed', 'class_position',
    ]
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student')


# ─────────────────────────────────────────────────────────────────────────────
# RESULT SHEET
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ResultSheet)
class ResultSheetAdmin(admin.ModelAdmin):
    list_display = [
        'classroom', 'term', 'school', 'status_badge',
        'score_count', 'student_count',
        'published_by', 'published_at', 'created_at',
    ]
    list_filter = ['status', 'school', 'term__academic_year']
    search_fields = ['classroom__name', 'school__name', 'term__name']
    readonly_fields = [
        'published_by', 'published_at', 'created_at', 'updated_at',
        'score_count', 'student_count',
    ]
    date_hierarchy = 'created_at'
    inlines = [ReportCardInline]
    fieldsets = (
        ('Sheet Info', {
            'fields': ('school', 'classroom', 'term', 'academic_session'),
        }),
        ('Status', {
            'fields': ('status', 'published_by', 'published_at'),
        }),
        ('Report Card Settings', {
            'fields': ('next_term_begins', 'principal_remark'),
        }),
        ('Stats', {
            'fields': ('score_count', 'student_count'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colours = {
            'draft': '#6c757d',
            'under_review': '#fd7e14',
            'published': '#28a745',
            'archived': '#343a40',
        }
        colour = colours.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>',
            colour, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    def score_count(self, obj):
        return obj.scores.count()
    score_count.short_description = 'Scores'

    def student_count(self, obj):
        return obj.report_cards.count()
    student_count.short_description = 'Students'

    actions = ['publish_sheets', 'unpublish_sheets']

    @admin.action(description='Publish selected result sheets')
    def publish_sheets(self, request, queryset):
        count = 0
        for sheet in queryset.filter(status__in=['draft', 'under_review']):
            sheet.publish(published_by=request.user)
            count += 1
        self.message_user(request, f'Published {count} result sheet(s).')

    @admin.action(description='Unpublish (revert to draft) selected result sheets')
    def unpublish_sheets(self, request, queryset):
        count = 0
        for sheet in queryset.filter(status='published'):
            sheet.unpublish()
            count += 1
        self.message_user(request, f'Unpublished {count} result sheet(s).')


# ─────────────────────────────────────────────────────────────────────────────
# STUDENT SCORE
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(StudentScore)
class StudentScoreAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'subject', 'result_sheet',
        'ca1_score', 'ca2_score', 'ca3_score', 'exam_score',
        'total_score', 'percentage', 'grade_badge', 'is_absent',
    ]
    list_filter = [
        'result_sheet__school', 'result_sheet__term',
        'grade', 'is_absent',
    ]
    search_fields = [
        'student__first_name', 'student__last_name', 'student__email',
        'subject__name', 'subject__code',
    ]
    readonly_fields = [
        'total_ca', 'total_score', 'percentage',
        'grade', 'grade_remark', 'grade_points',
        'entered_by', 'created_at', 'updated_at',
    ]
    fieldsets = (
        ('Identity', {'fields': ('result_sheet', 'student', 'subject')}),
        ('Scores', {
            'fields': (
                'ca1_score', 'ca2_score', 'ca3_score', 'exam_score',
                'is_absent',
            ),
        }),
        ('Computed (read-only)', {
            'fields': (
                'total_ca', 'total_score', 'percentage',
                'grade', 'grade_remark', 'grade_points',
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('entered_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def grade_badge(self, obj):
        colour_map = {
            'A1': '#28a745', 'B2': '#5cb85c', 'B3': '#5cb85c',
            'C4': '#17a2b8', 'C5': '#17a2b8', 'C6': '#17a2b8',
            'D7': '#ffc107', 'E8': '#fd7e14',
            'F9': '#dc3545', 'F': '#dc3545',
            'ABS': '#6c757d',
        }
        colour = colour_map.get(obj.grade, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 6px;border-radius:3px;font-weight:bold;">{}</span>',
            colour, obj.grade or '—',
        )
    grade_badge.short_description = 'Grade'

    def save_model(self, request, obj, form, change):
        obj.entered_by = request.user
        super().save_model(request, obj, form, change)


# ─────────────────────────────────────────────────────────────────────────────
# REPORT CARD
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'result_sheet', 'average_score',
        'class_position', 'out_of',
        'subjects_offered', 'subjects_passed', 'subjects_failed',
    ]
    list_filter = [
        'result_sheet__school', 'result_sheet__term',
        'result_sheet__status',
    ]
    search_fields = [
        'student__first_name', 'student__last_name', 'student__email',
    ]
    readonly_fields = [
        'total_score', 'average_score',
        'subjects_offered', 'subjects_passed', 'subjects_failed',
        'class_position', 'out_of', 'computed_at', 'created_at',
    ]
    fieldsets = (
        ('Identity', {'fields': ('result_sheet', 'student')}),
        ('Academic Stats (computed)', {
            'fields': (
                'total_score', 'average_score',
                'subjects_offered', 'subjects_passed', 'subjects_failed',
                'class_position', 'out_of',
            ),
        }),
        ('Remarks', {
            'fields': ('class_teacher_remark', 'principal_remark'),
        }),
        ('Attendance', {
            'fields': ('days_present', 'days_absent', 'days_in_term'),
        }),
        ('Affective Domain', {
            'fields': ('punctuality', 'neatness', 'attentiveness', 'sports'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('computed_at', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['recompute_selected']

    @admin.action(description='Recompute selected report cards from scores')
    def recompute_selected(self, request, queryset):
        count = 0
        for card in queryset:
            card.recompute()
            count += 1
        self.message_user(request, f'Recomputed {count} report card(s).')


# ─────────────────────────────────────────────────────────────────────────────
# SCORE ENTRY BATCH
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(ScoreEntryBatch)
class ScoreEntryBatchAdmin(admin.ModelAdmin):
    list_display = [
        'result_sheet', 'subject', 'entered_by',
        'scores_entered', 'scores_updated', 'created_at',
    ]
    list_filter = ['result_sheet__school', 'result_sheet__term']
    search_fields = ['subject__name', 'entered_by__email']
    readonly_fields = [
        'result_sheet', 'subject', 'entered_by',
        'scores_entered', 'scores_updated', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
